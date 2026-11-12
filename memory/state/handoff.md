# 会话交接单（2026-11-10 · 第五版，替换 11-06 v4）

> **开场必做**：① 读本文件和 `memory/profile-core.md`（不要整读 86 KB 的 `profile.md`，按索引 grep）② `git status` 干净、`git log -1` 正常
> ③ 跑 §5 命令 ④ 再动手。**§3 已做的不要重做；§4 才是待办。** 非 Claude Code 的 harness 先读根目录 `AGENTS.md`。

## 0. 基线

| 项 | 值 |
|---|---|
| 分支 | `claude/install-claude-hud-d51E6`（= GitHub 默认分支；只推这里；不开 PR，除非用户要求） |
| 取数 | 容器封 sec.gov、cboe 等 → 要联网的一律走 GitHub Actions（改触发文件并推送，读产物；见 `AGENTS.md` §5） |
| 推送 | 工作流会并发提交：推前 `git fetch && git merge` |
| 用量 | 用户套餐用量有限（11/10）：一件事开一个新会话；能用工具和程序检查解决的，不靠多轮评审 |

## 1. 硬约束（用户原话或已确认）

- **期权（us-options-agent）**：只做卖方单腿（盈立无组合单）；卖 put 和价外 call，绝不卖价内 call；不接货；保证金 ×1.15 ≤ 可取现金；不做回本单。
  无持仓，阶段 1 张，可取现金 **$5,468.69**（11/07）。用户说「今日期权」才扫；**不得擅自重建每日定时扫描**。
- **天道的期权条款（只做价差、单笔 ≤ $275）与 us-options-agent 无关**，两套互不读取（用户 11/08 定）。「三源智囊团」不存在。
- **合规**：不披露海底捞（6862）、绿茶（6831）未公开数据；不帮客户文章过 AI 检测；简历不编数字；凭证只进 GitHub Secrets。
- 分支 `claude/us-stock-opportunities-htj5ur` 不合并、不再提。
- Critic 两轮不过就停下问用户（COO 规则）。
- 工作原则见 `CLAUDE.md`：第一性原理；目标不清先讨论；不熟的功能先搜开源、给取舍、做最小验证。

## 2. 各条线现状（都有工具 + 程序检查 + 回归测试）

| 线 | 入口 | 检查 |
|---|---|---|
| 期权扫描 | `tools/scan.py fetch → run --bp <可取现金> → verify`；规则唯一出处 `us-options-agent/references/position-discipline.md` 第 1–19 条 | `verify_scan.py` V1–V12；`tests/test_options_regression.py`（冻结 11/05 数据） |
| 报告（Earner / Merlin / restaurant-research） | 各 skill；Critic 第 0 步 `tools/report_check.py <报告> --record` | `tests/test_report_check.py`；Earner 样例 `reports/uber_Copilot_Report.html` |
| 巴菲特 | 估值 `tools/owner_value.py <输入.json>`；报告 `tools/buffett_report.py <输入.json> <叙述.json>`（通用模板，不再手写生成脚本） | `tests/test_owner_value.py`、`tests/test_buffett_report.py`；样例 `tests/fixtures/buffett/` |
| 筛选器（burry / sleeper） | Actions 工作流 | `tools/screen_check.py`；`tests/test_screen_check.py` |
| 天道 | `.claude/skills/tiandao/`；个人规则 `memory/state/tiandao/personal-rules.md` 与 `.json`；上限检查 `tools/tiandao_check.py` | 交付前 `tools/tiandao_verify.py answer / card`；`tests/test_tiandao_*.py`；样例 `tests/fixtures/tiandao/` |
| 可编辑 PPTX | `.claude/skills/pptagent/`（第三方，MIT；安装见 `AGENTS.md` §9） | 它自带 `finalize`，`complete=true` 才交付 |
| 取数脚本 | `scripts/fetch_*.py`（价格、期权链、新闻、美联储、宏观、电话会、网页、SEC 财务） | `tests/test_fetch_financials.py` |

反馈台账 `memory/state/feedback.jsonl`；自检 `tools/self_check.py`（C1–C16）；skill 索引 `SKILLS.md`（`tools/skill_index.py` 生成）。

## 3. 已做（勿重做）

- **11/05–11/06**：期权、报告、筛选器三条线的 skill 改造；UBER 财报报告、海底捞 AI 导购提纲报告交付。
- **11/07**：KO 巴菲特报告（高估不买，内在价值 48.59–58.81，评分 48）。
- **11/08**：搬家准备（`AGENTS.md`、`SKILLS.md`、报告 PDF 入库）；PPTAgent 接入并验证；天道智能体布置。
- **11/09**：NVDA 巴菲特报告（高估不买，135.27–148.38，评分 74）；天道验收标准与检查器；台账确认为空（无借款、无入股）。
- **11/10**：
  - 期权第 7 条改为**报价差 ÷ 中间价 ≤ 20%**（原 ÷ 买价 ≤ 10%），数值唯一出处 `option_quote.SPREAD_MAX`；`scan.py` 拒绝覆盖已有底稿。
  - 巴菲特评分 8 项由工具查表（输入里给 `score_facts`）+ 通用报告模板；必读档案改为 `profile-core.md`。
- **巴菲特规则（用户定，已进工具）**：安全边际按下沿；一次性项只用于估值；基准终端增长封顶 3%；交叉验证用股权口径；
  营收增速波动率 = 增速标准差；完整财年结束超过 6 个月用 TTM；护城河按证据打分。

## 4. 待办

1. **期权**：11/10 红灯未开。11/13 PPI → 11/12 为事件前一交易日，不新开；按灯色最早 11/11。扫描在开盘 1 小时后（10:30 ET 起）才有参考价值。
2. **predictions 待记分**：XLE 11/13 ≥ 63、UBER 11/20 ≥ 62、UBER 三情景（2027-11-05）、UBER Q4 指引两条（2027-02-15）、KO FY2030 FCF < $22.7B（2031-02-28）、INTC Q4 等。
3. **feedback open 两条**：FB-20261107-B04（burry 债务标签修复，等下次 burry 实跑核对 KO 净负债为正）；FB-20261109-B10（KO 报告未按 TTM 规则重跑，结论不变，用户要求时再跑）。
4. **尚未实测**：巴菲特通用模板还没用在新公司上；天道的资金类决策（借钱、入股、黄金）；restaurant-research 新流程。
5. **NVDA**：11/17 财报、11/18 黄仁勋国会闭门作证、董事会调查——出结论后重评管理层评分（3C）和关键人风险，报告风险表尚未补这一项。
6. INTC 最后一张平仓价（等用户）。仍调用 Anthropic API 的代码清单在 `AGENTS.md` §6，换 DeepSeek 时要改，未改。

## 5. 复核命令

```
python3 -m unittest tests/test_options_regression.py tests/test_report_check.py tests/test_screen_check.py tests/test_owner_value.py tests/test_skill_index.py tests/test_tiandao_check.py tests/test_fetch_financials.py tests/test_tiandao_verify.py tests/test_buffett_report.py tests/test_combo_payoff.py   # 11/12 起含组合分析
python3 tools/self_check.py --quiet     # 交接时无 P1 / P2
```

## 6. 已排除的路线（不要再提）

帮文章过 AI 检测；编简历数字；回本单；us-options-agent 里做价差或组合单；买实时期权数据；用最大购买力算张数；加收入门槛；擅自重建每日定时扫描；三源智囊团。
