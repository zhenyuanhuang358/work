# 调研报告 HTML 生成规范

每次调研完成后，**必须**生成 HTML 版本并用 Write 工具保存到 `reports/` 目录。
文件名格式：`reports/[品牌缩写]_research_[YYYY].html`

---

## 视觉规范（与 earner 报告统一）

| 元素 | 规范 |
|------|------|
| 字体 | `'IM Fell English'`（英文衬线）+ `'Songti SC','STSong','SimSun',Georgia,serif`（中文衬线） |
| 主色板 | ink `#0a0a0b` / paper `#f1efea` / copper `#8b6c42` / gold `#c9a84c` |
| 正面数据 | `--green: #2a5c3f` |
| 负面数据 | `--red: #8b2e2e` |
| 警示/估算 | `--amber: #c47a1e` |
| 辅助色 | muted `#6b6460` / border `#d4cec6` / card `#faf8f4` |
| SVG 图表 | 纯原生 SVG，零外部库，图表内声明 `font-family='IM Fell English',Georgia,serif` |
| 零 Markdown | 报告正文不得出现 `*` `**` `#` 等符号，格式全用 HTML/CSS |

---

## 固定 Section 顺序

1. **Pub Bar**：品牌 · 调研类型 · 日期 · 客户标识
2. **双语标题**：中文大标 + 英文副标 + 标签行（上市状态 / 数据质量 / 行业类别）
3. **Stat Bar**：4 格关键指标（最重要的 4 个数字）
4. **数据质量声明**（amber 左边框 notice 块，说明哪些是一手、哪些是推断）
5. **核心数据表**（严格按客户提纲顺序）
6. **SVG 图表区**（见下方规则）
7. **数据详解**（拆分卡片，detail-grid 双列）
8. **执行摘要裁决框**（深色底，3 条判断，每条有数据依据）
9. **数据缺口补全建议**（表格，列出路径和可得性评级）
10. **来源索引**
11. **Footer**

---

## 数据徽章（badge）规则

| 情况 | 徽章样式 | CSS class |
|------|---------|-----------|
| 来自财报/公告（一手） | 绿底白字 `官方` | `badge-official` |
| 分析预测/推断 | 琥珀底白字 `预测` | `badge-predict` |
| 数据缺口 | 红底白字 `缺口` | `badge-gap` |

徽章写在数值后面，inline 内嵌，不单独成行。

---

## SVG 图表生成规则

**什么数据必须图表化（不得纯文字）：**

| 数据类型 | 图表类型 |
|---------|---------|
| 年度营收 / 利润趋势（≥2年） | 竖向柱状图（最多显示 5 年） |
| 分部收入拆分（≥3项） | 横向条形图（含同比标注） |
| 多品牌 / 多景区客流对比 | 横向条形图（含区间带） |
| 入园人次 / 门店数趋势 | 竖向柱状图或折线 |
| 市场份额 | 横向条形图（不用饼图） |

**图表通用规范：**
- viewBox 宽度 800（单图）或 360（双列）
- 背景色用 `var(--card)` 的外层 `chart-wrap` div 包裹
- 轴线用 `#d4cec6`，虚线网格用 `stroke-dasharray="4,3"`
- 数值标注在 bar 右侧固定列位（不要跟随 bar 宽度），防止重叠
- 下降值标红（`#8b2e2e`），上升标绿（`#2a5c3f`），估算标琥珀（`#c47a1e`）
- 图表内所有文字 font-size ≤ 12，轴标签 ≤ 10

---

## CSS 骨架（每次复用，不重新发明）

```css
:root {
  --ink:#0a0a0b; --paper:#f1efea; --copper:#8b6c42; --gold:#c9a84c;
  --green:#2a5c3f; --red:#8b2e2e; --amber:#c47a1e;
  --muted:#6b6460; --border:#d4cec6; --card:#faf8f4;
}
body { background:var(--paper); color:var(--ink);
  font-family:'Songti SC','STSong','SimSun',Georgia,serif;
  font-size:15px; line-height:1.75; max-width:1000px; margin:0 auto; padding:0 24px 72px; }

/* pub-bar / title-block / stat-bar / section / notice /
   table / badge / chart-wrap / detail-grid / dcard /
   verdict / footer  — 参见 reports/theme_park_research_2025.html */
```

完整 CSS 参照 `reports/theme_park_research_2025.html`（已是标准实现，直接复用）。

---

## 执行摘要（裁决框）写法

```html
<div class="verdict">
  <div class="v-en">Research Verdict · Executive Summary</div>
  <div class="v-zh">执行摘要：[N]条关键判断</div>
  <div class="v-item">
    <div class="v-num">1</div>
    <div class="v-text">
      <strong>[核心判断，一句话点题]</strong>
      [2-3句支撑，引用具体数字]
      <span style="color:var(--gold);font-size:11px;display:block;margin-top:4px;">
        依据：[数据来源，一句话]
      </span>
    </div>
  </div>
  <!-- 重复 2-3 条 -->
</div>
```

**禁止**在判断里写「整体平稳」「竞争激烈」「有待观察」等无信息量表述。

---

## 数据缺口补全建议表（固定格式）

```html
<table>
  <thead><tr>
    <th>缺口项</th><th>推荐补数路径</th><th>预计可得性</th>
  </tr></thead>
  <tbody>
    <tr>
      <td>[缺口数据名]</td>
      <td>[具体路径，如 IR邮箱 / TEA报告 / 访谈]</td>
      <td><span style="color:var(--green);">较高</span> 或
          <span style="color:var(--amber);">中等</span> 或
          <span style="color:var(--red);">较低</span></td>
    </tr>
  </tbody>
</table>
```

---

## 文件保存

```
报告保存路径：reports/[slug]_research_[YYYY].html
slug 规则：品牌名拼音缩写或英文缩写，小写，下划线连接
示例：chimelong_haichang_research_2025.html
     haidilao_research_2025.html
     luckin_research_2025.html
```

生成后用 `SendUserFile` 推送给用户。
