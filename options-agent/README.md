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
| vol_spread | 纳坦伯格/麦克米伦波动率派 | IV≥35% 时卖 put 并买最近一档更低行权价 put，风险限定；看净权利金/最大亏损 |
| taleb_hedge | 塔勒布尾部对冲 | 买 ask≤$0.10、delta 在 -0.12~-0.02、缓冲 5%~25% 的远价外 put，定位是保险 |
| thorp_ev | 索普期望值（叠加层） | 假设真实波动率 = IV×0.85 重算公允价，EV=bid-公允价；EV<-0.05/股的卖方候选一票否决 |

## 风控（任何模块之上）

- bid≤0、买卖倒挂：无法反解 IV，直接不出数字（与既有 option_quote.py 相同）
- 买卖价差 > 中间价 50%：流动性否决
- `--live` 模式下报价超过 30 分钟：整只标的否决；回放模式只在报告头标注
- IV 一律由中间价反解，不用数据源自带 IV；卖方收入按 bid 计

## 口径与局限

- 定价时刻 = 每只标的的 `quote_time_utc`（CBOE 延迟约 15 分钟），到期按美东 16:00
- IV Rank/Percentile 需要历史 IV 序列，v1 没有引入，先用 IV 绝对值 + z 值；
  接入历史链数据后应把 vol_spread 的门槛换成 IV Rank
- 当前关注清单只有 put（`options_watch.json` 的 `right: "P"`），call 侧策略
  （如备兑开仓）需要先把抓取扩到双边
- 信号只用于研究筛选，下单前必须以交易平台实时报价复核；不构成投资建议

## 示例结果（2026-11-02 期权链回放）

30 条信号（CSP 18 / 尾部对冲 7 / 信用价差 5），57 条被风控否决。
评分靠前包括 PLTR 152.5P 现金担保卖 put（IV 151%、z 1.05）等；
注意 PLTR、AMD 当周 IV 超过 100%，与财报临近有关，高 IV 既是权利金
来源也是跳空风险来源，报告里已如实标注 IV 数值供人工复核。
