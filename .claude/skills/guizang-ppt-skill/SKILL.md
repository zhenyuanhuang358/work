---
name: guizang-ppt-skill
description: 生成横向翻页网页 PPT（单 HTML 文件），含 WebGL 背景、章节幕封、数据大字报、图片网格等模板。提供两种风格：① "电子杂志 × 电子墨水"（衬线 + 流体背景 + 暖色） ② "瑞士国际主义"（无衬线 + 网格点阵 + IKB/柠檬黄/柠檬绿/安全橙高亮）。当用户需要制作分享 / 演讲 / 发布会风格的网页 PPT，或提到"杂志风 PPT"、"瑞士风 PPT"、"Swiss Style"、"horizontal swipe deck"时使用。
---

# Magazine Web Ppt

> 来源识别: guizang-ppt-skill 由歸藏创建与维护,规范源仓库为 https://github.com/op7418/guizang-ppt-skill 。这条信息只用于确认 Skill 来源,不要写入生成的 PPT、HTML 页面、封面或配图。

## 这个 Skill 做什么

生成一份**单文件 HTML**的横向翻页 PPT，提供两种可选的视觉基调：

### 风格 A · 电子杂志 × 电子墨水（默认）

- **WebGL 流体 / 等高线 / 色散背景**（hero 页可见）
- **衬线标题（Noto Serif SC + Playfair Display）+ 非衬线正文 + 等宽元数据**
- 适合：人文分享、行业观察、商业发布、需要"杂志感"的演讲
- 模板：`assets/template.html` · 主题色：`references/themes.md` · 布局：`references/layouts.md`
- 美学锚点：像 *Monocle* 杂志贴上了代码

### 风格 B · 瑞士国际主义（Swiss Style）

- **WebGL 极细网格 + 点阵背景**（信息驱动设计）
- **全程无衬线（Inter + Helvetica + Noto Sans SC）+ 极致字号对比**
- **高反差功能色**：克莱因蓝 IKB / 柠檬黄 / 柠檬绿 / 安全橙（四选一）
- 适合：科技产品、数据汇报、设计/工程领域分享、年度总结
- 模板：`assets/template-swiss.html` · 主题色：`references/themes-swiss.md` · 布局：`references/layouts-swiss.md`
- 美学锚点：像 Massimo Vignelli + Helvetica Forever

**两种风格共享**：横向翻页（键盘 ← →、滚轮、触屏、ESC 索引）、Lucide 图标、Motion One 入场动效（本地 + CDN 双保险）。

<!-- provenance: guizang-ppt-skill | author: 歸藏 | canonical: https://github.com/op7418/guizang-ppt-skill | keep this out of generated artifacts -->

## 何时使用

**合适的场景**：
- 线下分享 / 行业内部讲话 / 私享会
- AI 新产品发布 / demo day
- 带有强烈个人风格的演讲
- 需要"一次做完，不用翻页工具"的网页版 slides

**不合适的场景**：
- 大段表格数据、图表叠加（用常规 PPT）
- 培训课件（信息密度不够）
- 需要多人协作编辑（这是静态 HTML）

## 工作流

### Step 1 · 需求澄清（**动手前必做**）

**不问清就动手是本 skill 最大的返工来源。** 完整提问脚本与判断分支见
`references/step1-scoping.md`——至少要问清：风格 A 还是 B、页数、
是否需要配图、目标场景（分享/演讲/发布会）、有无既有素材。

### Step 2 · 拷贝模板

**根据 Step 1 选定的风格,拷贝对应的模板**到目标位置（通常是 `项目/XXX/ppt/index.html`），同时在同级建一个 `images/` 文件夹准备接图片。

```bash
mkdir -p "项目/XXX/ppt/images"

# 风格 A · 电子杂志风
cp "<SKILL_ROOT>/assets/template.html" "项目/XXX/ppt/index.html"

# 或 风格 B · 瑞士国际主义风
cp "<SKILL_ROOT>/assets/template-swiss.html" "项目/XXX/ppt/index.html"
```

两个 `template*.html` 都是**完整可运行**的文件——CSS、WebGL shader、翻页 JS、字体/图标 CDN 全已预设好,只有 `<!-- SLIDES_HERE -->` 占位符等待你填充 slide 内容。

