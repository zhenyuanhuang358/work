# Merlin · 输出规范（HTML + PDF）

## 结构（模式 B）

1. Pub bar：报告名 + 数据截止日期
2. 标题 + 英文副题
3. Stat bar（4 个关键数）
4. 一句话结论（3–4 行，带依据指向）
5. 每题区块：`Qn · 问题` + 四段（结论/依据/含义/置信）
6. 机制图/时间轴/矩阵表（SVG 原生，≥1 张）
7. 分析师附注（末尾，>50% 位置）：页码口径、来源性质、未核实项、合规声明、数据截止
8. 来源索引（真实 URL + 页码）
9. 反馈链接（netlify `product=merlin&report={slug}`）

## 硬性

- **零 Markdown 符号**（`**` `#` `` ` ``），全部 HTML/CSS
- 中英双语：章节标题中文 + 英文小标
- 色板：ink `#0a0a0b` / paper `#f1efea` / copper `#8b6c42` / gold `#c9a84c`；绿 `#2a5c3f`、红 `#8b2e2e`、琥珀 `#c47a1e`
- 字体：IM Fell English（英文衬线）+ Songti SC（中文）
- 每题第一句必须结论（数字/判断），禁止元叙述开头
- 正文只写结论与证据链；方法限制、未核实项全部进附注

## PDF

- 优先 `node tools/render_pdf.js <html>`；该脚本依赖 playwright，缺依赖时用 Chrome headless 回退：
  `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --no-pdf-header-footer --print-to-pdf=... file://...`
- 交付前确认 PDF 与 HTML 同源（改完 HTML 必须重渲染）

## 交付核对

```bash
python3 tools/merlin_check.py <报告> --outline <outline.json> --evidence <evidence.jsonl> --pdf <PDF>
python3 tools/report_check.py <报告> --pdf <PDF> --record
```

两项 0 FAIL，且 Critic 独立上下文裁定 PASS（或 CONDITIONAL 修完）才交付；附一行「高 X / 中 Y / 低 Z · Critic 裁定」。
