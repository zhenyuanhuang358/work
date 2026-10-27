# 会话交接单（2026-10-27 · 第二版，替换 10-21 版）

> **新 Agent 开场必做**：① 读本文件 ② `git log -1` 对照下方 commit ③ `git status` 确认无未提交改动
> ④ 跑「已跑测试」里的命令复核结果 ⑤ 再动代码。**凡标「已做」的不要重做；标「计划」的才是待办。**

## 0. 基线

| 项 | 值 |
|---|---|
| 分支 | `claude/install-claude-hud-d51E6`（只在这里开发与推送；不开 PR，除非用户要求） |
| 交接时 HEAD | `d3429f5`（2026-10-27 14:47Z「journal：10/27 FOMC 前」）之后仅本交接单一个提交 |
| 未提交 diff | 无（交接时 `git status` 干净） |
| 容器坑 | 重启后可能是浅克隆 → `git fetch --unshallow origin claude/install-claude-hud-d51E6`，否则 `spread_check` / `candidate_ledger` 取不到价格历史 |
| Kami 依赖 | 不随容器保留 → 用前 `bash tools/setup_kami.sh` |
| 上一会话完整记录（索引用，不要只信摘要） | `/root/.claude/projects/-home-user-work/981d8078-2cc0-5e88-9987-9d6f23f45373.jsonl` |

## 1. 用户目标与硬约束（全部来自用户原话或已确认）

- 期权账户：净值约 **$6,074**（10/22 截图），融资账户；风控 73%「预警」、可取现金 $388（10/22）。
- **只做卖方**（用户 10/21 选「继续卖 put 收权利金」）；**选股不考虑资金能否覆盖、不考虑接货**，资金与风控只在选完后**提示**（用户多次强调，R4/R5 只提示不否决）。
- 每次扫描遵守 skill 内已写入的规则（见 §3「已做」）；红灯不新开；FOMC 前一交易日不新开。
- 客户文章与报告：**不帮绕过 AI 检测**（用户已接受）；文章体用第一人称、不放研究附注（profile 1.1za）；手机端交付 HTML 须附 PDF（profile 1.1zb）。
- 简历：**不替用户编数字**；所有数字来自用户。
- 合规红线：不披露海底捞（6862.HK）/ 绿茶（6831.HK）未公开经营数据；用户为前海底捞华南大区运营官（2016–2019）、现绿茶品牌运营总经理。

## 2. 期权：当前持仓与状态（已做）

| 持仓 | 开仓 | 止损 | 最近复核 |
|---|---|---|---|
| **UBER 261030 63P ×6** | 10/21 卖开 @0.18（建议 1 张，用户开 6） | 条件单 ≥ **0.36** 买回（用户 10/22 称「挂好了」，**未截图核验**） | 10/27 10:47 ET：UBER $65.91，缓冲 4.4%，z≈1.18，持有；约 $64.5–65 触发止损 |

- 已平仓历史：GM 79P×4（−$448）、INTC 104P×5（约 −$5,150，最后一张成交价**未提供**）、SGI 55P×3（+$89）。
- 闸门最近读数（10/27）：VIX 17.77 / 期限 0.905 / VVIX 99.6 / SKEW 151（常驻观察）→ 绿灯；期限溢价 1.105 < 1.20（30–45 天档关闭）。
- **10/28 14:00 ET FOMC**。

## 3. 已做 vs 计划（防重复）

