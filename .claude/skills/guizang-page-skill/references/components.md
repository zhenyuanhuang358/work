# 组件参考

归藏 Page 的所有可用组件。每个组件在两种风格下有不同的视觉表现。

## 页面级组件

### doc-chrome（文档顶栏）

自动从 `meta` 和 frontmatter 生成。

| 风格 | 表现 |
|------|------|
| Magazine | mono 字体 bar + 2px 粗线 + meta row + 描边标签 |
| Swiss | 灰色背景卡片 bar + meta row + 黑底白字标签 |

### hero（主标题区）

| 风格 | 表现 |
|------|------|
| Magazine | 全宽标题+副标题，纯文字 |
| Swiss | **全宽底图卡片**：图片 darken 至 25% + luminosity 混合 + 网格点阵 overlay + 文字叠加在底部 |

`meta.hero_image` 控制图片来源。默认使用 Unsplash 抽象照片。

### TOC sidebar（目录侧边栏）

两种风格都有。左上角按钮，默认收起，点击展开（宽屏推开正文，窄屏是抽屉）。自带 scroll spy 高亮当前章节。

### section-header（章节标题）

| 风格 | 表现 |
|------|------|
| Magazine | 居中「✦✦✦ 04 ✦✦✦」花饰编号 + 居中衬线标题，分两行 |
| Swiss | 节首 2px 墨色粗线；44px 细体浅灰编号挂在左轨，与无衬线标题基线对齐 |

## 内容升格组件

### pullquote（大字引用）

**触发**：独立强判断句，整段只有一句话，观点性结论。

| 风格 | 表现 |
|------|------|
| Magazine | 上下 1px 细线包围，衬线大字 |
| Swiss | 顶部 2px 墨色线 + 左轨 QUOTE 标签 + 2rem weight-300 无衬线大字，`accent` 关键词用小字强调色加粗 |

`accent` 字段可指定一个关键词，渲染为 accent 色。

### highlight（高亮卡片）

**触发**：核心定义、原则、一句话总结。

| 风格 | 表现 |
|------|------|
| Magazine | 墨色底全宽色块 + 交叉线纹理 + 纸色字 + 底部 attr 标签（深色主题下反过来是浅底深字） |
| Swiss | 强调色满底色块 + 左侧 mono 标签 + 正文；色块上的文字色由主题决定（黄、绿、橙上是墨色，蓝上是白色） |

### def-card（术语定义卡片）

**触发**：`> **Term**：definition` 格式。

| 风格 | 表现 |
|------|------|
| Magazine | 堆叠式：灰底卡片 + 左 accent 边线 + label/term/body 三行 |
| Swiss | **左右分栏 3:9**：左列术语 + accent 标签，右列释义，灰底卡片，无边线 |

### gallery（图片画廊）

**触发**：3+ 个并列的同类案例/示例。

| 风格 | 表现 |
|------|------|
| Magazine | 横向滚动 scroll-snap，280px 宽卡片 |
| Swiss | **2×2 网格平铺**，全宽 |

### process（流程步骤）

**触发**：有序步骤 1→2→3。

| 风格 | 表现 |
|------|------|
| Magazine | 左编号 + 右标题描述，步骤间 hairline |
| Swiss | **灰底卡片列表**，蓝色编号，卡片间 8px 间距，无线条 |

### checklist（约束列表）

**触发**：否定性或约束性规则列表。

| 风格 | 表现 |
|------|------|
| Magazine | 方框描边 checkbox |
| Swiss | 强调色淡底方块 + 小字强调色勾号 |

### big-number（大数字）

**触发**：预留，渲染器暂不生成。

| 风格 | 表现 |
|------|------|
| Magazine | 描边卡片，黑字 |
| Swiss | 强调色满底色块 |

## 解释模式专用组件

### figure（配图）

从 Unsplash 或其他来源引入的解释性配图。

```json
{ "type": "figure", "line": 35, "src": "https://...", "alt": "描述", "caption": "图注" }
```

渲染为全宽图片 + 底部 mono 字体 caption。

### embed（嵌入式预览）

AI 生成的 SVG 信息图、UI 预览、示意图。

```json
{ "type": "embed", "line": 30, "label": "Overview", "svg": "<svg>...</svg>", "caption": "说明" }
```

渲染为：黑底标签 + 灰底展示区 + 底部 caption。SVG 必须纯内联，viewBox 宽度 600-720。

### aside（补充提示）

AI 提炼的实践建议、参数速查、工程提示。

```json
{ "type": "aside", "line": 46, "title": "实践提示", "text": "CSS 中用 `transform: scaleY()`..." }
```

渲染为：灰底卡片 + 💡 图标 + accent 标题 + 正文。

### summary-card（速查卡）

全文总结或知识点网格。

```json
{
  "type": "summary-card", "line": 241, "label": "速查卡",
  "items": [{ "title": "名称", "desc": "描述" }]
}
```

渲染为：黑底标签 + auto-fill 网格卡片（每卡 220px 最小宽度）。

## 表格、代码块和图表

### table（Markdown 竖线表格）

自动识别 `| col | col |` 格式的 Markdown 表格，解析为 HTML `<table>`。

| 风格 | 表现 |
|------|------|
| Magazine | 书籍三线表：无衬线小号表头，上下墨色线，行间细线 |
| Swiss | 透明表头 + 墨色粗线，细行线，隔行极浅底；纯数字列右对齐、等宽数字 |

### table（HTML 表格 pass-through）

源文档中的 `<table>...</table>` HTML 标签直接透传，包裹在 `.table-wrap` 容器中获得主题样式。支持单行和多行 HTML 表格。

### code block（代码块）

自动识别 ` ``` ` 围栏代码块，渲染为深色底 `<pre><code>`。

| 风格 | 表现 |
|------|------|
| Magazine | 近黑底 + 暖灰白字 + 微圆角 3px + mono 字体 |
| Swiss | 近黑底 + 冷灰白字 + 直角 + mono 字体 |

内联 `code` 用灰色背景 + 小字号渲染。

### section-footnote（脚注区）

标题匹配 `Footnote`、`脚注`、`注释` 的 section 自动获得 `section-footnote` class。

| 风格 | 表现 |
|------|------|
| Magazine | 上方 1px 浅色分割线 + 小字 0.8rem + 次级灰色 + 加粗标题保持主色 |
| Swiss | 上方 1px `--bg-card` 分割线 + 小字 0.8rem + muted 灰色 |

### chart（原生条形图）

在 Markdown 里写 ` ```chart ` 代码块触发，纯 HTML/CSS，不加载外部脚本，可导出 PDF / 长图。格式见 SKILL.md「自动渲染的元素」。配色跟主题走：高亮项用强调色，其余为墨色浅灰。

## 布局

12 列网格，1200px 宽，左右 80px margin。

| 内容类型 | 列跨度 |
|----------|--------|
| 正文/列表/def-card | col 2–12（10 列） |
| 全宽组件（highlight/gallery/pullquote/big-number/chart） | col 1–12 |
| 章节编号（Magazine 模式） | col 1–2 |
| 章节编号（Swiss 模式） | 与标题同一行 |
