# 每日扫描模板：《今日美股期权机会》

用户触发「今日期权机会」「每日扫描」「今天有什么机会」时，
**严格按以下顺序**执行数据获取，然后输出报告。

---

## 扫描清单（分三轨，顺序不可颠倒）

### 第零步：读持仓日志（出报告前必做）

读取 `references/position-journal.md`，提取：
- 当前总风险敞口（各仓位最大亏损之和）
- 距上限 $2,550 的剩余空间
- 有无需要关注的仓位（接近止损 / 即将到期）

在报告的「账户状态提醒」部分用实际数字填写，而非模板占位符。
若日志显示敞口已满 → 本日只输出观察，不推荐新仓。

---

### 第零轨：触发 GitHub Action 刷新价格缓存（每次必做，最先执行）

> ⚠️ GitHub Actions 定时任务有时延迟，缓存可能已过时数小时。
> **每次扫描前必须主动触发一次更新，等到价格刷新后才能出报告。**

**触发方式**：用 `mcp__github__push_files` 推一个 trigger 文件到 main 分支：
```json
owner: "zhenyuanhuang358"
repo:  "work"
branch: "main"
message: "trigger: refresh stock prices for options scan [当前日期]"
files: [{"path": "price_fetch_trigger.txt", "content": "[当前日期时间] triggered by options scan pre-fetch"}]
```

推送后，**使用 Bash 轮询等待**，直到 `stock_prices.json` 的 `updated_at` 超过今日零点：
```bash
until curl -sf "https://raw.githubusercontent.com/zhenyuanhuang358/work/main/stock_prices.json" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d['updated_at'] > '[当前日期]T00:00:00' else 1)" \
  2>/dev/null; do sleep 5; done && echo "prices updated"
```

> 🔴 **硬性规则：不等到 `prices updated` 出现，绝不出报告。**
> - 不设超时时间——等多久都要等
> - 不用缓存数据降级
> - 不先出"临时版"再更新
> - 只出一份报告，价格确认新鲜后一次性完成

**等待期间并行执行第二轨**（IV / 异常流 / 财报 / 宏观 WebSearch 不依赖价格，可同步进行）。

---

### 第一轨：GitHub 缓存文件 — 实时价格（触发更新后再读）

> ⚠️ 价格数据**只用这个文件**，不用 WebSearch 代替。WebSearch 价格有延迟且容易出错。

**读取方式**（WebFetch 调用）：
```
URL: https://raw.githubusercontent.com/zhenyuanhuang358/work/main/stock_prices.json
```

**文件结构**（含新增的 VIX + 10年期国债收益率）：
```json
{
  "updated_at": "2026-05-22T09:27:37Z",
  "vix": 18.5,
  "treasury_10y": 4.38,
  "prices": {
    "SPY":  { "price": 733.73, "changePct": -0.67, "high": 737.65, "low": 731.53 },
    "QQQ":  { "price": 701.53, "changePct": -0.82, ... },
    "NVDA": { "price": 220.61, ... },
    "PLTR": { "price": 135.26, ... },
    "TSLA": { "price": 404.11, ... },
    "AAPL": { "price": 298.97, ... },
    "AMD":  { "price": 414.05, ... },
    "IWM":  { "price": 273.00, ... },
    "GLD":  { "price": 411.50, ... }
  }
}
```

`vix` 直接填入报告头部；`treasury_10y` 用于判断利率环境与 risk-on/off 背景。
**如果文件读取失败**（WebFetch 报错）：在报告顶部注明「价格来自 WebSearch，需在平台二次确认」，然后 WebSearch 兜底。

---

### 第二轨：WebSearch — IV / 异常流 / 财报 / 宏观（Finnhub 不覆盖的数据）

**可在等待第零轨价格更新期间并行执行：**

1. `[候选标的] IV rank site:marketchameleon.com` — IV Rank（最关键，每个标的必查，优先 marketchameleon）
2. `unusual options activity today` — 异常期权流
3. `earnings this week [日期]` — 本周财报日历
4. `宏观 美联储 经济数据 本周` — 宏观风险

---

# 《今日美股期权机会》

**日期**：[YYYY-MM-DD]
**大盘**：SPY $[X]（[+/-]%）| QQQ $[X]（[+/-]%）
**VIX**：[stock_prices.json.vix]（[<15低/15-25中/25-35高/>35极高]，[解读一句话]）
**10年期国债**：[stock_prices.json.treasury_10y]%（[利率环境一句话]）
**市场情绪**：[Risk-on / Risk-off / 中性]

---

## 一、收权利金机会（稳定收益）

> 目标：高 IV Rank 标的，卖 CSP 或 CC，稳定收取时间价值

### 机会 1：[标的代码]
- **策略**：[CSP / CC / Wheel]
- **理由**：IV Rank [X]，支撑位 $[X] 明确，[简短原因]
- **参考执行**：卖 $[X] Put / Call，到期 [日期]，权利金约 $[X]
- **最大亏损**：$[X]（占账户 [%]）
- **PoP**：约 [%]
- **注意**：[风险提示]

### 机会 2：[标的代码]
[同上格式]

---

## 二、高胜率信用价差

> 目标：IV Rank 中高，标的有明确方向偏好，做有限风险价差

### 机会 1：[标的代码]
- **策略**：[Bull Put Spread / Bear Call Spread / Iron Condor]
- **理由**：[简短分析]
- **参考执行**：[具体行权价组合]，到期 [日期]，净权利金 $[X]
- **最大亏损**：$[X]（占账户 [%]）
- **最大盈利**：$[X] | **R/R**：[X]:1
- **PoP**：约 [%]
- **注意**：[风险提示]

---

## 三、财报波动机会

> 今日/本周财报标的，评估是否存在 IV 错误定价机会

| 标的 | 财报日期 | IV Rank | Expected Move | 机会类型 | 推荐？ |
|------|---------|---------|--------------|---------|-------|
| [代码] | [日期] | [X] | ±[%] | [Long Straddle/价差] | [是/否/观察] |

**详细分析**（仅推荐标的）：
- 策略：[具体执行]
- 逻辑：[为什么 IV 错误定价 / 为什么赔率有优势]
- IV Crush 风险：[高/中/低，说明原因]
- 最大亏损：$[X]（有限风险）

---

## 四、异常期权流机会

> 今日大额扫单、异常成交量、机构博弈信号

| 标的 | 异常信号 | 方向 | 规模 | 可跟随？ | 跟随方式 |
|------|---------|------|------|---------|---------|
| [代码] | [大额买 Call/Put / IV 异动] | [看涨/看跌] | [成交量/金额] | [是/否] | [有限风险跟随策略] |

**注意**：异常期权流是信号，不是信仰。必须配合技术面和 IV 评估。不推荐直接买 OTM 彩票单。

---

## 今日风险提示

- [宏观/地缘/经济数据等影响当天持仓的主要风险]
- [VIX 是否异常，是否需要降低卖方仓位]

---

## 账户状态提醒

| 项目 | 当前 | 上限 |
|------|------|------|
| 本日新增敞口 | $[X] | — |
| 总风险敞口估算 | $[X] | $2,550 |
| 现金/保证金充裕度 | [充裕/注意/偏紧] | — |

*若总敞口接近 $2,550，本日优先观察，不加新仓。*
