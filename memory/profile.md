# 用户偏好与经验档案

> 本文档基于所有历史对话复盘提炼，每次 Code 会话自动加载，无需重复说明。
> 最后更新：2026-06-10

---

## 一、执行经验总结

### 1.1 数据质量事故

**规则：每次期权扫描前必须先更新 GitHub 价格缓存（2026-06-03 确认）**
- 触发方式：`mcp__github__push_files` 推 `price_fetch_trigger.txt` 到 main 分支
- 等待方式：轮询 `stock_prices.json` 的 `updated_at` 超过当日零点后才出报告
- 不允许用旧缓存直接出报告，不允许 WebSearch 价格代替

---

**事故：PLTR 股价错误（2026-05-19）**
- 问题：WebSearch 返回延迟数据，报告显示 PLTR ~$22，实际价格 $135.58
- 根因：WebSearch 不可作为股票实时价格来源，数据来源和呈现时间不一致
- 修复：引入 iTick API，股价强制走 `api0.itick.org`，WebSearch 只用于 IV Rank / 异常流
- 教训：**任何价格数据必须先从 iTick 拉取并核实，未核实数据不得呈现**

**事故：港股 PDF 直接 WebFetch 失败率 >70%**
- 问题：直接 WebFetch hkexnews.hk 年报 PDF，失败，浪费时间
- 修复：港股财务数据优先走聚合站（aastocks / futu.io / 雪球），PDF 只作最后手段
- 教训：**永远不要把 hkexnews PDF 作为第一选择**

---

### 1.2 报告遗漏问题

**问题：多次报告忘记附反馈链接**
- 用户发现方式："分析完了你忘了给我什么了？"
- 反馈链接：`https://spontaneous-youtiao-b9cde9.netlify.app`
- 规则：**每份 HTML 报告必须在 Verdict Box 下方加反馈入口**，链接带 product + report 参数
- 涉及产品：earner.py / merlin.py / merlin_research.py / 所有手写 HTML 报告

---

### 1.3 Bug 修复模式

**问题：Bug 修复分批返工，用户不满**
- 用户原话："给我检查优化一下，我怎么感觉很多 bug，要一次性搞定，不要返工，现在找出来直接改"
- 用户原话："搞定了？再看看有没有可以优化的，一次性找出来改掉，开始干"
- 正确模式：**收到"检查/优化"指令 → 全量扫描所有相关文件 → 列出所有问题 → 一次性全部修复，不分批**

---

### 1.4 CSS/布局错误

**问题：Merlin critic-box 白屏（只有几个字，大量留白）**
- 根因：外层 `div` 同时带了 `critic-box`（边框）和 `critic-header`（display:flex），两 class 叠加后内容横向并列被 overflow:hidden 截断
- 修复原则：**每个 CSS class 单一职责，容器 class 不做 flex 布局，布局 class 不加 overflow**
- 教训：HTML 生成前必须检查 class 叠用

---

### 1.5 上下文压缩后的信息丢失

**问题：上下文压缩后丢失关键记忆（如反馈链接 URL、用户的期权账户参数）**
- 根因：Claude 上下文窗口压缩了早期对话内容
- 解法：**所有关键配置写进文件（本文档 + CLAUDE.md），不依赖对话记忆**

---

### 1.6 GitHub Action 缓存机制

**问题：GitHub 缓存超过 24 小时未更新，导致财务数据不准**
- 用户原话："github缓存要更新，实时行情差距24小时不准确，每次执行前都要更新一次github缓存"
- 规则：每次调研前先检查 `research_cache/_manifest.json` 的 `updated_at`，距今 >24h 则先触发 GitHub Action 刷新

---

### 1.7 Skills 文件交叉引用问题

**问题：Skill 文件之间有大量 broken references（指向不存在的文件路径）**
- 发现方式：用户要求"全量扫描 skill 文件，找出所有问题"
- 正确流程：每次新建或修改 skill 后，**主动验证所有 spoke 路径是否真实存在**
- 教训：hub 里的 spoke 加载表路径必须和实际文件路径完全一致

