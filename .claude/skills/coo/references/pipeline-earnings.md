# 流水线 · 财报分析

<!-- skills: earner, critic -->

关卡：G2 → G3 → 交付 → G4 → G5 → G6。G1 只在标的是 6862 / 6831 时适用。

## 步骤

| # | 步骤 | 做什么 | 交接 |
|---|---|---|---|
| 1 | 继承 | `grep -n -A30 "<ticker 或公司名>" memory/state/research-ledger.md`；predictions.md 里该标的还有没有待验项 | 上次结论；**上次的预测这次财报能不能记分**——能就先记分再分析 |
| 2 | 生产 | `earner` 完整跑：Step 0「现价已经假设了什么」→ 五维度 → 14 节 HTML（CLAUDE.md 模板） | `reports/{slug}_Copilot_Report.html` |
| 3 | G2 Critic | 子 agent，报告类型写「Earner」（D5 查 14 节与 4 张必需图表） | 裁定 |
| 4 | G3 PDF | `node tools/render_pdf.js <html>` | — |
| 5 | 交付 | `SendUserFile` HTML + PDF；一行写评级 + 三情景目标价 + Critic 裁定 | — |
| 6 | G4 | **三情景必须登记**：熊市价不被击穿、基准价、牛市价兑现，各一行，验证时点 12 个月、收盘口径；下季营收 / 毛利率指引各一行（公告值口径）。牛市情景成立概率 <50% → 把握档「低」（MU 先例） | — |
| 7 | G5 | research-ledger 追加 | — |
| 8 | G6 | 提交推送 | — |

## 交接坑

- 财报股必须有盘后价（profile 1.1c）；现价从 `stock_prices.json` 读，港股 / 缓存外标的在报告注明来源。
- 同一标的若在期权持仓或候选里，交付时提醒用户「本报告影响 <持仓>」，但不在本流水线给期权动作——转期权流水线。
- 上一次的 SNDK 目标价 8 个交易日被打穿（倍数前提失效）：Step 0 必须回答「这个倍数的前提今天还成立吗」。
