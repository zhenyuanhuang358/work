# Skill 构建标准

每次创建或更新 Skill 时，必须遵循 hub-and-spoke 架构：

## 结构
- **SKILL.md（hub）**：只放 agent 立即需要的内容——触发条件、核心原则、工作流骨架、加载指引。目标 ≤200 行。
- **references/（spokes）**：重的、条件性的内容放到独立文件，hub 说明何时加载哪个 spoke。

## Hub 必须包含的 Spoke 加载表
```
| 场景 | 加载文件 |
|------|---------|
| [触发条件] | references/xxx.md |
```

## 什么放 hub，什么放 spoke
| 放 hub | 放 spoke |
|--------|---------|
| 角色扮演规则 / 身份 | 详细操作流程 / 检查清单 |
| 核心心智模型（≤5个） | 人物时间线 / 谱系 |
| 决策启发式（≤7条） | 分场景研究框架 |
| 质量自检（精简版） | 数据来源索引 / 指标定义 |
| Spoke 加载指引 | 格式模板 / 案例 |

## 设计原则（来自 Perplexity 实践）
1. Skill 写的是**给模型的上下文**，不是代码——不要写成程序
2. 只写 agent 没有 Skill 就会做错的事，其他省略
3. 不为变化比维护更快的东西建 Skill
4. LLM 不能可靠地自己写 Skill——必须基于真实领域经验
5. 每个 spoke 是条件加载的，hub 里要明确说"什么情况下读哪个文件"

---

# Earnings Copilot 报告模板标准

**模板规范内嵌于本节**（14节顺序 + 视觉规范），无独立模板文件；参考实现见 `reports/00538_Copilot_Report.html` / `reports/avgo_Copilot_Report.html`。

每次生成财报分析 HTML 报告，必须严格遵守以下规范：

## 强制要求

1. **零 Markdown 符号**：报告中不得出现任何 `*`、`**`、`#` 等 Markdown 标记。所有格式通过 HTML/CSS 实现（`<strong>`、`<span class="label-zh">` 等）。

2. **中英双语**：面向中国客户，中文为主体，英文为辅助副标题。具体规则：
   - Section 标题：中文大标 + 英文小标（`.section-zh` / `.section-en`）
   - 分析段落：中文正文，段首 `.label-zh` + `.label-en` 双语标签
   - 风险/主题条目：中文名称 + 英文斜体副名
   - 裁决框：中文主体 + 英文 `.verdict-en` 半透明副文

3. **数据必须图表化**：以下数据不得以纯文字呈现，必须用 SVG 图表：
   - 季度营收走势 → 柱状图（8 季度）
   - 分部营收拆分 → 水平条形图（含 YoY 增速）
   - EPS 对比 → 双柱对比图（共识 vs 实际）
   - 毛利率走势 → 折线图（含低点标注 + Q2E 虚线预测）

4. **目标价三情景**：每份报告必须包含：
   - SVG 价格区间图：熊市/基准/牛市标记 + 现价箭头
   - 三列情景卡片：目标价、较现价涨跌幅、核心逻辑、EPS 假设、P/E
   - 关键假设对照表：4 行核心假设，三情景并列对比

## 视觉规范

| 元素 | 规范 |
|------|------|
| 字体 | IM Fell English（英文衬线）+ Songti SC（中文衬线） |
| 颜色 | ink #0a0a0b / paper #f1efea / copper #8b6c42 / gold #c9a84c |
| 超预期 | var(--green) #2a5c3f |
| 低于预期 | var(--red) #8b2e2e |
| 中性/注意 | var(--amber) #c47a1e |
| SVG 图表 | 纯原生 SVG，零外部库依赖 |
| 图表字体 | 在 svg 标签上声明 `font-family:'IM Fell English',Georgia,serif` |

## 固定 Section 顺序

1. Pub Bar（发布栏）
2. 双语标题 + 标签行（评级 + 语气评分）
3. Stat Bar（4格关键指标）
4. 季度营收走势图
5. 分部营收图
6. EPS 对比 + 毛利率走势（两列）
7. 核心分析（文字，四段双语）
8. 目标价三情景（SVG 区间图 + 卡片 + 假设表）
9. Verdict Box（裁决框，深色底）
10. 管理层语气（进度条 + 说明）
11. 核心主题（chips）
12. 风险矩阵（表格）
13. 分析师 Q&A 张力区域
14. Footer

---

# 工作原则

以第一性原理！从原始需求和问题本质出发，不从惯例或模板出发。