---

## 二、偏好与理念

### 2.1 产品方向

**正在构建的系统**：连锁餐饮 + 金融投资的多智能体决策工具集。

| 产品模块 | 定位 |
|---------|------|
| Earner | 机构级财报分析，输出 HTML 报告 |
| Merlin | 麦肯锡风格访谈作战包 + 客户提纲研究 |
| Restaurant Research | 消费行业调研助手（含专家访谈格式） |
| Viral Content | 全网爆文热点扫描 |
| US Options | 小账户期权策略（$8500 规模） |
| Buffett Analyst | 价值投资分析 |
| Expansion Health | 连锁餐企扩张健康度预警 |
| Restaurant Risk Radar | 连锁餐饮组织风险诊断 |

**产品本质**：不是聊天机器人、不是知识库、不是 FAQ。是有立场的决策 Copilot，能给出可操作的洞察和行动方案。

---

### 2.2 UI 设计偏好

**视觉风格：古典 × 机构**
- 字体：IM Fell English（英文衬线）+ Songti SC（中文衬线）
- 调色板：ink #0a0a0b / paper #f1efea / copper #8b6c42 / gold #c9a84c
- 超预期：#2a5c3f（深绿）/ 低于预期：#8b2e2e（暗红）/ 注意：#c47a1e（琥珀）

**排版原则**
- 信息密度高，不留无意义白空间（"这个界面就这几个字，怎么留那么长的白"）
- 数据必须图表化（SVG 原生，零外部库依赖）
- 关键数字用大字报式呈现（stat bar / 数据大字报）
- Verdict box 用深色底，强调判断结论

**双语规则**
- 中文为主体，英文为辅助
- 段落标签：`.label-zh`（中文大标）+ `.label-en`（英文副标，较小较浅）
- Merlin/对话类报告：英文在上 + 中文在下（`.bi-en` / `.bi-zh`）
- 财报类报告：中文为主，英文副标题

---

### 2.3 交互偏好

**指令风格：极简触发**
- 用户习惯用极短指令触发任务："今日美股机会" / "earner 味千中国" / "今日爆文机会"
- 无需确认，直接执行到底

**期望的响应模式**
- 不要问"需要我做什么"——直接做
- 不要分批交付——一次性完整交付
- 错误要承认并立即修正（"上次推荐错误更正"表格）
- 如果忘了什么，用户会直接说（"你忘了给我什么了？"）——立刻补上

**中断信号**
- "[Request interrupted by user]" 出现 = 方向错了，停下来思考再来
- 被中断后要主动说明调整了什么

---

### 2.4 数据处理理念

**数据诚实优先**
- 找不到的数据必须标注 `【数据缺口】`，不用模糊语言掩盖
- 每个关键数字注明来源和日期：`【一手·财报】` / `【二手·媒体】` / `【推断】` / `【分析预测】`
- 多源数据冲突时：一手 > 二手；差异 ≤15% 取均值；>15% 并列呈现

**推断有据**
- 不能获取的数据，用结构化逻辑推断并明确标注（如加盟商名单推断表）
- 推断置信度要标出（高/中/低），不装成确定事实

---

### 2.5 Skill 架构理念

- Hub-and-spoke 架构：hub ≤200 行，重内容放 spoke
- Skill 是"给模型的上下文"，不是代码
- 只写 agent 没有 Skill 就会做错的事
- 每个 spoke 条件加载，hub 里明确写"什么情况下读哪个文件"

---

## 三、可复用规则清单

> 以下规则适用于本项目所有 Code 会话，权重高于默认行为。

### 数据规则

