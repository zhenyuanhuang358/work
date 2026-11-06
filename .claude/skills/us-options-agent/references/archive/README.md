# 归档（2026-11-06，用户定「移到归档文件夹」）

这些文件与现行规则冲突，**不再被 SKILL.md 引用，Agent 不要按它们执行**。保留只为追溯当时的设计与事故背景。

| 文件 | 为什么归档 | 现行替代 |
|---|---|---|
| SKILL_2026-11-05.md | 主文件旧版：账户 8,500–9,000、策略分配含 20% 信用价差、「禁止裸卖 call」、IV Rank > 30、「需用户触发扫描」 | 新 SKILL.md（工作地图 + 验收标准） |
| daily-scan-template.md | 旧扫描流程：WebSearch 抓 IV Rank、推信用价差、手工推触发文件 | `tools/scan.py` + `coo/references/pipeline-options.md` |
| strategy-catalog.md | 70/20/10 策略分配、价差 / 铁鹰（盈立无组合单） | `references/position-discipline.md` 第 1–19 条 |
| data-sources.md | IV Rank 网页搜索、Barchart 筛选、异常期权流 | SKILL.md「数据产物」表 |
| analysis-template.md | 单标的报告模板，以 IV Rank 与价差为核心 | `option_quote.py --ticker X` + `gap_stress.py` |
