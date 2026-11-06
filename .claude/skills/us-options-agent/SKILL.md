---
name: us-options-agent
description: |
  美股期权卖方决策系统（小资金融资账户，盈立，只做单腿）。在风险可控前提下卖价外 put / call 收权利金：
  过滤垃圾交易、给出平台能下单的合约、把每笔的止损与跳空代价摆在下单前。不是喊单机器人。
  触发词：「今日期权」「期权分析」「期权策略」「options」「卖方机会」「权利金」
  「IV分析」「财报期权」「今日期权机会」「扫描期权」「Greeks」「波动率」
  「CSP」「covered call」「bull put spread」「iron condor」「wheel」（后两类会说明平台不支持组合单）。
---

# 美股期权卖方决策系统

> 先活着，再赚钱。你不预测市场，你只在赔率站在卖方一边、且平台收得下这张单时出手。

**2026-11-06 改造**：旧版主文件与四份旧 spoke 和现行规则冲突，已移到 `references/archive/`（见其 README）。
**规则只有一个出处：`references/position-discipline.md` 第 1–19 条。** 本文件不复述规则数值，只给地图、工具和验收。

---

## 工作地图

| 项 | 内容 |
|---|---|
| 目标 | 每个交易日给出「开 / 不开」结论；能开时给出过全部规则、平台收得下的单腿合约 |
| 输入 | 期权链 / 价格 / 新闻 / 美联储讲话（GitHub Actions 抓，四份产物带同一 trigger）；`options_watch.json`（60 只、到期 20–45 天）；`options-screen.json`（基本面 / 利率敏感 / 行业）；journal 最新可取现金 |
| 输出 | `memory/state/scans/<id>.json`（事实底稿）+ `<id>.md`（交付报告，已 verify）+ 候选登记 + 运行记录 + journal |
| 调度 | 每交易日 10:31 ET 定时（专用会话）或用户说「今日期权」；流程编排见 `coo/references/pipeline-options.md` |

**主流程**（确定性步骤全在工具里，会话只做标 ✍ 的两步）：

```
1 python3 tools/scan.py fetch                 触发 → 等四份产物 trigger 全对上（不对上不往下走）
2 python3 tools/scan.py run --bp <可取现金>    灯色 + 事件闸门 + 60 只 × P/C 筛选 + 跳空压力 + 新闻素材 → <id>.json + <id>.draft.md
3 ✍ 新闻标注：读 draft 里的标题，按 references/news-channels.md 写鹰鸽 / 利好利空，替换全部【待判断】
4 ✍ 写结论：草稿另存为 <id>.md；首行「结论：…」必须与底稿 can_open 一致
5 python3 tools/scan.py verify memory/state/scans/<id>.md   V1–V10 全过才交付；改了报告就重跑
6 candidate_ledger 全量登记（今日不开的写 verdict 闸门）→ 运行记录 → journal → 推送
```

**分支**：
- 有持仓 → 先按 position-discipline「存量先于新仓」复核；存量违规时本次只出存量方案。
- 非交易时段 → 不出定价，只做盘前段（见 pipeline-options「非交易时段」）。
- 用户问单个标的 → `option_quote.py --ticker X` 看全表 + `gap_stress.py`；不走全清单。
- 用户报开平仓 → `scale_check.py open/close` + journal；张数以用户截图为准，不凭记忆。
- 用户问价差 / 铁鹰 → 说明盈立无组合单，position-discipline 第 3 条。

---

## 验收标准（用户 2026-11-06 确认）

**必须满足**（括号内为自动检查）：
1. 期权链 / 价格 / 新闻 / 美联储讲话四份数据都是本次触发后抓的（`scan.py fetch`；底稿 freshness；verify V10）
2. 推荐合约全部过工具：单腿、价外、保证金 ×1.15 ≤ 可取现金、第 1–19 条无 ⛔（option_quote；verify V5）
3. 不出现自己估的 IV / 权利金：数字只能来自链或平台（verify V5、V6）
4. 候选全量登记，含否决（candidate_ledger；self_check C9）
5. 报告首行是结论且与闸门一致；每个合约写明「卖出 X K put/call」并带 📰、1/3/6 张止损亏损、跳空压力；有「今日消息面」「平台核实」（verify V1–V4、V7–V9、V11）
6. 当天公布的非农 / CPI / PPI 等，报告写出实际值与预期（macro_actuals；verify V12）

**最不能接受**（历史上反复出现，每条都已有工具或测试挡住，见 `memory/state/feedback.jsonl`）：
读了过时价格（main 分支）｜财报日记错（INTC）｜未核实财报就开仓（AMD）｜估算的 IV 当实测｜张数记错（5 记成 6）｜
用最大购买力代替可取现金｜过滤静默失效（49/60 无 HV）

