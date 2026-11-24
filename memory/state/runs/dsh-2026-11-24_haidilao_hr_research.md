# 海底捞 HR/组织/门店运营调研 · 2026-11-24（DSH）

状态：完成（Critic 两轮 CONDITIONAL，按规则交用户定是否第三轮）
来源：用户 2026-11-24「了解海底捞人力资源管理体系、员工激励、家族制和抱团小组制度、组织架构演变、大区片区管理、门店运营等」
路由：Merlin 模式 B（调研报告线）

## 步骤
- [x] 1 继承：research-ledger 海底捞条目（2026-07 运营管理体系、2026H1 提纲、AI 导购）；不重复已核事实
- [x] 2 M0 输入契约：`memory/state/research/haidilao_hr_2026/outline_map.md` + `outline.json`（6 题：原问/真实想问/决策用途/答案形态/数据需求）
- [x] 3 Scout：Actions 抓原文 20+ 页——2018 招股书（本地 PyMuPDF 可读）、2025 ESG/年报、2026 中期报告（本地下载 90 页）、2022 业绩稿（CCFA）、中泰 2021、东北证券 2026、界面/蓝鲸/36氪/每经/观点/澎湃/新华财经/证券之星/商业时报/新浪 2019、中国市场监管报（四色卡）
- [x] 4 证据底账：`evidence.jsonl` 21 条（Q、claim、来源 URL、pages/文件、原文引文）
- [x] 5 生成：`reports/haidilao_hr_org_2026_Research_Report.html`（6 题，结论-依据-含义-置信；2 SVG；Q4 演变表；Q5 职责矩阵；来源索引 18 条）
- [x] 6 G3 PDF：Chrome headless 渲染（`tools/render_pdf.js` 缺 playwright，沿用 Chrome 回退）
- [x] 7 G1/机械：`report_check.py --record` 无 FAIL；`merlin_check.py --outline` 无 FAIL（M8 已按 rubric 收紧）
- [x] 8 G2 Critic：R1 CONDITIONAL（6 项）→ 修 → R2 CONDITIONAL（H1 单位错/H2 四色卡/H3 挂名/M1-M5）→ 修 → **未复评**（两轮规则）
- [x] 9 G5：research-ledger 追加
- [x] 10 G6：提交推送（见 commit）

## 关卡
- [x] G1 合规：仅公开信息；无 6862 未公开数据
- [x] G2 Critic：两轮 CONDITIONAL（已修，未复评；按规则停）
- [x] G3 PDF
- [x] G4 预测：不登记（无门槛+时点）
- [x] G5 台账
- [x] G6 推送

## 待用户决定
- 报告已按 R1/R2 全部修正、机械检查无 FAIL，但 Critic 两轮未 PASS：① 送第三轮 Critic；② 用户直接看；③ 换会话重做。
