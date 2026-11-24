# Decision Mode 首测 · 海底捞 2027 开店/副品牌（客户尽调）· 2026-11-24

状态：完成（v0.2；Critic R1 CONDITIONAL→R2 REWRITE→R3 CONDITIONAL；R3 的 2 项 P1 已修，机械+一致性 0 FAIL，未再复评；作为测试与对比交付）
来源：用户 2026-11-24「先测试。对比跟之前有什么不同和优势」

## 产物
- 报告：reports/haidilao_2027_dd_Research_Report.html + PDF
- 任务目录 memory/state/research/haidilao_2027_dd/：state.json、hypotheses.json（5 假设）、evidence.jsonl（20 claim）、conflicts.json（5）、redteam.md、calc.py/calc.json、decision_memo.md、comparison.md
- M0：memory/state/research/haidilao_2027_dd_q/outline.json
- 新工具：tools/dr_state.py；新 spoke：.claude/skills/merlin/references/decision-mode.md

## 门禁与检查
- G0 frame / G1 source / G2 triangulate / G3 redteam / G4 synthesize：全过
- merlin_check M0–M10 0 FAIL；report_check --record 0 FAIL（修完后）
- loops：reframes=1（H3 客单证伪触发回环 2）

## Critic
- R1 CONDITIONAL：C7 引文越界（2027 高双位数无原文）、H3 客单证伪漏判、Q4 −0.74pct 归因错、Q1 区间未入 calc、Q3 口径/区间错、挂名/字段缺失等
- R2 REWRITE：跨文件传播不一致（冲突表旧数、H3 两套状态、条件漏客单、0.74 残留、增量口径）——**根因是 dr_state 不查跨文件一致性**
- v0.2：新增 `tools/dr_consistency.py` + facts.json 一致性门禁（抓出 8 处跨文件旧数）；修 R2 P0/P1；送 R3 得 CONDITIONAL（仅剩：增量区间未配对、40–90 无依据、PDF 版式）；已修「增量 −2 至 +5 亿元（40–90 为假设、净增 −20 至 +30 家）」与 print CSS，机械/一致性 0 FAIL；未再复评

## 结论
Decision Mode v0.1 流程与产物成立，但未过 Critic；下一步补「跨文件一致性门禁」+ 修 P1 后再送审。对比见 comparison.md。
