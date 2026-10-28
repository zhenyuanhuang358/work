# 流水线 · 客户调研报告

<!-- skills: merlin, restaurant-research-skill, huashu-report, critic -->

关卡：G1 → G2 → G3 → 交付 → G4 → G5 → G6（全部）。

## 第一步先分型（判据是交付形态，CLAUDE.md 路由表）

| 用户给的 | 走 | 产物 |
|---|---|---|
| 客户提纲 / 逐条回答 / 投资尽调问题清单 | `merlin` 模式 B | `reports/{slug}_Research_Report.html` |
| 访谈准备、给背景资料准备访谈 | `merlin` 模式 A | `reports/{slug}_Merlin_Brief.html` |
| 品牌 / 渠道 / 消费行业调研（非提纲非访谈） | `restaurant-research-skill` | `reports/{slug}_research_{YYYY}.html` |
| 专家访谈 Q&A 格式 | `restaurant-research-skill` 的 expert-interview-format | 同上 |
| 客户要「文章」 | **转内容流水线**（`pipeline-content.md`）——文章体规则不同（profile 1.1za） | — |
| 多章 ≥20 页、要目录页码 / PDF 存档 | `huashu-report`，**接活前先对齐数据能否达到 value/basis/n/src 标准** | PDF |

## 步骤

| # | 步骤 | 做什么 | 交接 |
|---|---|---|---|
| 1 | 继承 | `grep -n -A30 "<公司/品牌名>" memory/state/research-ledger.md` | 已有事实与推测（带日期）；只补新的 |
| 2 | 合规预检 | 提纲里有没有直接问 6862/6831 未公开数据的题 → 有就标出，口径框写「仅公开口径」 | 题目清单 + 合规标记 |
| 3 | 生产 | 调用对应 skill 完整跑完；答案前置（profile 1.1d），客户提纲推测数值交付单值（R-R6） | HTML 路径 |
| 4 | G1 合规终检 | 见 gates.md | — |
| 5 | G2 Critic | 子 agent 裁定 | 裁定 + flags |
| 6 | G3 PDF | `node tools/render_pdf.js <html>` | PDF 路径 |
| 7 | 交付 | `SendUserFile` HTML + PDF；附一行「高 X / 中 Y / 低 Z · Critic <裁定>」 | — |
| 8 | G4 | 报告里带门槛+时点的推测（门店数、收入、同店）逐条登记，当场定档 | — |
| 9 | G5 | research-ledger 追加一条（格式照台账末尾几条） | — |
| 10 | G6 | 提交推送，运行记录完成 | — |

## 交接坑

- **数据缺口默认推测，不留空**（R-D6），但「结构性不存在」的维度答「未披露」（profile 1.1q）。
- **问卷时点 vs 事件时点**先核对（profile 1.1r）。
- **总额 ≠ 分项之和**时在交付物里写明差额去向（profile 1.1s）；数据表里声明 `parts`。
- **搜索摘要不是来源**（profile 1.1y）：关键数字至少点开一个原文。
