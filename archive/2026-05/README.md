# 归档（2026-11-11 项目体检）

这里的文件只是挪了位置，没有删除。归档标准：全仓库（skill、工具、工作流、测试、文档）没有任何地方引用，且 2026-06 之后没有改动。

| 内容 | 说明 |
|---|---|
| `ira_chapter2–7_workflow.py`、`output_chapter2–6.md`、`input.json`、`intermediates*` | 5 月的一组章节生成脚本及其输入输出，自成一体，外部无引用 |
| `run_amd.py`、`test_agent_real.py` | 5 月的一次性脚本，无引用 |
| `audit_skills.py`（原 `scripts/`） | 9 月的 skill 审计脚本，已被 `tools/self_check.py` 取代，无引用 |
| `gen_followup_docx.py`（原 `scripts/`） | 6 月的一次性文档生成脚本，无引用 |

要恢复：`git mv archive/2026-05/<文件> <原位置>`。