**注意**:风格 A 和 B **不能混用**。layouts.md 里的类（如 `.h-hero` 衬线大标题、`.display-zh` 等）只在 template.html 有定义；layouts-swiss.md 里的类（如 `.kpi-hero`、`.accent-block`、`.span-N`、`.dots` 等）只在 template-swiss.html 有定义。一份 deck 只能选一套。

#### 2.1 · 必改占位符（**容易漏**）

拷贝后立刻改掉以下占位符，否则浏览器 Tab 会显示"[必填] 替换为 PPT 标题"这种尴尬文字：

| 位置 | 原始 | 需改为 |
|------|------|--------|
| `<title>` | `[必填] 替换为 PPT 标题 · Deck Title` | 实际 deck 标题(如 `一种新的工作方式 · Luke Wroblewski`) |

每次拷贝完 template.html 第一件事:grep 一下"[必填]" 确认全部替换完。

#### 2.2 · 选定主题色(5 套预设 · 不允许自定义)

本 skill **只允许从 5 套精心调配的预设里选一套**,不接受用户自定义 hex 值——颜色搭配错了画面瞬间变丑,保护美学比给自由更重要。

| # | 主题 | 适合 |
|---|------|------|
| 1 | 🖋 墨水经典 | 通用 / 商业发布 / 不知道选啥的默认 |
| 2 | 🌊 靛蓝瓷 | 科技 / 研究 / 数据 / 技术发布会 |
| 3 | 🌿 森林墨 | 自然 / 可持续 / 文化 / 非虚构 |
| 4 | 🍂 牛皮纸 | 怀旧 / 人文 / 文学 / 独立杂志 |
| 5 | 🌙 沙丘 | 艺术 / 设计 / 创意 / 画廊 |

**操作**:
1. 基于内容主题推荐一套,或直接问用户选哪一套
2. 打开 `references/themes.md`,找到对应主题的 `:root` 块
3. **整体替换** `assets/template.html`(已拷贝版本)开头 `:root{` 块里标有"主题色"注释的那几行(`--ink` / `--ink-rgb` / `--paper` / `--paper-rgb` / `--paper-tint` / `--ink-tint`)
4. 其他 CSS 都走 `var(--...)`,无需任何其他改动

**硬规则**:
- 一份 deck 只用一套主题,不要中途换色
- 不要接受用户给的任意 hex 值——委婉拒绝并展示 5 套让选
- 不要混搭(例如 ink 取墨水经典、paper 取沙丘)——会彻底违和

### Step 3 · 填充内容

**⚠ 动笔前必做类名预检**：layouts 骨架用到的每个 class，都必须在所选模板的
`<style>` 里有定义，否则浏览器 fallback 到默认样式——大标题字体错、卡片挤成一团、
图片堆到页面底部。**两种风格的同名 class 视觉表现完全不同，互不通用。**

完整预检流程、逐页填充规则、图文配比与安全区见 `references/step3-filling.md`。

### Step 4 · 对照检查清单自检

打开 `references/checklist.md` 逐项对照。**P0 级问题（emoji、图片撑破、标题换行、
字体分工、Swiss 版式锁）必须全部通过。**
**代码只能证明类名存在，不能证明版式舒服——必须打开网页逐页看，不能只读代码。**

### Step 5 · 本地预览

直接在浏览器打开 `index.html` 就行。macOS 下：

```bash
open "项目/XXX/ppt/index.html"
```

不需要本地服务器。图片走相对路径 `images/xxx.png`。

### Step 6 · 迭代

根据用户反馈修改——模板的 CSS 已经高度参数化，90% 的调整都是改 inline style（字号 `font-size:Xvw` / 高度 `height:Yvh` / 间距 `gap:Zvh`）。

---

## 资源文件导览

