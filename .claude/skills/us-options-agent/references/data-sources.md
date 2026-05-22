# 数据来源索引

每次分析前，按需从以下来源获取实时数据。标注可靠性和免费程度。

---

## ⭐ Finnhub 实时行情 API（核心价格来源）

**Base URL**：`https://finnhub.io/api/v1`
**认证**：Query 参数 `token={FINNHUB_TOKEN}`（环境变量 `FINNHUB_TOKEN`）
**免费版限额**：60次/分钟，美股实时报价无延迟，无 IP 白名单限制

| 数据类型 | Endpoint | 示例 | 说明 |
|---------|---------|------|------|
| 实时股价 | `GET /quote` | `?symbol=AAPL&token=...` | `c`=当前价，`d`=涨跌额，`dp`=涨跌幅% |
| 公司概况 | `GET /stock/profile2` | `?symbol=AAPL&token=...` | 市值、行业 |
| 财报日历 | `GET /calendar/earnings` | `?from=2026-05-20&to=2026-05-27&token=...` | 本周财报安排 |

**响应字段**（`/quote`）：`c`=当前价 · `d`=涨跌额 · `dp`=涨跌幅% · `h`/`l`=当日高低 · `pc`=昨收

**在本 skill 中的用途**：
- 所有标的实时价格通过 GitHub Action 每5分钟自动抓取并缓存到：
  `https://raw.githubusercontent.com/zhenyuanhuang358/work/main/stock_prices.json`
- 日扫报告直接 WebFetch 读取该文件，无需 token，无沙箱限制
- `earner.py` 已集成：`--price` 未提供时直接调用 Finnhub（需本地配置 `FINNHUB_TOKEN`）

**覆盖标的**：SPY · QQQ · NVDA · PLTR · TSLA · AAPL · AMD · IWM · GLD（每5分钟更新）
**新增标的**：在 `.github/workflows/fetch-prices.yml` 的 `tickers` 列表中添加即可。

**搜索方式（文件读取失败时）**：继续使用 WebSearch，格式不变。

---

## IV Rank / IV Percentile（最重要）

**来源优先级（按序使用，前一个失败再用下一个）**：

| 优先级 | 来源 | 搜索方式 | 免费？ | 说明 |
|--------|------|---------|-------|------|
| **#1 首选** | Market Chameleon | `[代码] IV rank site:marketchameleon.com` | 免费基础版 | IV Rank、IV Percentile、历史IV走势图，数据最全，**每次必先查这里** |
| **#2 备选** | Barchart | `[代码] implied volatility barchart` | 免费 | IV Rank 在期权页面右侧；若 marketchameleon 无结果用此补充 |
| **#3 验证** | Finviz | `[代码] IV finviz options` | 免费基础 | 与 marketchameleon 数值差距 >10% 时，取两者均值并注明差异 |
| **#4 精确值** | TastyTrade / ThinkorSwim | 经纪商平台 | 需开户 | 执行前在平台二次确认，特别是 Iron Condor 等精确度要求高的策略 |

> **冲突处理**：若两个来源 IV Rank 相差 >10（如 24% vs 51%），两个数值都列出，
> 以 marketchameleon 为准，并注明「来源有分歧，执行前在平台确认」。
> 不得取平均或选高值来降低风险阈值。

**搜索模板（每次必查，逐个标的执行）**：
```
[代码] IV rank site:marketchameleon.com
```

---

## 期权链 / Greeks

| 来源 | 地址 | 免费？ | 说明 |
|------|------|-------|------|
| Barchart | barchart.com | 免费 | 期权链完整，有 OI、Volume、Greeks 估算 |
| Yahoo Finance | finance.yahoo.com/quote/[代码]/options | 免费 | 基础期权链，无 IV Rank |
| CBOE | cboe.com | 免费 | 官方数据，偏专业 |
| Optionistics | optionistics.com | 免费基础 | Greeks 计算工具 |

