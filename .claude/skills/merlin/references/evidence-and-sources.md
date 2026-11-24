# Merlin · 证据与来源纪律

> 这份文件回答一个问题：**报告里每个数字/判断，凭什么能核？**
> 用户投诉「搜索面窄、不够专业」的根因是来源层裸奔；本文件把来源变成可检查的产物。

## 1. 来源矩阵（每 Q 至少两类）

| 类别 | 例 | 要求 |
|---|---|---|
| 一手 | 招股书、年报/中报、公告、ESG 报告、官网、监管文件、访谈原文 | **每 Q ≥1 条** |
| 二手 | 券商研报、权威媒体、行业报告 | 可多，但不得单独支撑核心数字 |
| 反证 | 与主结论相反的证据/口径 | 至少有则列出；没有要写「未找到反证」 |

- 同一媒体转载按 1 个来源计；媒体转述不得冒充一手。
- 全文真实域名 ≥ 2×题数（6 题 → ≥12），且每个域名要在正文被引用，不许「索引挂名」。
- 搜不到的源写「已尝试清单 + 失败原因」，不许用「公开渠道未见/据搜索」当答案。

## 2. 原文落盘（pages/）

- 会话打不开的站点 → 改 `pages_request.json` 推送，由 GitHub Actions 抓正文到 `pages/`（见 AGENTS.md §5）。
- PDF 用 PyMuPDF 在本机抽取：`tools/PPTAgent/skills/pptagent/.venv/bin/python -c "import pymupdf..."`；抽取后核对关键句，**不能只信搜索摘要**。
- 引用页码写清口径：PDF 页 vs 印刷页（招股书差 ~6 页，中报差 ~1 页）。

## 3. evidence.jsonl（Scout 必须落盘）

路径：`memory/state/research/<task>/evidence.jsonl`，一行一条：

```json
{"q":"Q6","claim":"2026H1 同店日销 7.78 万元（-1.4%）","src":"HKEX 2026 中期报告 p20","url":"https://...pdf","file":"/tmp/haidilao_ir2026.pdf","quote":"average same store sales per day ... 77.8 (in thousands of RMB)"}
```

- `quote` 必须是**原文摘录**（简繁/数字照抄，不许自己改写后当原文）。
- 每条 claim 与 quote 必须对得上（单位/期间/口径）——Q6 曾把 `77.8 千元` 写成 `77.8 万元`，就是 claim 与 quote 不匹配。
- 工具检查：`python3 tools/merlin_check.py <报告> --evidence <evidence.jsonl> --outline <outline.json>`（M10：每 Q ≥2 条、每条有 url+quote；M8：每 Q ≥1 一手、域名 ≥2×题数）。

## 4. 数据时点与口径

- 报告必须写「数据截止」日期（M5）；不同来源日期不一致时标明。
- 金额写币种与单位（元/千元/百万元/亿元）；比率写分子分母与期间；同店/翻台写公司定义。
- 推测与事实分开：事实进正文给来源，推断标【推测】+ 置信；「未公开」「待核实」只进分析师附注，不进正文结论。