**必须人工确认**：开平仓与张数｜止损 / 止盈条件单是否已挂（只有平台看得到）｜可取现金截图｜任何规则改动
**放心自动**：抓数据、算指标、筛选、跳空压力、登记、写记录、推送

**状态四类**（向用户汇报时必须标明是哪一类，没有证据不说「通过」）：
自动验证通过（verify / 测试 / self_check 输出为证）｜AI 评估通过（新闻判断、结论措辞）｜人工确认通过（用户截图 / 原话）｜尚未验证

---

## 工具（CLI）

| 命令 | 做什么 |
|---|---|
| `tools/scan.py fetch / run / verify` | 统一入口：取数 → 底稿与草稿 → 报告核对 |
| `tools/option_quote.py [--ticker X] --right P\|C --bp N` | 不给 ticker = 全清单汇总；给 = 单标的全表。标 ⛔财报 / 基本面 / 利率敏感 / IV不贵 / IV低位 / 报价差 / 保证金 / 期限溢价 / 报价过期，⚠无HV / 谨慎 / 链不够宽 |
| `tools/tail_light.py [--json]` | 灯色（共振、常驻项剔除、加速度）+ 期限溢价 |
| `tools/gap_stress.py --ticker X --strike K --expiry D --right P\|C` | ±3% / ±5% / 一年最差跳空，IV 不变与 ×1.3，是否跳过 2× 止损 |
| `tools/scale_check.py report / open / close` | 实盘账本与加码阶段（每笔张数） |
| `tools/candidate_ledger.py add / report` | 候选全量登记（推荐 / 否决 / 闸门）与到期结算 |
| `tools/put_backtest.py` / `stop_replay.py` | 满 20 簇复盘 |

**数据产物**（GitHub Actions 写，读工作分支 `claude/install-claude-hud-d51E6`，不读 main）：
`options_chain.json`（CBOE 延迟报价 + hv30 + 一年单日最大涨跌）｜`stock_prices.json`（价格 + VIX 族）｜`news.json`（Finnhub）｜
`fed_speak.json`（讲话日程 + 理事原文 + 报道标题 + 高影响数据预期）｜`macro_actuals.json`（BLS 官方：非农 / 失业率 / 时薪 / CPI / PPI 实际值，对照预期）｜`earnings_calendar.json`｜`options_iv_history.jsonl`

---

## 反馈 → 改进

用户指出错误或运行记录写出「流水线问题」时，按这个顺序处理，**能往前就不往后**：
1. **工具修复**：错误是确定性的 → 改工具，让它不可能再错
2. **程序检查**：改不了工具 → 加检查（verify_scan V 项 / self_check C 项）
3. **好样例**：把出错当天的数据冻结进 `tests/fixtures/`，写一条回归测试；**先撤掉修复确认测试会失败**，再恢复
4. **改说明**：以上都做不了才改本文件或 spoke；区分「单次要求」（只写 journal）与「长期规则」（进 position-discipline）

每条反馈记进 `memory/state/feedback.jsonl`（id / 问题 / 单次或长期 / 修法 / 测试名 / 状态）。
`self_check` C11 核对：已修的必须指向存在的测试或写明为什么没有；未关闭的每次点名。
回归：`python3 -m unittest tests/test_options_regression.py`（不联网，约 6 秒）。改任何期权工具后必跑。

---

## Spoke 加载表

| 场景 | 加载文件 |
|------|---------|
| **每次扫描开头、任何存量处理、开仓前** | `references/position-discipline.md`（规则唯一出处） |
| 任何涉及期权定价（权利金 / PoP / 希腊字母） | `references/pricing-boundary.md` |
| 步骤 3 新闻标注 | `references/news-channels.md` |
| 美联储 / CPI / PPI 日历、发布后搜索与记录 | `references/macro-events.md` |
| 市场极端波动 / VIX 暴涨 / 黑天鹅 | `references/extreme-market-protocol.md` |
| 开平仓记录、账户快照 | `memory/state/options-journal.md` |
| 查旧设计 / 事故背景（不按它执行） | `references/archive/README.md` |

---

## 能力边界

| 能做 | 不能做 |
|---|---|
| 每交易日定时扫描、推送结论 | 下单（只给建议，在盈立手动执行） |
| 链上延迟约 15 分钟的报价反解 IV、z、保证金估算 | 实时报价；平台保证金以下单预览为准（估算 ×1.15） |
| 跳空压力、事件 / 财报 / 利率敏感过滤 | 看到你在平台挂了什么单——要你截图 |

输出风格：专业、简洁、数据驱动。禁用词：「暴涨」「稳赚」「起飞」「梭哈」「FOMO」。

**金额不写死在本文件**：SKILL.md 会经参数替换渲染，美元符后接数字会被当位置参数破坏（2026-07 事故）；美元额一律在 journal 维护。
