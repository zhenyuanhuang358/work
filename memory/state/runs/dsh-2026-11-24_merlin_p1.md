# Merlin P1 改造 · 2026-11-24（DSH）

状态：完成
来源：用户 2026-11-24「继续 P1」（承接梅林三投诉整改 P0）

## 目标（P1 四项）
1. 拆 hub + spokes（hub ≤200 行）
2. 修路由判据（Merlin vs restaurant-research）
3. 把 outline_map / evidence 前置工具化
4. 冻结 2 份好样例 + 1 份失败样例做回归

## 改动
- **Spokes**：`.claude/skills/merlin/references/` 新增 `mode-a.md`、`mode-b.md`、`evidence-and-sources.md`、`output-spec.md`、`critic-checklist.md`；`quality-rubric.md` 保留。
- **Hub**：`SKILL.md` 572→79 行；只留身份/判据边界/模式判断/通用流程/M0 硬门/红线/Spoke 表/精简自检/示例。判据表明确「有客户原问+逐条回答才是 Merlin；自己出题的行业调研→restaurant-research；多章≥20页→huashu-report」。
- **工具**：
  - 新增 `tools/merlin_outline.py`：`init` 生成 outline.json/outline_map.md；`check` 校验每题 intent/decision/answer_form/data_need 齐全（拒占位符「待补」），退出码 0/1。
  - `tools/merlin_check.py` 新增 **M10 证据底账**（每 Q ≥2 条 evidence、每条有 url+quote），CLI `--evidence`；M8 已按 rubric 收紧为 FAIL（域名≥2×题数、每 Q≥1 一手）。
- **回归样例**：`tests/fixtures/merlin/good/`（已交付的海底捞 HR 报告 + outline + evidence）、`bad/`（旧如鮨报告，已知来源/交付失败）；`tests/test_merlin_check.py` 增 3 项、`tests/test_merlin_outline.py` 新增 3 项。
- **测试**：全量 110 项通过；`skill_index --check` 最新；hub 79 行（≤200）。

## 残余
- `restaurant-research-skill` 的触发词仍含「客户提纲/按提纲调研」，与 Merlin 重叠；该文件属 Claude 侧共享文件，本次未改（隔离协议），建议合并时同步一行判据。
- 改造有效性仍待**下一单** Critic PASS 验证（本单两轮 CONDITIONAL 后用户接受）。

## 验收
- [x] hub ≤200 行、Spoke 表场景全覆盖
- [x] M0/M10 工具可跑、缺料会失败
- [x] 好样例 0 FAIL、坏样例稳定 FAIL
- [x] 全量测试 110 通过
