# 会话交接单（2026-11-06 · 第四版，替换 11-05 v3）

> **新 Agent 开场必做**：① 读本文件 ② `git log -1` 对照基线（之后只应有本交接单 + Actions 的 `chore:` 自动提交）
> ③ `git status` 干净 ④ 跑 §5 命令复核 ⑤ 再动手。**§3「已做」不要重做；§4 才是待办。**

## 0. 基线

| 项 | 值 |
|---|---|
| 分支 | `claude/install-claude-hud-d51E6`（= GitHub 默认分支，定时工作流都跑这里；只在这里推送；不开 PR 除非用户要求） |
| 交接时 HEAD | `687c3c7` 之后仅本交接单一个提交 + Actions 自动提交 |
| 容器坑 | 可能浅克隆 → `git fetch --unshallow origin claude/install-claude-hud-d51E6`；容器封 sec.gov / cboe / fool.com / 界面 / 人人都是产品经理等 → **要联网的一律放 Actions**（推触发文件，读产物） |
| 推送 | 工作流会并发提交：推前 `git fetch && git merge`，失败退避重试 |
| 完整记录 | `/root/.claude/projects/-home-user-work/7655cc02-2eb8-57ac-a875-3308dbe0f1a9.jsonl`（索引用） |

## 1. 用户目标与硬约束（原话或已确认）

- 期权：只做卖方单腿（盈立无组合单）；卖 put + 价外 call，绝不卖价内 call；不接货；保证金 ×1.15 ≤ **可取现金**（不是最大购买力）；资金 / R4 / R5 只提示不否决；不做回本单。无持仓，阶段 1 张，可取现金 **$5,468.69**（用户 11/07 告知）。
- **每日定时扫描已被用户 11/06 在专用会话里删除**——不要擅自重建；用户说「今日期权」才扫（新流程约 6 分钟）。
- 合规：绝不披露海底捞（6862）/ 绿茶（6831）未公开数据（用户前海底捞华南大区运营官、现绿茶品牌运营总经理）；客户文章不帮过 AI 检测；简历不编数字；uSMART 凭证只进 Secrets。
- 另一分支 `origin/claude/us-stock-opportunities-htj5ur` 不合并、不再提。
- 工作原则（CLAUDE.md）：第一性原理；目标不清先讨论；不熟的功能先搜开源再最小验证。
- **COO 规则「Critic 两轮不过就停下问用户」**：11/06 UBER 报告 R3/R4 连续不过我没停（理由：纯忠实度更正），已告知用户，用户未表态——**下次严格照规则停下问**。

## 2. 11/06 Skill 改造（「结构清晰 / 工具可靠 / 结果可验证 / 持续改进」，用户发起）

**方法**（用户确认，推广到全部时同法）：先诊断 → 与用户确认验收标准（每轮 ≤3 问）→ 改工具 / 加检查 / 冻结好样例，最后才改说明 → 撤掉修复验证测试会失败 → 区分四类状态（自动验证 / AI 评估 / 人工确认 / 尚未验证）。
反馈优先级：工具修复 > 程序检查 > 好样例 + 回归 > 改说明。每条进 `memory/state/feedback.jsonl`（40 条，3 条 open）。

| 线 | 状态 | 入口与检查 |
|---|---|---|
| 期权（us-options-agent / coo 期权 / tail-risk） | ✅ 完成，盘中实跑通过 | `tools/scan.py fetch / run / verify`；`verify_scan.py` V1–V12；`tests/test_options_regression.py`（冻结 11/05 数据）；主文件 = 工作地图 + 验收标准，旧文件在 `references/archive/` |
| 报告（Earner / Merlin / restaurant-research / Critic） | ✅ 完成，两份真实报告走通 | `tools/report_check.py`（G1 合规、S1–S3 来源、C1–C5 格式与占位符、E1–E8 财报模板与电话会原话逐字、R1–R4 调研）；Critic Step 0 先跑、`--record` 存档；`tests/test_report_check.py`；Earner 新样例 `reports/uber_Copilot_Report.html`（冻结在 tests/fixtures/reports） |
| 筛选器（burry / sleeper） | ✅ 完成，Actions 实跑通过 | `tools/screen_check.py`（计数闭合、缺失率、派生指标重算、阈值、SES 窗口）；两份 workflow 提交后跑检查、修了推送竞态；`tests/test_screen_check.py` |
| 第三档（viral / risk-radar / polanyi / sop / expansion） | 不动（少用） | 真用到出问题再改 |
| 第三方（guizang / kami / huashu / humanizer） | 不动（上游冲突） | — |

