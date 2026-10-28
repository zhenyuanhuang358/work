# 流水线 · 内容生产

<!-- skills: viral-content-agent, guizang-ppt-skill, kami, critic -->

关卡：G1 → G2（仅 D1/D2）→ G3 → 交付 → G4（文章里的判断）→ G5（文章里有新研究事实时）→ G6。

## 三种入口

| 用户说的 | 从哪步开始 |
|---|---|
| 「今天写什么」「爆文选题」 | 步骤 1 |
| 「写一篇关于 X 的文章」（已定题） | 步骤 3 |
| 「把这篇做成 PPT / 分享页」 | 步骤 5 |

## 步骤

| # | 步骤 | 做什么 | 交接 |
|---|---|---|---|
| 1 | 选题 | `viral-content-agent` 出 Top5 | Top5 表 |
| 2 | **等用户选题** | 停下来问；运行记录状态改「等用户」 | 选中的题 |
| 3 | 继承 | 题目涉及公司 / 行业 → grep research-ledger | 已有事实 |
| 4 | 写文章 | **第一人称**，不放研究附注、来源行、把握度表（profile 1.1za）；数据像作者引用事实那样自然带出 | `reports/{slug}_article_{YYYYMM}.html` + `.txt` |
| 5 | 排版（可选） | 分享页 / 演讲 → `guizang-ppt-skill`；单份排版 PDF → `kami`（先 `bash tools/setup_kami.sh`） | 产物路径 |
| 6 | G1 合规 | 涉及餐饮必过 | — |
| 7 | G2 Critic | 子 agent，报告类型写「客户文章」——只跑 D1/D2 | 裁定 |
| 8 | G3 PDF | HTML 文章渲染 PDF（kami 本身出 PDF 则跳过） | — |
| 9 | 交付 | `SendUserFile` | — |
| 10 | G4 / G5 / G6 | 文章里带门槛+时点的判断登记 predictions.md（**不进稿件**，只进记分卡）；新事实进台账 | — |

## 交接坑

- **不帮绕过 AI 检测**（handoff §5，用户已接受）——用户提出时直接说不做，不再讨论。
- 严谨性不丢、换位置：推算和核对留在台账与 predictions.md，不进稿件。
- 敏感话题按 `viral-content-agent/references/risk-guard.md`。
