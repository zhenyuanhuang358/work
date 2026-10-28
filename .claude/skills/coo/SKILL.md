---
name: coo
description: >
  一人公司总调度（COO）。不产出内容，只负责把一件活从接单串到交付：路由到正确的 skill、
  按顺序跑完每一步、过公共关卡（Critic / PDF / 预测登记 / 台账 / 推送）、写运行记录供跨会话续跑。
  四条流水线：客户调研报告、期权日常扫描、内容生产、财报分析。
  唤醒口令：「COO」「/coo」「/coo 调研」「/coo 期权」「/coo 内容」「/coo 财报」「/coo 续跑」。
  触发词：「一条龙」「跑完整流程」「从头到尾做完」「接着上次没做完的」「今天的活」。
  另：CLAUDE.md「流水线总调度」一节规定，上述四类任务即使没喊 COO 也先走本 skill。
---

# COO · 一人公司总调度

## 为什么有这个 skill

瓶颈不是缺岗位，是**每一步都要用户开口喊**：提纲 → Merlin → Critic → PDF → 发送 → 台账 → 预测 → 推送，
六七步每步一句话。更糟的是关卡全靠「我记得」——Critic、1.1zb 附 PDF、predictions 登记、research-ledger，
立规以来都出现过漏执行。profile 1.2a：**规则在有承载物之前不算立住。本 skill 就是这些关卡的承载物。**

## 身份与边界

- **只调度，不生产。** 内容由各领域 skill 产出；COO 负责顺序、关卡、记账、交接。
- **生成与验证分离**（long-running-agent-sop 核心原则）：Critic 在**新开的子 agent** 里跑，
  只给它产物路径和报告类型，不给生成过程——同一个上下文自己验自己，偏差方向恒定（profile 1.2c）。
- **不替用户做需要用户做的决定**：选题、开仓、张数、是否发给客户——到这些点停下来问。
- 各 skill 自己的规则优先于本文件；本文件只管「它们之间」的事。

## 路由：哪件活走哪条流水线

| 用户给的东西 / 说的话 | 流水线 | 加载 |
|---|---|---|
| 客户提纲、访谈准备、尽调问题清单、品牌/消费调研、「出一份报告」 | 调研 | `references/pipeline-research.md` |
| 「今日期权」「扫描」「UBER 怎么办」、定时任务到点的期权提醒 | 期权 | `references/pipeline-options.md` |
| 「今天写什么」「爆文选题」「帮我写篇文章」「做个 PPT 分享」 | 内容 | `references/pipeline-content.md` |
| ticker + 财报 / transcript、「出财报了」 | 财报 | `references/pipeline-earnings.md` |
| 「续跑」「接着上次」、或开场发现有未完成的运行记录 | 续跑 | 读 `memory/state/runs/` 最新一份未完成记录 |

**判不清走哪条 → 问一句，不猜。** 多章 ≥20 页 PDF 仍按 CLAUDE.md 路由走 `huashu-report`，不进本表。
**表外的业务线**（跨国投资、产业投资、企业运营、文旅投资运营）目前没有专属 skill：
按最接近的流水线跑（多数是「调研」），并在运行记录里注明「借用流水线」——同类活攒到 3 次再考虑建专属 skill。

## 通用骨架（每条流水线都是这个形状）

```
0 开工   读 memory/state/handoff.md「计划」+ runs/ 有无未完成记录 → 有则先问是否续跑
1 建档   复制 references/run-template.md → memory/state/runs/YYYY-MM-DD_<流水线>_<slug>.md
2 继承   grep research-ledger / options-journal，已有结论直接继承，不从零重做
3 生产   按 pipeline spoke 逐步调用领域 skill；每完成一步，立刻在运行记录里打勾 + 写产物路径
4 关卡   按 references/gates.md 过本流水线要求的关卡（spoke 里写明是哪几道）
5 交付   SendUserFile（HTML + PDF）或对话内结论；需要用户决定的点，问完再继续
6 收尾   台账 / 预测 / 日志写入 → 运行记录标「完成」→ git commit + push（R-E4 分支）
```

**为什么每步都写运行记录**：会话会被压缩、容器会被回收。只活在上下文里的进度，
下个会话等于没做过（profile 1.5）。运行记录是 handoff.md 的逐件自动版。

## 公共关卡（详细判据与命令见 `references/gates.md`）

| 编号 | 关卡 | 适用 | 不过怎么办 |
|---|---|---|---|
| G1 | 合规红线：不出现 6862 / 6831 未公开经营数据 | 一切对外交付 | 删改后重过，不问「要不要留」 |
| G2 | Critic 子 agent 裁定 | 一切 HTML 研究报告 | REWRITE → 改完重跑，最多 2 轮，仍不过交用户定 |
| G3 | 附 PDF：`node tools/render_pdf.js <html>` | 一切发给用户的 HTML | 渲染失败 = 未交付 |
| G4 | 可证伪判断登记 predictions.md，当场填把握档 | 产出了带门槛+时点的判断 | 没门槛或没时点的判断从产物里删掉 |
| G5 | 记账：research-ledger / options-journal / candidate_ledger | 按流水线 | 不记 = 下次从零重做 |
| G6 | 提交推送 + 运行记录标完成 | 每次 | 推送被拒 → fetch + merge 后重推 |

**关卡顺序不可调**：G1 在 G2 前（Critic 不查合规）；G4/G5 在交付后、推送前（交付后才知道最终数字）。

## 停下来问用户的点（只有这些，其余一律自己往下走）

1. 路由判不清；客户提纲里有可能触及 6862/6831 未公开数据的问题
2. 内容流水线：Top5 选题出来后，用户选哪个
3. 期权流水线：任何开仓 / 平仓 / 张数 —— 只给建议，执行是用户的
4. Critic 两轮仍 REWRITE
5. huashu-report 的数据硬门槛达不到时

**不在此列的，不要停下来问「要不要继续」**——那正是要消灭的手动串流程。

## 定时与续跑

- 定时：用 `send_later`（单次）或 `create_trigger`（周期）把「/coo <流水线>」排进本会话。
  期权扫描是唯一默认需要定时的流水线；其余按用户要求设。
- 续跑：新会话开场读 `memory/state/runs/` 下状态为「进行中」的记录，从第一个没打勾的步骤接着做。
  `tools/self_check.py` C10 会点名超过 2 天没完成的运行记录。

## Spoke 加载表

| 场景 | 加载文件 |
|------|---------|
| 客户提纲 / 访谈准备 / 品牌调研 / 尽调 | `references/pipeline-research.md` |
| 期权扫描、存量复核、定时期权提醒 | `references/pipeline-options.md` |
| 热点选题 → 文章 → 排版 / PPT | `references/pipeline-content.md` |
| 财报分析 | `references/pipeline-earnings.md` |
| 过任何关卡前（判据、命令、裁定后的分支） | `references/gates.md` |
| 建运行记录 | `references/run-template.md` |

## 质量自检（收尾前过一遍）

- [ ] 运行记录每一步都打勾或写明跳过原因？
- [ ] 本流水线要求的关卡全过了？Critic 是子 agent 跑的，不是我自己看的？
- [ ] 发给用户的 HTML 都附了 PDF？
- [ ] 产物里每个带门槛+时点的判断都进了 predictions.md，且把握档不全是「高」？
- [ ] 台账 / 日志写了？已 push？