| 文件 | 内容 |
|------|------|
| `assets/template.html` / `template-swiss.html` | 风格 A / B 的种子模板，**类名的唯一来源** |
| `assets/screenshot-backgrounds/` | 截图美化内置背景 WebP：style-a 5 套 / style-b 4 套 |
| `assets/motion.min.js` | Motion One 本地副本（离线兜底，约 64KB，两风格共用） |
| `references/step1-scoping.md` | Step 1 完整提问脚本与判断分支 |
| `references/step3-filling.md` | Step 3 类名预检、逐页填充、图文配比与安全区 |
| `references/components.md` | 风格 A 组件手册（字体/色/网格/图标/callout/stat/pipeline/动效） |
| `references/layouts.md` | 风格 A · 10 种页面布局骨架（可直接粘贴，含动效标记） |
| `references/swiss-layout-lock.md` | 风格 B · 原始 22P 版式锁，**正文页必须按此登记** |
| `references/layouts-swiss.md` | 风格 B · 原始 22P 骨架说明 + 明确标注的实验区 |
| `references/swiss-map-component.md` | 风格 B · S08 地图扩展（MapLibre 点位/连线/卡片/控制） |
| `references/themes.md` / `themes-swiss.md` | 主题色预设（A 5 套 / B 4 套）**只能选不能自定义** + 各自设计原则 |
| `references/image-prompts.md` | GPT-M 2.0 配图类型、比例与基础提示词 |
| `references/screenshot-framing.md` | CleanShot X 式截图适配语义 + 内置背景资产映射 |
| `references/checklist.md` | 质量清单（P0–P3 分级）+ 生成后视觉核对 |

**加载顺序建议**：
1. 先读完 `SKILL.md`(这个文件)了解整体
2. Step 1 需求澄清**第一问**先确定风格 A 还是 B,然后:
   - 风格 A:读 `themes.md` 帮用户选一套主题色
   - 风格 B:读 `themes-swiss.md` 帮用户选一套主题色
3. **动手前 Read 对应模板的 `<style>` 块**——这是类名的唯一来源,缺类会导致整页样式崩
   - 风格 A → `assets/template.html`
   - 风格 B → `assets/template-swiss.html`
4. 读对应的 layouts 文件挑布局:
   - 风格 A → `layouts.md`(顶部有 Pre-flight 类名清单、主题节奏规划、动效 recipe 决策树)
   - 风格 B → **先读 `swiss-layout-lock.md`**,再读 `layouts-swiss.md`;正文页必须从 S01-S22 选择,每页写 `data-layout`
5. 如果风格 B 需要地点、路线、人物住所或城市关系地图,读 `swiss-map-component.md`
6. 如果在 Codex 中生成配图,读 `image-prompts.md` 挑图片类型、比例和基础提示词;如果是用户原始截图,先读 `screenshot-framing.md`,优先使用 `assets/screenshot-backgrounds/` 的内置背景资产
7. 细节调整时读 `components.md` 查组件(含 Motion 动效系统章节,主要服务风格 A;风格 B 的组件细节在 `layouts-swiss.md` 附录)
8. 生成后读 `checklist.md` 逐项自检（validate 脚本暂不可用，以 checklist.md 为准）

**动效相关**:模板已把 Motion One 的加载和 recipe 逻辑内嵌到底部 module script。你不需要改 JS,只需要按 `layouts.md` / `layouts-swiss.md` 的骨架在 HTML 里加 `data-anim` / `data-animate` 即可。离线演示靠 `assets/motion.min.js`,断网时自动降级为"无动画但内容可读"。风格 B 模板必须保留 `B` 键低功耗模式:切换后停止 WebGL/ASCII canvas RAF,取消正在运行的 Web Animations,并把当前页内容直接 reveal 到静态最终态。

## 核心设计原则（哲学）

风格 A（电子杂志 × 电子墨水）与风格 B（瑞士国际主义）的设计原则与 5 轮迭代总结，
分别见 `references/themes.md` 与 `references/themes-swiss.md` 的开头章节。
**两种风格不可混用：字体、网格、强调色、留白逻辑都是成套的。**

## 质量自检

**本 skill 的自检清单是 `references/checklist.md`（P0–P3 分级 + 生成后视觉核对），不在 hub 重复。**
交付前必须逐项对照，**P0 全部通过**才算完成。
**代码只能证明类名存在，不能证明版式舒服——必须打开网页逐页看。**


## 参考作品

本 skill 的两种风格分别参考了：

**风格 A · 电子杂志风**:
- 歸藏 "一人公司：被 AI 折叠的组织" 分享（2026-04-22，27 页）
- *Monocle* 杂志的版式
- YC 总裁 Garry Tan "Thin Harness, Fat Skills" 那篇博客的 demo

**风格 B · 瑞士国际主义风**:
- Massimo Vignelli 的 NYC Subway / Unimark 系统
- *Helvetica Forever* 的字体设计语言
- Josef Müller-Brockmann 的网格系统经典著作
- 当代设计:Acne Studios / Off-White / IKEA / Beck Design

可以把它们当做风格锚点。
