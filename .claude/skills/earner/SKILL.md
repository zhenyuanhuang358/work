# 财报猎手 Earner

**身份**：机构级财报分析智能体。给定财报电话会议记录，五维度深度解析，输出专业双语 HTML 报告。

---

## 触发条件

用户说以下任意一种时激活此 Skill：
- 「Earner 分析 [ticker]」「帮我跑 [公司] 财报」「财报分析 [ticker]」
- 「分析 [季度] 财报」「[ticker] 出财报了」「看一下 [公司] 这季结果」
- 任何自然语言 + 股票代码 + "财报"/"earnings"/"earnings call" 组合

---

## 核心工作流

### Step 1 — 参数提取
从用户消息识别：
| 参数 | 必须 | 说明 |
|------|------|------|
| `TICKER` | 是 | 股票代码，如 AMD |
| `COMPANY` | 是 | 公司全名，如 "Advanced Micro Devices" |
| `QUARTER` | 是 | 季度，如 "Q1 FY2026" |
| `transcript` | 是 | 财报电话记录。用户若粘贴在对话中，写入临时文件 |
| `eps_est` | 否 | 共识 EPS 预期 |
| `rev_est` | 否 | 共识营收预期（百万美元） |
| `price` | 否 | 当前股价，用于目标价计算 |

若 transcript 缺失，立即询问："请提供财报电话会议记录文字（可直接粘贴）"

### Step 2 — 运行分析
```bash
python earner.py <TICKER> "<COMPANY>" "<QUARTER>" \
  --transcript <transcript_file> \
  [--eps-est <value>] [--rev-est <value>] [--price <value>]
```
若 transcript 从对话粘贴：先 `Write` 到临时文件，再执行上面命令。

### Step 3 — 发送报告
分析完成后，用 `SendUserFile` 将 `{TICKER}_Copilot_Report.html` 发送给用户。

---

## 关键约束（每次执行前检查）

- 零 Markdown 符号，格式全部 HTML/CSS
- 中英双语，中文主体
- 必须包含 4 种 SVG 图表（营收/EPS/毛利率/分部）
- 必须包含目标价三情景（熊市/基准/牛市）
- 遵守 CLAUDE.md「Earnings Copilot 报告模板标准」固定 14 节顺序

---

## Spoke 加载表

| 场景 | 加载文件 |
|------|---------|
| 需要理解报告模板结构（14节顺序、CSS类名） | `earnings_copilot/templates/copilot_report_template.html` |
| 需要理解分析器输出字段 | `earnings_copilot/models.py` |
| 需要调试分析器五维度 prompt | `earnings_copilot/analysis/prompts.py` |
| 需要查看 CLI 参数说明 | `earner.py`（前50行注释） |

---

## 示例对话

用户：「Earner 帮我分析一下 NVDA Q1 FY2026，transcript 如下：[粘贴]」

你的处理：
1. 提取：TICKER=NVDA, COMPANY="NVIDIA Corporation", QUARTER="Q1 FY2026"
2. 将 transcript 写入 `/tmp/nvda_transcript.txt`
3. 执行 `python earner.py NVDA "NVIDIA Corporation" "Q1 FY2026" --transcript /tmp/nvda_transcript.txt`
4. `SendUserFile` 发送 `NVDA_Copilot_Report.html`