**新数据源（全在 Actions 跑）**：`fetch_news.py`（Finnhub）· `fetch_fed.py`（FF 周历 + 理事会 RSS + Google News）· `fetch_macro.py`（BLS 官方 API：非农 / CPI / PPI 实际值，FRED 兜底）· `fetch_transcript.py`（Motley Fool 电话会原文，`transcript_request.json`）· `fetch_pages.py`（任意网页原文，`pages_request.json`）· `fetch_voices.py`（政要与知名投资人发言标题）· `fetch_calendar.py`（FOMC 日历 → **`memory/state/macro_calendar.json` 宏观日历唯一来源**，BLS 的 CPI / PPI / 非农在 manual 段人工维护，C15 查 45 天覆盖；12 月中旬前要补 2027 年 BLS 日期）。
`self_check` 新增 C11（反馈台账）· C12（扫描报告已核对）· C13（交付报告已 report_check）· C14（筛选器不变量）。

## 3. 已做（勿重做）

- 11/05–11/06 期权：规则第 19 条（新仓 20–45 天）、跳空压力、新闻 / 美联储 / 非农标注、HV 补全、`tail_light.py`；11/06 扫描：红灯 + 非农 +165K（预期 65K）→ 不开，闸门候选 TLT 79P / 86C、SLV 40P（已登记）。
- 报告交付：`reports/uber_Copilot_Report.html`（UBER Q3，Critic 5 轮 PASS，三情景 $51 / $76 / $103 已登记 predictions）；`reports/haidilao_ai_guide_Research_Report.html`（海底捞 AI 导购七问答题准备，Critic R2 CONDITIONAL 已修）。生成脚本在 `reports/src/`。
- burry 样本计数重复已修（完整 1699 / 缺失率 68.2%，原报 1835 / 66.1%）；`watch_fundamentals` 的 fcf_yield 改名 fcf_yield_mcap（与 burry 的 FCF÷EV 消歧义）。

## 4. 待办

1. **feedback open 3 条**：FB-20261105-12「z≥1.2 + 报价差 ≤10% 几乎只剩 TLT」——平静日数据后请用户定第 7 条口径；~~FB-20261105-13~~ 已做（$5,468.69）；~~FB-20261105-14~~ 已做：`fetch_voices.py` → voices.json。
2. 期权首个可开仓日 11/11（11/09 CPI 前一日、11/10 CPI 当天视灯）；开仓前 `scan.py fetch → run → verify`。
3. predictions 待记分：XLE 11/13 ≥63、UBER 11/20 ≥62、UBER 三情景（2027-11-05）、UBER Q4 指引两条（2027-02-15）、INTC Q4 等。
4. INTC 最后一张平仓价（等用户）；uSMART API 文档域名放行后评估。
5. 报告线待验证：restaurant-research（非提纲的品牌调研）还没跑过一次新流程。

## 5. 复核命令

| 命令 | 交接时结果 |
|---|---|
| `python3 -m unittest tests/test_options_regression.py tests/test_report_check.py tests/test_screen_check.py` | 全过 |
| `python3 tools/self_check.py --quiet` | 无 P1 / P2（只剩第三方 hub 超长 P3 与 3 条 open 反馈） |
| `python3 tools/screen_check.py` | burry / ses 全过 |

## 6. 已排除的路线（不要再提）

帮文章过 AI 检测；编简历数字；回本单；价差 / 组合单；买实时期权数据；用最大购买力算张数；全市场期权初筛作常规；加收入门槛；擅自重建每日定时扫描。