**Greeks 说明**：
- 本 skill 给出的 Greeks 为基于 Black-Scholes 的估算值
- 实时精确 Greeks 需从经纪商平台（TastyTrade/ThinkorSwim）获取
- **Delta 估算规则**：ATM ≈ ±0.50，每一个标准差外 ≈ ±0.16，两个标准差外 ≈ ±0.05

---

## 异常期权流 / 大额扫单

| 来源 | 地址 | 免费？ | 说明 |
|------|------|-------|------|
| Unusual Whales | unusualwhales.com | 部分免费 | 异常期权流最权威，免费版有延迟 |
| Barchart Unusual Activity | barchart.com/options/unusual-activity | 免费 | 每日异常成交量期权列表 |
| Finviz | finviz.com | 免费基础 | 期权成交量异常筛选 |
| Reddit r/options | reddit.com/r/options | 免费 | 社区发现异常流，有噪音 |

**搜索方式**：
```
unusual options activity today site:unusualwhales.com
[代码] unusual options flow today
```

---

## VIX 与宏观数据

| 数据 | 主要来源 | 备注 |
|------|---------|------|
| **VIX 实时** | `stock_prices.json` 顶层 `vix` 字段 | GitHub Action 与股价同步更新，无需额外搜索 |
| **10年期国债收益率** | `stock_prices.json` 顶层 `treasury_10y` 字段 | 同上，^TNX via yfinance |
| 财报日历 | Earnings Whispers | `earnings calendar this week` |
| 经济数据日历 | Investing.com | `economic calendar this week` |
| 美联储动态 | Fed官网 / CNBC | `fed meeting date next` |
| Expected Move | Market Chameleon | `[代码] expected move this week` |

**VIX 解读参考**：
| VIX 区间 | 市场状态 | 卖方策略建议 |
|---------|---------|------------|
| < 15 | 低波动、乐观 | IV 偏低，权利金少，谨慎开新仓 |
| 15–25 | 正常 | 正常操作 |
| 25–35 | 高波动、恐慌 | IV 偏高利好卖方，但风险也大，缩减仓位 |
| > 35 | 极端恐慌 | 触发极端市场协议，见 `extreme-market-protocol.md` |

---

## 标的筛选（寻找高 IV Rank 机会）

**每日扫描推荐流程**：
1. 打开 Barchart：`barchart.com/options/high-implied-volatility` → 筛选 IV Rank > 30
2. 打开 Market Chameleon：搜索「high IV rank stocks today」
3. 检查 VIX 水平，决定是否适合卖方

**常见高流动性期权标的（优先考虑范围）**：

| 类型 | 标的 | 特点 |
|------|------|------|
| 宽基 ETF | SPY、QQQ、IWM | 流动性最好，适合散户 |
| 行业 ETF | XLF、XLE、GLD、SLV | 波动较低，适合 Wheel |
| 大盘股 | AAPL、TSLA、NVDA、AMZN | 高流动性，IV 波动大 |
| 波动率产品 | VXX、UVXY | 高风险，仅事件驱动用 |

**$8,500 账户特别提醒**：
- 优先选择股价 < $50 的标的（保证金友好）
- 或直接用 ETF（SPY 期权也有 mini 版 SPDR）
- 避免股价 > $200 的标的做 CSP，保证金会占账户比例过大

---

## 数据获取的局限性说明

本 skill 通过 WebSearch 抓取公开页面数据，以下情况数据可能不准确：

| 情况 | 说明 | 解决方式 |
|------|------|---------|
| IV Rank 实时值 | 搜索结果可能有 15-20 分钟延迟 | 以经纪商平台数据为准 |
| 期权链报价 | 非交易时段数据为收盘价 | 开盘后确认成交价 |
| Greeks 精确值 | 为估算，非实时计算 | 下单前在经纪商平台确认 |
| 异常期权流 | 免费来源有延迟 | 重要机会付费验证 |

**原则：本 skill 提供分析框架和方向判断，具体执行参数必须在经纪商平台二次确认再下单。**
