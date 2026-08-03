# 数据获取与降级路径

---

## 主源：GitHub 价格缓存（唯一可信来源）

```
https://raw.githubusercontent.com/zhenyuanhuang358/work/main/stock_prices.json
```

**结构**（`tail_risk` 区块由 `scripts/fetch_prices.py` 生成）：
```json
{
  "updated_at": "2026-08-03T02:53:16Z",
  "vix": 15.99,
  "treasury_10y": 4.72,
  "tail_risk": {
    "vix9d": 13.05,          // ^VIX9D  9日VIX
    "vix3m": 19.02,          // ^VIX3M  3月VIX
    "skew": 141.23,          // ^SKEW   CBOE SKEW
    "vvix": 91.64,           // ^VVIX   波动率的波动率
    "term_structure": 0.841, // VIX / VIX3M  —— <1 contango, >1 倒挂
    "short_end_ratio": 0.816 // VIX9D / VIX
  },
  "prices": { ... }
}
```

**上线验证记录（2026-08-03）**：6/6 指标全部成功拉取，yfinance 对 ^VIX9D / ^VIX3M / ^SKEW / ^VVIX
均有数据。此为实测非假设。

---

## 刷新流程（与 us-options-agent 的 R-D0 同源，每次必做）

缓存由 GitHub Action 维护，定时任务可能滞后数小时。**每次判定前必须主动触发刷新。**

**Step 1 — 触发**：用 `mcp__github__push_files` 推 trigger 文件到 main
```
owner: zhenyuanhuang358    repo: work    branch: main
files: [{"path": "price_fetch_trigger.txt", "content": "[ISO时间] triggered by tail-risk-monitor"}]
```

**Step 2 — 轮询等待**，直到 `updated_at` 超过当日零点：
```bash
until curl -sf "https://raw.githubusercontent.com/zhenyuanhuang358/work/main/stock_prices.json" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d['updated_at'] > '[当前日期]T00:00:00' else 1)" \
  2>/dev/null; do sleep 8; done && echo "prices updated"
```

> 🔴 **不等到刷新完成不出裁定。**不用旧缓存降级，不先出"临时版"。
> 这条与 us-options-agent 完全一致——尾部指标用隔夜数据判断当日环境是没有意义的。

**若与 us-options-agent 在同一次对话中连续运行**：两者共用同一份缓存，
**只需触发一次刷新**，不要重复触发。

---

## 日变化率的计算（加速度规则需要）

缓存只存当前值，**没有历史序列**。三条路径按序尝试：

| 优先级 | 路径 | 说明 |
|--------|------|------|
| 1 | 对话内的前一次读数 | 若同一会话中此前跑过本 skill，直接对比 |
| 2 | WebSearch 查前一交易日收盘 | `CBOE SKEW index [日期] close`、`VVIX historical [日期]` |
| 3 | **放弃并明确声明** | 输出中写「加速度未检查（无历史基准）」并将置信度降一级 |

**绝不允许**：用当前值倒推、用行业惯例值填充、或跳过加速度检查而不声明。

---

## 降级路径

| 故障 | 处理 |
|------|------|
| 整个缓存文件拉取失败 | WebSearch 兜底查 VIX/SKEW/VVIX 当前值，报告顶部注明「数据来自网络检索，非缓存，需平台二次确认」 |
| `tail_risk` 区块缺失（脚本未部署） | 检查 main 分支 `scripts/fetch_prices.py` 是否含 INDEX_TICKERS 的四个尾部指标；缺失则说明未同步推 main（参见 profile.md 1.1 节同类事故） |
| 单个指标为 null | 该指标不计分，标注「X/4 可用」，置信度降一级；仅1个可用时不输出灯色 |
| Action 长时间不更新 | 查 GitHub Actions 页面 fetch-prices 最新 run 日志；期间不出裁定 |

---

## 可选扩展（尚未接入，需要时再加）

以下指标能提升判定质量，但当前未纳入，避免过度工程：

| 指标 | 价值 | 获取方式 |
|------|------|---------|
| HYG / LQD 信用利差 | 跨资产压力确认，股票之外的第二意见 | 已在 prices 里有 TLT，可加 HYG |
| 杠杆ETF规模变化 | 那篇文章的结构性风险源头 | 无免费API，需 WebSearch |
| 个股 25-delta put/call skew | 单标的层面的尾部定价 | marketchameleon / barchart，需逐个查 |
| put/call ratio | 情绪指标 | ^PCALL 或 CBOE 官网 |

**加入原则**：只有当现有四指标出现明确失灵（记录在 indicators.md 校准记录里）时才扩展，
不为了"更全面"而增加噪音。
