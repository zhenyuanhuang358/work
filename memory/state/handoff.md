# 会话交接（2026-10-21）

新窗口开场说：「读 memory/state/handoff.md，接着干」。CLAUDE.md 与 profile.md 会自动加载，本文件只记**进行中的事**和**不在仓库规则里的约定**。

## 一、期权账户（最要紧）

- **现状**：净值约 $6,000，**无持仓**。GM 79P（−$448）、INTC 104P×5（约 −$5,150）均已平仓。最后一张 INTC 成交价用户未给。
- **新规则（已写进 us-options-agent，扫描时自动执行）**：
  - `references/position-discipline.md`：存量违规先处理、不出新候选；持有硬线（z ≥1.0 持有 / 0.8–1.0 减半 / <0.8 或 2× 收入全平）；接货 > 净值默认用价差；近 10 日有增发/减持/指引下调只观察。
  - `references/macro-events.md`：FOMC 10/28、12/09；CPI 11/10、12/10；PPI 11/13、12/15。持有期含事件 z 门槛 1.2，事件前一交易日不新开。
  - 价差门槛：净收/宽度 ≥ HV 到期价内概率 + 3pct，最大亏损 ≤ 净值 5%（约 $300）→ `python3 tools/spread_check.py`。
  - 开仓前必问两句：止损条件单挂好了吗？张数按 5% 算了吗？只做 1 张。
- **近期待办**：10/27（FOMC 前一日）不新开；GM 财报后（10/20 −6%）观察是否企稳；10/19–10/20 SPY/XLE 价差都没过新门槛。
- **环境坑**：容器重启后仓库可能是浅克隆，价格历史只剩几天 → 先 `git fetch --unshallow origin claude/install-claude-hud-d51E6`。
- 预测记分：predictions.md 里 2026-09-25 期限溢价那条仍待记分（另一分支已记 ◐）。

## 二、客户文章 · 海底捞 2026-10

- 交付件：`reports/haidilao_article_202610.html/.txt`（第一人称，已融入用户 7 条一线判断，已去多余符号）。
- **客户有 AI 审查，问「是不是您自己写的」。约定：不帮绕过 AI 检测**；建议用户按提纲亲笔重写，或如实告知「观点是我的，整理用了工具」。用户口述的判断：8 月月底下滑是开学、店长从主动赚钱变被动过日子、中产客流失、翻台靠产品与品牌运营、主品牌停滞靠副品牌突破、房租已到底、人工靠机器人省。

## 三、简历

- Kami 版（2 页）源文件：`memory/state/resume/content.json`（手机号已替换为 `{{手机号}}`）+ `fill.py`。
  重建：`bash tools/setup_kami.sh` → 复制 Kami resume 模板 → `python3 memory/state/resume/fill.py content.json`（先把手机号填回）→ `python3 .claude/skills/kami/scripts/build.py --deliver resume.html content.json`。
- 时间线：海底捞 2010.02–2019.12（华南大区运营官 **2016**–2019，**起始年份待用户确认**）→ 长隆 2020.01–2023.02 → 绿茶 2023.03 至今。
- **约定：不替用户编数字**；长隆数字全部来自用户（年均降本 34%、3.4 亿、200 人、1 万余家、淘汰 5,000 / 降级 2,000、60→15 天）。
- 可选下一步：用户有具体面试时，按 ai-job-search 的思路做面试准备包（简历数字一致性、按面试官身份预测问题、STAR 案例、模拟面试）。

## 四、其他未结事项

- 另一分支 `origin/claude/us-stock-opportunities-htj5ur`（用户权威 journal 9/22–9/30、profile 1.2q–1.2y）**尚未合并**，等用户同意。
- Kami 依赖与字体不随容器保留：用之前跑 `bash tools/setup_kami.sh`。
- 长隆携程景酒推算：`tools/chimelong_ctrip_estimate.py`（约 4.3 亿、YoY 约 +3%，已标推算）。