### 已做（已提交，勿重做）
- us-options-agent：`references/position-discipline.md`（存量先于新仓、持有硬线、接货>净值默认价差、事件压力过滤）；`references/macro-events.md`（FOMC 10/28、12/09；CPI 11/10、12/10；PPI 11/13、12/15）；价差改期望值门槛（`tools/spread_check.py`，净收/宽度 ≥ HV 价内概率 + 3pct）；hub 197 行。
- `tools/candidate_ledger.py`（候选全量登记与到期结算）；`tools/self_check.py` C9。
- Critic：D1 摘要级来源三关、D2 口径可比性。Earner：Step 0「现价已经假设了什么」。
- Kami 技能已安装（`.claude/skills/kami`，CLAUDE.md 路由表已加）；`tools/setup_kami.sh`。
- 交付件（`reports/`）：`haidilao_article_202610.html/.txt`（第一人称版）、`haidilao_south_china_Research_Report.html`、`haidilao_ruyi_sushi_Research_Report.html`（两份 Merlin 报告的 PDF 已渲染并发给用户，PDF 被 .gitignore 忽略）、`江苏绿茶门店所在商场日均客流_v2.xlsx`、`tools/chimelong_ctrip_estimate.py`。
- 简历：Kami v2 定稿（长隆/海底捞各两张卡），源文件 `memory/state/resume/`（手机号为占位符）；用户 10/21 确认 2016 起任大区运营官与四处补充描述属实。
- profile 新增 1.1y / 1.1z / 1.1za / 1.1zb；predictions 新增海底捞 3 条、如鮨 1 条。

### 计划 / 待办（未做）
1. **10/29（FOMC 后）扫描**：先看 UBER 63P（10/30 到期）；新候选看 11/06 档。
2. **predictions.md 记分**（self_check P1，4 条逾期）：10/09 GM 79P 不被行权（已提前平仓→按登记规范判 ⊘ 或 ✗，先读规范第 1–10 条）；10/16 SGI 55P（提前平仓）；10/20 绿茶外卖增速（需查 2026 中报外卖增速再判）；9/25 期限溢价（另一分支已记 ◐）。
3. **统一止损规则**：strategy-catalog 写「亏损达 2× 权利金」（价格 3×），position-discipline 写「价格 ≥ 2× 收入」。用户 10/21 未明确答复；当前按后者执行。**改文件前先问用户。**
4. INTC 最后一张平仓价补记（待用户提供）。
5. 另一分支 `origin/claude/us-stock-opportunities-htj5ur` **未合并**，等用户同意。
6. 可选：用户有具体面试时做面试准备包（ai-job-search 思路，未安装该仓库）。

## 4. 已跑测试 / 检查及结果（交接时）

| 命令 | 结果 |
|---|---|
| `python3 tools/self_check.py` | 2 项：P1 predictions 4 条逾期待记分；P3 kami hub 210 行（第三方，不改） |
| `python3 tools/candidate_ledger.py report` | 83 条，已结算 55（价内 17 / 价外 38），独立簇 18 < 20 → 拒绝下结论（正常） |
| `python3 tools/spread_check.py …`（10/16、10/19、10/21 报价回放） | SPY 755/752 −7.6% ⛔；SPY 751/748（10/21）+4.8% ✅；GM 10/30 全链负优势 ⛔ |
| Kami `build.py --deliver resume.html content.json` | READY，2 页，字体 TsangerJinKai02 嵌入 |
| Critic | 华南、如鮨两份报告均 CONDITIONAL |

## 5. 已排除的路线（不要再提）

- 帮客户文章「去 AI 痕迹 / 过 AI 检测」——已拒绝，用户已接受。
- 替用户编简历数字——已拒绝；用户随后提供真实数字。
- INTC 远期 85P「回本」单——否决（跨财报、z 0.44、回本动机）。
- 安装 ai-job-search 全套 / knowledge-work-plugins / claude-quickstarts / agent-skills——评估后不装（只借了 validate-data 的口径可比性检查进 Critic）。
- GM 10/30 价差——流动性差，全链负优势。
- HOOD/SOFI 在 FOMC 窗口内——利率敏感只观察。

## 6. 记忆文件位置

`memory/profile.md`（教训）｜`memory/state/options-journal.md`（逐日持仓与扫描）｜`memory/state/options-candidates.jsonl`（候选账本）｜`memory/state/predictions.md`（预测记分）｜`memory/state/research-ledger.md`（研究台账）｜`memory/state/resume/`（简历源）