```
R-D0: 期权扫描前 → 必须先触发 GitHub Action 更新价格缓存，等 updated_at 刷新后才出报告
      触发：push price_fetch_trigger.txt 到 main 分支
      验证：轮询 stock_prices.json updated_at > 当日零点

R-D1: 股票实时价格 → 必须从 GitHub 缓存 stock_prices.json 读取，不得用 WebSearch 代替
      缓存地址：https://raw.githubusercontent.com/zhenyuanhuang358/work/main/stock_prices.json
      后端：GitHub Action 运行 scripts/fetch_prices.py（Finnhub 主源 + yfinance 兜底）
      缓存外标的：WebSearch 兜底，报告中注明「需在平台二次确认」
      （历史：2026-05 曾用 iTick API，已废弃；.env 现存 FINNHUB_TOKEN）

R-D2: 港股财务数据 → 优先聚合站（aastocks / futu.io / 雪球），不要先试 hkexnews PDF

R-D3: GitHub 研究缓存 → 每次使用前检查 _manifest.json updated_at，>24h 则先刷新

R-D4: 数据来源 badge → 每个关键数字必须带标注：
      【一手·财报】【二手·媒体】【推断】【分析预测】【数据缺口】

R-D5: 数据核实后才出报告 → 不允许用未核实数据生成结论性内容
```

### 报告规则

```
R-R1: 每份 HTML 报告必须有反馈链接
      URL: https://spontaneous-youtiao-b9cde9.netlify.app
      位置：Verdict Box 下方
      参数：?product={产品名}&report={报告ID}

R-R2: 财报类报告严格遵循 CLAUDE.md 中的 14 节顺序（Earner Copilot 报告模板标准）

R-R3: 所有 HTML 报告零 Markdown 符号（无 * # ** 等）

R-R4: 数据图表化 → 营收/EPS/毛利率用 SVG 原生图表，不得纯文字呈现

R-R5: 双语输出 → 中文主体 + 英文辅助，格式见 CLAUDE.md 视觉规范
```

### 执行规则

```
R-E1: Bug 修复 → 全量扫描后一次性修完，不分批，不返工

R-E2: 检查/优化指令 → 先读所有相关文件，列出全部问题，再一次性全改

R-E3: Skill 新建/修改后 → 主动验证所有 spoke 路径是否真实存在

R-E4: Git 推送 → 始终推到 claude/install-claude-hud-d51E6 分支

R-E5: 触发词识别 → 极简指令直接执行，无需确认（见 Skill 触发词列表）
```

### CSS/布局规则

```
R-C1: 每个 CSS class 单一职责——容器 class 不做 flex 布局，布局 class 不加 overflow

R-C2: 避免 overflow:hidden 在动态高度容器上——改用 overflow:visible 或去掉

R-C3: 信息密度 > 留白——除非有设计意图，不留大段空白区域

R-C4: SVG 图表必须在 <svg> 标签声明字体：
      font-family:'IM Fell English',Georgia,serif
```

---

## 四、关键配置速查

| 项目 | 值 |
|------|---|
| Finnhub Token | `FINNHUB_TOKEN`（存于 `/home/user/work/.env` + GitHub Secrets） |
| 价格缓存 | `https://raw.githubusercontent.com/zhenyuanhuang358/work/main/stock_prices.json` |
| 反馈表单 URL | `https://spontaneous-youtiao-b9cde9.netlify.app` |
| Git 工作分支 | `claude/install-claude-hud-d51E6` |
| 研究缓存路径 | `research_cache/{slug}.json` |
| 报告输出目录 | `reports/` |
| 期权账户规模 | $8,500（中等偏激进，70%权利金/20%价差/10%高赔率） |
| 字体系统 | IM Fell English（英文）+ Songti SC（中文） |

---

## 五、产品背景速记

用户在构建一套面向**餐饮连锁行业**和**个人投资决策**的 AI 工具集。

**餐饮侧**：服务对象是连锁餐饮老板 + 投资机构调研员。核心价值：领先财报 1-2 季度的定价缺口判断、组织风险早期信号、专家访谈作战包。

**投资侧**：个人投资组合（美股期权 $8500 账户）+ 机构级财报分析工具。核心价值：消除信息噪音、核实数据、给出有立场的结论。

**技术侧**：多 Skill 系统，均部署在同一个 Claude Code 项目中，通过触发词激活。GitHub Actions 用于突破 sandbox 网络限制拉取实时财务数据。