1. 不要假设我清楚自己想要什么。动机或目标不清晰时，停下来讨论。
2. 目标清晰但路径不是最短的，直接告诉我并建议更好的办法。
3. 遇到问题追根因，不打补丁。每个决策都要能回答"为什么"。
4. 输出说重点，砍掉一切不改变决策的信息。

---

# 报告类任务的路由（2026-09-15 定，因 huashu-report 无触发词）

**⚠ 为什么需要这条规则**：Merlin / Earner / restaurant-research 都有明确触发词列表，
**而 huashu-report 的 frontmatter 里一个触发词都没有，只靠 description 语义匹配**。
后果：说「帮我做个报告」会被前三个截胡。**这条路由规则就是补那个缺口——
不改第三方文件（upstream 更新会冲突），在自己这侧解决（profile 1.2h 的同一条推论）。**

**判据是可观测的交付形态，不是题材：**

| 交付形态 | 走谁 | 产物 |
|---|---|---|
| **多章、≥20 页、要目录页码 / Exhibit 编号 / 跨页表头、PDF、供引用或存档** | **huashu-report** | `数据表.json` + `build.py` + PDF |
| 客户提纲 / 访谈准备 / 逐条回答 / 投资尽调准备 | Merlin | 单篇 HTML（R-E6） |
| 财报季度分析 | Earner | 单篇 HTML（14 节模板） |
| 品牌 / 渠道 / 消费行业调研（非提纲非访谈） | restaurant-research | 单篇 HTML |
| 横向翻页网页 PPT（杂志风 / 瑞士风 / 发布会分享页） | `guizang-ppt-skill` | 单 HTML |
| 单篇文章 | `design` | — |

**⚠ 本表一律写 skill 的精确可调用名**（如 `guizang-ppt-skill` 不是 `guizang-ppt`）——
写错名字的路由表比没有路由表更糟：照着它叫会叫不中，而且看起来像已经解决了。
`tools/self_check.py` 的 C5 会逐个核对表里的名字。

**一句话判据：交付物是「一页 HTML」还是「一本 PDF」。** 是一本就走 `huashu-report`。

**显式点名一律优先**：用户说「用 huashu-report」「/huashu-report」时直接走它，不再判形态。

**⚠ huashu-report 的硬门槛，接活前先确认**：它要求每个数字有 value / basis（口径）/ n（样本量）/ src（出处）。
**口径写不出一句完整的话，这个数字就不能用。**「大概是这样」「我记得好像」它会直接拒收——
**这不是它难伺候，这是它和前面几个 skill 的本质差别，接活前要先跟用户对齐数据能不能到这个标准。**

---

# Critic 质量门控

**每次 `SendUserFile` 推送 HTML 研究报告前，必须先运行 `.claude/skills/critic/SKILL.md`，输出裁定结果（PASS / CONDITIONAL / REWRITE），再决定是否推送。**

适用范围：Merlin / Earner / restaurant-research / buffett-analyst 生成的所有 HTML 报告。

**⚠ huashu-report 不走 Critic**：它交付的是 PDF 不是 HTML，且自带两层自检——
`render.py` 的机械自检（图表编号连续性、目录页码一致、空页、占位符残留、**逐页四边留白几何实测**）
＋ SKILL.md 里的逐页肉眼清单（列缝粘连、负值画成零高度、标注被版心切掉、孤儿段、长表跨页表头丢失）。
**Critic 的五维评审是为 HTML 报告设计的，套到 PDF 上大部分维度失效。**
→ **但 D1（数据来源）/ D2（内部数字一致性）/ D3b（答案前置）仍然适用，交付前手工过这三项。**

---

# 记忆中心 Memory

**记忆的家**：`memory/`（读写约定见 `memory/README.md`）

跨会话、跨 skill 的记忆统一存于 `memory/`，不再散落在 `.claude/` 或各 skill 的 `references/`。

| 文件 | 何时读 |
|------|--------|
| `memory/profile.md` | **每个会话第一次执行任何任务前必读**——历史教训、UI/产品偏好、可复用规则（R-D/R-R/R-E/R-C）、配置速查 |
| `memory/state/options-journal.md` | 期权扫描 / 持仓相关任务前 |
| `memory/state/research-ledger.md` | 研究某公司前 grep，继承已有结论，不从零重做 |

**写入**：出现新事故/纠正 → 追加 `profile.md`；开平仓 → 更新 `options-journal.md`；交付研究报告 → 追加 `research-ledger.md`。详见 `memory/README.md`。
