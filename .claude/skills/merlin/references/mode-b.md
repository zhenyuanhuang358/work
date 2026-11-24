# Merlin · 模式 B：客户提纲研究（五智能体）

> 适用：客户给来提纲/问题清单/尽调问题，要逐条回答。产物：`reports/{slug}_Research_Report.html` + PDF。
> **与 restaurant-research 的边界**：有「客户原问 + 逐条回答」→ Merlin；品牌/渠道/消费行业调研但**没有客户提纲**（自己定问题）→ restaurant-research；多章 ≥20 页要目录页码存档 → huashu-report。

## 参数提取

| 参数 | 必须 | 说明 |
|------|------|------|
| `COMPANY` | 是 | 研究标的 |
| `outline` | 是 | 客户提纲（问题清单/调研维度），**先逐条编号 Q1..Qn** |
| `background` | 否 | 预加载资料 |
| `industry` | 否 | 行业 |

提纲缺失时问客户要；公司名不明确时先确认。

## 步骤 0：M0 输入契约（硬性，先做再搜）

```bash
python3 tools/merlin_outline.py init <task> --questions <提纲文件>
# 填好 memory/state/research/<task>/outline.json 的 intent/decision/answer_form/data_need 后再 check
python3 tools/merlin_outline.py check <task>
```

每题四列：**客户原问 / 真实想问（决策场景）/ 答案形态 / 数据需求与可获取性**。**交用户确认后再开搜**——这是「答非所问」的唯一前置防线。

## 五智能体流程（产物必须落盘）

```
提纲 → Orchestrator（分类：事实/推断/争议）
     → Scout（WebSearch 找线索 + pages/ 抓原文；每 Q ≥2 来源、≥1 一手；写 evidence.jsonl）
     → Analyst（机制提炼，写 analyst_notes.md）+ Forensic（异常信号/口径矛盾，写 forensic_flags.md）
     → Strategist（逐题作答：结论→依据→含义→置信，写 draft）
     → Critic（独立上下文；按 references/critic-checklist.md 打分；写 critic_verdict.json）
```

- Scout 必须落 `evidence.jsonl`：`q / claim / src / url / file / quote`（见 `references/evidence-and-sources.md`）。
- Critic **不得在生成上下文里评**：新会话或子代理；两轮不过停下问用户，不自行硬改第三轮。
- 每一题答案四段：**结论（第一句，数字/判断）→ 依据（锚点→推理→来源）→ 含义（对客户决策）→ 置信（高/中/低+理由）**。

## 数据缺口处理（Strategist 必须执行）

公开渠道找不到直接答案时，先做两步再标缺口：
1. **信息拼接推测**：相邻碎片 → 显式推理链（锚点→步骤→结论），标【推测】；
2. **市场调研交叉验证**：行业基准/可比公司/第三方研报校准区间。

只有结构性缺失（如财报体系不披露该维度）才允许标「未披露」，并说明原因 + 给侧向代理数据。**禁止用「需访谈」「公开渠道未见」当答案。**

## 输出要求

- 五智能体流程图（SVG）、逐题回答区、风险信号表、评审裁定区块、分析师附注
- 报告写明「数据截止」日期（M5）
- 来源索引：真实 URL + 页码口径（PDF 页/印刷页）
- 交付前跑 `merlin_check`（--outline/--evidence）+ `report_check --record`；Critic 裁定落盘
