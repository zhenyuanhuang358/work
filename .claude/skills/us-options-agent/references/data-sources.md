# 数据来源索引

每次分析前，按需从以下来源获取实时数据。标注可靠性和免费程度。

---

## IV Rank / IV Percentile（最重要）

| 来源 | 地址 | 免费？ | 数据质量 | 说明 |
|------|------|-------|---------|------|
| Market Chameleon | marketchameleon.com | 免费基础版 | ★★★★★ | IV Rank、IV Percentile、历史IV图，最推荐 |
| Barchart | barchart.com/stocks/quotes/[代码]/options | 免费 | ★★★★ | IV Rank 在期权页面右侧，有 Put/Call 比率 |
| TastyTrade | tastytrade.com | 需开户（免费） | ★★★★★ | 开户后有完整 IV Rank 工具 |
| ThinkorSwim | TD Ameritrade 平台 | 需开户（免费） | ★★★★★ | thinkScript 可扫描 IV Rank > N 的标的 |

**搜索方式（无账户时）**：
```
[代码] IV rank site:marketchameleon.com
[代码] implied volatility rank today
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

| 数据 | 来源 | 搜索关键词 |
|------|------|-----------|
| VIX 实时 | CBOE / Yahoo Finance | `VIX 今日 数值` |
| 财报日历 | Earnings Whispers | `earnings calendar this week` |
| 经济数据日历 | Investing.com | `economic calendar this week` |
| 美联储动态 | Fed官网 / CNBC | `fed meeting date next` |
| Expected Move | Market Chameleon / TastyTrade | `[代码] expected move this week` |

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
