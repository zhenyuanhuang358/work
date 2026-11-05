# 美股期权智能体 v1（研究信号版）

只筛选、只提示、不下单。输入与 GitHub 仓库 `zhenyuanhuang358/work` 的
`fetch-options` 工作流产出的 `options_chain.json` 完全同格式，可直接接现有
数据管道（CBOE 延迟报价主源、yfinance 兜底）。

## 运行

```bash
# 在仓库根目录运行（options-agent/ 为本目录，期权链接在仓库根）：
python3 options-agent/agent.py --file options_chain.json --out options-agent/out/
# 实盘时段（报价超 30 分钟整只否决）+ 购买力标注：
python3 options-agent/agent.py --file options_chain.json --out options-agent/out/ --live --bp 5000
```

输出 `out/signals.json` 和 `out/report.md`（按分数排序的信号 + 被否决清单）。

## 策略模块

| 模块 | 思想来源 | 规则要点 |
|---|---|---|
| buffett_csp | 巴菲特式现金担保卖 put | z≥1.0、价外概率≥80%、OI≥100，按现金担保年化打分，标注 Reg-T 保证金 |
| short_call | 卖 call（2026-11-05 用户加入） | 与卖 put 镜像：行权价高于现价、z≥1.0、价外概率≥80%、OI≥100；裸卖 call 上行风险无限，同受全部风控与保证金硬否决 |
| thorp_ev | 索普期望值（叠加层） | 假设真实波动率 = IV×0.85 重算公允价，EV=bid-公允价；EV<-0.05/股的卖方候选一票否决 |

2026-11-03 按用户决定收窄：只做单腿卖出（券商不支持组合单），
原 vol_spread（信用价差）与 taleb_hedge（买 put 尾部对冲）两个模块已移除。
2026-11-05 起关注清单改为双边（`options_watch.json` 的 `right: "PC"`），
put/call 在 rows 的 right 字段区分，必须分开定价，不得混用。

## 事件日历（events.json）

美国宏观事件日历（非农、CPI、PPI、FOMC、大选、PCE），日期按 BLS
官方发布日程与美联储 FOMC 日历核对维护。扫描时自动比对每条信号的
持有期（扫描日到到期日）：报告头列出窗口内全部事件，每条跨事件的
信号单独标注「事件窗口」。按 2026-11-03 用户决定：只标注提醒，
不否决、不改分数。日历需每月核对官方日程后更新 events.json。

## 财报日历（earnings.json）

自选股下一次财报日期（美东，含盘前/盘后）。按 2026-11-04 用户
决定：持有期跨财报日的信号直接否决，移入报告否决区并注明原因
（与宏观事件的「只标注」不同）。SLV、XLE 为 ETF 无财报。每个
财报季结束后需更新 earnings.json 中的下一次日期。

## 风控（任何模块之上）

- bid≤0、买卖倒挂：无法反解 IV，直接不出数字（与既有 option_quote.py 相同）
- 买卖价差 > 中间价 50%：流动性否决
- `--live` 模式下报价超过 30 分钟：整只标的否决；回放模式只在报告头标注
- IV 一律由中间价反解，不用数据源自带 IV；卖方收入按 bid 计

## 口径与局限

- 定价时刻 = 每只标的的 `quote_time_utc`（CBOE 延迟约 15 分钟），到期按美东 16:00
- IV Rank/Percentile 需要历史 IV 序列，v1 没有引入，先用 IV 绝对值 + z 值
- 卖 call 为裸卖：上行风险理论无限，且保证金随标的上涨膨胀，实盘
  必须配合 2 倍权利金止损与保证金 60% 硬否决（见 account.json）
- 信号只用于研究筛选，下单前必须以交易平台实时报价复核；不构成投资建议

## 示例结果（2026-11-02 期权链回放）

收窄后回放：30 条信号（全部为现金担保卖 put，上限 30 条），57 条被风控否决。
评分靠前包括 PLTR 152.5P 现金担保卖 put（IV 151%、z 1.05）等；
注意 PLTR、AMD 当周 IV 超过 100%，与财报临近有关，高 IV 既是权利金
来源也是跳空风险来源，报告里已如实标注 IV 数值供人工复核。
