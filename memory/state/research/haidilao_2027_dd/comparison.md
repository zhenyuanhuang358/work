# 对比：旧梅林 Mode B vs Decision Mode（2026-11-24 首测）

| 维度 | 旧梅林（haidilao_h1_2026_review） | Decision Mode（haidilao_2027_dd） |
|---|---|---|
| 任务形态 | 5 题（研究型） | 6 题（投资尽调，服务一个决策：是否给 2027 溢价） |
| 假设 | 无显式假设 | 5 条可证伪假设（falsifier/evidence_needed/status），H2 部分证伪、H3 证伪 |
| 证据 | 25 条 evidence，无 claim_id/source_type | 20 条 claim（claim_id/hypothesis_id/source_type/unit/period/file，q 映射 Q1–Q6） |
| 计算 | 报告内嵌数字；Critic R2 抓到成本桥错 | `calc.py → calc.json`：门店净变化、利润率、七项成本、其他收益、门店情景、大排档情景 |
| 冲突 | 无冲突表 | `conflicts.json` 5 条：同店/门店口径 resolved；大排档回收期、2027 目标 blind_spot |
| 红队 | 仅交付前 Critic | `redteam.md`：5 条反向检索 + 5 条反证（含看多侧）+ 证伪复核；H2 部分证伪触发回环 2（reframes=1） |
| 门禁 | 无 | `tools/dr_state.py` G0–G4 全过（假设/覆盖/冲突/红队/交付） |
| 交付 | 报告 | 报告 + `decision_memo.md`（3 选项 + falsifier + 盲区影响）+ 三层切分（硬事实/推演/盲区） |
| 机械检查 | Critic R2 抓到成本桥/页码 | `merlin_check` 0 FAIL、`report_check --record` 0 FAIL |
| Critic | R1 CONDITIONAL → R2 CONDITIONAL（用户接受） | R1 CONDITIONAL（C7 引文/H3/成本桥/口径）→ 修 → R2 **REWRITE**（跨文件传播不一致：冲突表旧数、H3 两套状态、条件漏客单）→ 已修 P0/P1，未复评（两轮规则停） |
| 增量成本 | — | +约 30–40% 时间（假设/冲突/红队/calc/门禁），换来可证伪、可回溯、可审计 |

## 首测结论
- **优势已验证**：Decision Mode 产出「决策选项 + falsifier + 盲区影响」，旧 Mode B 只给研究结论；冲突表当场抓出「大排档回收期 vs 单店收入」口径不闭合（旧版不会发现）；calc.json 让数字可复算。
- **暴露的缺口**：`dr_state` 门禁只查文件存在/字段完整，**不查跨文件数字一致性**——Critic R2 正是靠人工抽原文抓到 6 处旧数残留。下一版必须加「一致性门禁」：report/conflicts/memo/hypotheses 的同一指标必须同值。
- **当前状态**：v0.1 可跑、可审计，但 Critic R2 判 REWRITE，**不能作为客户交付件**；作为「测试+对比」已完成。
