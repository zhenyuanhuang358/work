# 中文排版调研笔记（v0.8，2026-10-13）

目的：把「中文排版好看」变成可执行、可验证的规则（落地见 `design-rules.md` §中文排版 T1–T14）。
只记录实际读过的来源；标注「推断/设计决定」的是本 skill 自己的取舍，不是来源原话。

## 1. 归藏 Notion「文章库」（只读检索）

| 条目 | 链接 | 取用的结论 |
|---|---|---|
| 可读性：最佳行长（Baymard） | https://www.notion.so/05991f02284f4f7482f720d8f57ebc79 | 拉丁文每行 50–75 字符；Ruder 50–60；WCAG 1.4.8 不超过 80 → T4 |
| 最标准的系统字体规范 font-family | https://www.notion.so/41778f29633f46fb921ba330ad34e577 | 西文字体在前，再 PingFang SC / Hiragino Sans GB / Microsoft YaHei / 思源黑体 → T13 |
| Web 开发中文字体指南 | https://www.notion.so/178b701d2cc948fd87a645b1538a7c5a | 西文字体放中文字体之前，让英文与数字用西文字形 → T13 |
| 一万六千字字体与排版指南 | https://www.notion.so/c991c6a7fa864f71a327d12a6d94196b | 中文行距 1.5–2 倍（1.2 过密）；引用 clreq 2.3.5 行长取字号整数倍；中文两端对齐靠调整字距；标点避头尾 → T3/T4/T5/T8 |
| Better Web Type: 8 more tips | https://www.notion.so/c82c459a307b4f219c17d76bf6c93796 | 行高要按语言调整 → T3 |
| Requirements for Chinese Text Layout (clreq) | https://www.notion.so/6b60ad2aebec46058980174b529991fe | 收藏了 clreq，见下 |

## 2. W3C《中文排版需求》clreq — https://www.w3.org/TR/clreq/
- §6.3.3 横排中西混排：汉字与西文字母/数字之间留 ≤1/4 em 间距，行首行尾不加 — https://www.w3.org/TR/clreq/#mixed_text_composition_in_horizontal_writing_mode → T10
- §6.2 正文原则上两端对齐 — https://www.w3.org/TR/clreq/#h_justification → T5
- §6.1.1 行首行尾禁则；标点挤压先于禁则处理 — https://www.w3.org/TR/clreq/#prohibition_rules_for_line_start_end → T8
- 标点宽度调整 — https://www.w3.org/TR/clreq/#punctuation_width_adjustment → T9
- §5.3.1 着重号：横排置于字下 — https://www.w3.org/TR/clreq/#x5-3-1-emphasis-marks → T12
- 段落可不缩进、以段间空白分段 → T6

## 3. 《中文文案排版指北》— https://github.com/sparanoid/chinese-copywriting-guidelines
- 中英文之间、中文与数字之间加空格；数字与单位之间加空格；度数与百分比前不加 → T10 + 写作侧规则
- 全角标点与其他字符间不加空格；用全角标点；不重复标点；数字用半角

## 4. X 上的讨论（搜索「盘古之白 / text-autospace / 中文排版」）
- https://x.com/onlookersh/status/2104992413127475524 — 仍在引用 2014 年的《指北》，说明手动加空格仍是共识
- https://x.com/AkinoNya/status/2106600162286276622 — 有了 CSS `text-autospace` 就不必手打「盘古之白」 → T10 的 `@supports` 分支
- https://x.com/SilentDepthCN/status/2108386635000021319 — 抱怨浏览器不支持 text-autospace → 所以 Chrome 下仍需渲染器插空格
- https://x.com/grok/status/2107578152268501382 — 依 W3C 做中西间距，配合不断行
- https://x.com/Jtxccjdbb/status/2104768592369869113 — 中文对字重与行高更敏感 → T14

## 5. 浏览器支持（MDN / web-features，2026-10）
- `text-autospace`：Firefox 145+、Safari 27+；Chrome/Edge 未支持 — https://developer.mozilla.org/en-US/docs/Web/CSS/text-autospace
- `text-spacing-trim`：仅 Chromium，且依赖字体 `halt`/`chws` 特性 — https://developer.mozilla.org/en-US/docs/Web/CSS/text-spacing-trim
- `hanging-punctuation`：仅 Safari
- `text-emphasis`：全主流浏览器

## 6. 推断与设计决定（非来源原话）
- 36em 行长：由 50–75 拉丁字符换算（1 汉字 ≈ 2 个拉丁字符宽），取中值偏短。
- 17px 字号、标题字重 ≥300：视觉判断。
- 渲染器插 span 而非直接插空格：便于在支持 text-autospace 的浏览器中关掉，避免双重间距。
