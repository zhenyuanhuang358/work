# Decision Mode 统一入口 · 2026-11-24（DSH）

状态：完成
来源：用户 2026-11-24「统一」「同意」

## 统一了什么
1. **路由**：`CLAUDE.md` 报告路由行改为「客户提纲/访谈准备/逐条回答/投资尽调准备 → Merlin（决策类=Decision Mode：dr_state 门禁 + 决策备忘）」。
2. **COO 调研流水线**：分型表新增「客户调研要支撑一个决策（尽调/立项/访谈决策）→ Merlin Decision Mode」；步骤 3 改为决策类先 `dr_state init`，G2 加 `dr_consistency` 一致性检查。
3. **Merlin hub**：判据表加 Decision Mode 行；通用流程第 0 步「决策类先分型」；Spoke 表已含 decision-mode。
4. **decision-mode.md**：写明统一入口（决策类默认走本模式，不再走普通 Mode B）。
5. **工具**：`dr_consistency.py` 与 `dr_state.py` 为一个入口（synthesize 门自动跑一致性）；`facts.json` 单一事实表。
6. **测试**：新增 `tests/test_dr_tools.py`（一致性 pass/stale/missing + frame 门 falsifier）；全量 **115 项通过**。

## 当前状态
- 报告 v0.2：R3 CONDITIONAL（仅 2 项 P1：增量区间已改 −2 至 +5 亿元、40–90 家标假设；PDF CSS 已放宽），机械+一致性 0 FAIL；未再复评（停止轮次）。
- 下一步：① 终审拿 PASS 或 ② 用真实客户提纲再跑一单。
