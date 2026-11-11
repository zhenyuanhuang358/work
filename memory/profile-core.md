# 用户档案 · 核心（每个会话必读的只有这一份）

> 2026-11-10 起：必读从 `profile.md`（86 KB，约 4–5 万 token）改为本文件。`profile.md` 是完整档案，内容没有删，
> **按需读**：用下面的索引找到编号，再 `grep -n "### 1.1y" memory/profile.md` 定位那一节。新教训仍追加到 `profile.md`，并在本文件索引里加一行。

## 用户要什么

- 产品：连锁餐饮 + 金融投资的多智能体决策工具集。是有立场的决策 Copilot，不是聊天机器人或知识库。
- 指令极简（「今日期权」「earner 味千中国」），直接执行到底，一次交付完整，不分批、不问「要不要继续」。
- 错了就承认并立即改；被打断说明方向错了，停下来想清楚再做，并说明调整了什么。
- 工作原则、路由、预测登记、Critic 门控都在 `CLAUDE.md`；当前状态和硬约束在 `memory/state/handoff.md`。
- 用量有限（2026-11-10）：一件事开一个新会话；能用工具和程序检查解决的，不靠多轮评审。

## 交付规范

- 视觉：IM Fell English + Songti SC；ink #0a0a0b / paper #f1efea / copper #8b6c42 / gold #c9a84c；绿 #2a5c3f / 红 #8b2e2e / 琥珀 #c47a1e。
- 信息密度高，不留无意义空白；数据用原生 SVG 图表；关键数字大字呈现；裁决框深色底。中文为主、英文为辅。
- HTML 报告零 Markdown 符号；必有反馈链接 `https://spontaneous-youtiao-b9cde9.netlify.app?product=…&report=…`；手机看文件，HTML 必须同时给 PDF（1.1zb）。
- 答案前置：先给结论，不写自证过程（1.1d）。

## 数据规则

- 每个关键数字带来源和日期；没有来源不可用。搜索摘要不是来源，关键事实看原文（1.1y）。
- 会话环境打不开的站点一律走 GitHub Actions 取数（见 `AGENTS.md` §5）；价格读工作分支的 `stock_prices.json`，不读 main（1.1f）。
- 数据缺口默认做信息拼接推测并标【推测】，不留空（R-D6）；客户提纲类报告的推测值交付单值（R-R6）。
- 没有实测 IV 不产出任何定价数字（1.1x）；会变的数不写成常量（1.1n）。
- 分部加总不等于总额时，交付物里写明差额（1.1s）。

## 执行规则

- 修 bug、做检查：先读全相关文件，列全问题，一次改完（R-E1 / R-E2）。
- 改了 skill 要验证 spoke 路径存在（R-E3），跑 `python3 tools/skill_index.py --check`。
- 只推 `claude/install-claude-hud-d51E6`（R-E4）。
- 规则要有承载物（工具、检查或测试）才算立住（1.2a）；检查器要建在真实产物上（1.2m）；记分由机器做（1.2c）。
- 动手前：先唱反调、先审会翻转结论的假设、说清完成线和上限（CLAUDE.md 工作原则 6–9，2026-11-11）。
- 撤销验证：改测试相关代码后，先撤掉修复确认测试会失败（`PYTHONDONTWRITEBYTECODE=1`，清 `__pycache__`）。

## 配置速查

| 项 | 值 |
|---|---|
| 工作分支 | `claude/install-claude-hud-d51E6`（也是默认分支） |
| 密钥 | 只在 GitHub Secrets：`FINNHUB_TOKEN`、`ANTHROPIC_API_KEY`、`TYPESAFE_API_KEY` |
| 报告目录 | `reports/`，生成脚本在 `reports/src/` |
| 期权账户 | 金额与持仓以 `memory/state/options-journal.md` 最新记录为准（`profile.md` 里的 $8,500 已过时） |

## 完整档案索引（`profile.md`，按主题找编号再 grep）

| 主题 | 编号 |
|---|---|
| 数据质量、来源、403 分诊 | 1.1、1.1b、1.1y、1.1u、1.1v |
| 报告与客户交付 | 1.1d、1.2（报告遗漏）、1.1q、1.1r、1.1s、1.1za、1.1zb、R-R1–R6 |
| 期权：张数、止损、保证金、IV | 1.1e、1.1g、1.1i、1.1k、1.1l、1.1m、1.1t、1.1w、1.1x、1.1z、1.1zc、1.1zd、1.2p、1.2r |
| 阈值与指标设计 | 1.1h、1.1n、1.1o、1.1p、1.2b、1.2f |
| 餐饮调研口径 | 1.1j |
| Bug、CSS、上下文压缩、Actions、交叉引用 | 1.3、1.3b、1.4、1.5、1.6、1.7、R-C1–C4 |
| 路由（提纲走 Merlin 等） | R-E6（以 CLAUDE.md 路由表为准） |
| 元规则：承载物、自评偏差、记忆压缩、第三方 skill、检查器 | 1.2a–1.2o |
| 产品背景（各模块细节） | 第五节 |
