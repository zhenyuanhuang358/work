# Merlin 验证单：海底捞 2026H1 后五问 · 2026-11-24（DSH）

状态：完成（Critic 两轮 CONDITIONAL；按规则未送第三轮，交用户定）
来源：用户 2026-11-24「都去做吧」——单轨制收敛 + 用新提纲验证 Merlin 新流程

## 步骤
- [x] M0：`tools/merlin_outline.py init/check` → `memory/state/research/haidilao_h1_2026_review/`（5 题，intent/decision/答案形态/数据需求齐全）
- [x] Scout：2026 中期报告（本地 PDF 90 页，PyMuPDF 抽取）、2025 业绩（澎湃/东财）、证券之星 MD&A 转载、新华财经、商业时报、观点网、每经、界面、CCFA 2022 业绩稿、中泰 2021、新浪 2019；`evidence.jsonl` 25 条
- [x] 报告：`reports/haidilao_h1_2026_review_Research_Report.html` + PDF；5 题结论-依据-含义-置信；收入结构 SVG；来源索引 11 条；数据截止/页码口径/未核实项
- [x] 机械：`merlin_check`（M0–M10）无 FAIL；`report_check --record` 无 FAIL
- [x] Critic：R1 CONDITIONAL（挂名源、Q5 成本桥漏折旧、页码、净 −8/−14、分部缺 0.1%、207→183）→ 修 → R2 CONDITIONAL（Q5 成本桥符号/量级错、页码漂移、32/14 口径、PDF 分页）→ 已修 P0/P1（成本桥改为「七项成本 +0.36pct、其他收益及亏损 −0.74pct、合计 −0.38pct」；页码改印刷页；32/14 标基数；PDF 分页）→ **未送第三轮**
- [x] G5/G6：台账 + 提交推送

## 验收情况
- 机械检查：0 FAIL（自动验证通过）
- Critic R2：五维 3/4/2.5/3.5/2.5，专业性与可核性 <3 → CONDITIONAL（AI 评估未通过）
- 用户验收：待定

## 待用户决定
① 接受当前版本（不推荐：R2 指出 Q5 成本桥曾算错，虽已修但未复评）；② 授权第三轮 Critic；③ 换会话重做。
