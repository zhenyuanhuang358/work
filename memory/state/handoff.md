# 会话交接单（2026-11-05 · 第三版，替换 10-27 版）

> **新 Agent 开场必做**：① 读本文件 ② `git log -1` 对照下方基线（之后只应有本交接单与 Actions 的 `chore:` 自动提交）
> ③ `git status` 确认干净 ④ 跑 §5 命令复核 ⑤ 再动手。**§3「已做」不要重做；§4 才是待办。**

## 0. 基线

| 项 | 值 |
|---|---|
| 分支 | `claude/install-claude-hud-d51E6`（= GitHub 默认分支，所有定时工作流跑在这里；只在这里推送；不开 PR 除非用户要求） |
| 交接时 HEAD | `38e10b6`「60 只基本面补审…」之后仅本交接单一个提交 + Actions 自动提交 |
| 容器坑 | 可能浅克隆 → `git fetch --unshallow origin claude/install-claude-hud-d51E6`；容器封 sec.gov / cboe / x.com / api-doc.usmart8.com → **要联网的一律放 Actions 跑**（推触发文件，读产物） |
| 推送 | 工作流会并发提交：推前 `git fetch && git merge`，失败退避重试 |
| 上一会话完整记录 | `/root/.claude/projects/-home-user-work/7655cc02-2eb8-57ac-a875-3308dbe0f1a9.jsonl`（索引用） |

## 1. 用户目标与硬约束（用户原话或已确认）

- 账户：净值约 **$5.5k**（11/04 截图 $5,845.37，之后 AMD 强平 −$375）；**当前无期权持仓**；阶梯阶段 = **1 张**。
- **只做卖方、不打算接货**；卖 put + 卖**价外** call（绝不卖价内 call）。**平台无组合单 → 只做单腿，不做价差。**
- 资金能否覆盖、接货比例、R4/R5 只**提示**不否决；**平台能否下单是硬过滤**：保证金 ×1.15 ≤ **可取现金**（不是最大购买力——用户实测 SPY「可沽空 0」）。
- 不做「回本」单；用户已被告知：没有能快速回本的策略，按 +0.30 优势 3 张约月 1.5–2%。
- 「价差」一律说「买卖报价差」，避免与价差策略混淆。
- 客户文章：**不帮过 AI 检测**（humanizer-zh 只做编辑，不宣传过检测）；简历**不编数字**；不披露海底捞 / 绿茶未公开数据。
- 盈立 uSMART API：凭证只进 GitHub Secrets，绝不贴聊天；只接只读行情，不接下单。
- **另一分支 `origin/claude/us-stock-opportunities-htj5ur` 不合并、不再主动提。** 分支上另一会话的 options-agent/ 提交（2be7e53、4add6a9）不要碰。
- 不熟悉的功能先搜开源、给取舍、再最小验证（CLAUDE.md 工作原则 5）。

## 2. 期权规则全集（position-discipline 第 1–18 条，hub 197 行）

| # | 规则 |
|---|---|
| 3 | 单腿，不做组合单 |
| 5 | 保证金估算 ×1.15 ≤ 可取现金；结论写「可沽空 N 张」 |
| 6–8 | 每笔张数 = `scale_check.py report` 阶段；买卖报价差 ≤ 收入 10%；开仓同挂 **2× 止损 + 0.5× 止盈**买回单（无 OCO，一边成交手动撤另一边） |
| 9 | 满 20 簇用 `put_backtest.py` / `stop_replay.py` 扣真实报价差复盘 |
| 10–12 | 卖价外 call 纳入；绝不卖价内 call；保证金 ×1.15 |
| 13–14 | 到期前有财报不开；IV/HV ≥ 1.1 |
| 15 | 阶梯加码 1→2→3 张：每 20 簇一轮五项门槛（≥20 簇且 ≥6 周 / 每 $ 收入优势 ≥ +0.30 / 最差 ≥ −2.5× / 止损准时 ≥90% / IV/HV 均值 ≥1.2），连续两轮不达标停止 |
| 16 | 行业分散：同行业同时 1 笔（`options-screen.json` sectors 22 组） |
| 17 | 基本面反向名单 `memory/state/options-screen.json`，每月 buffett/burry 复核（>35 天 self_check C10 点名） |
| 18 | IV 历史分位低位不开（`options_iv_history.jsonl` 满 15 天启用）；≥35 DTE 单 21 DTE 离场 |
| 宏观 | 红灯不新开；事件前一交易日不新开：CPI 11/10、12/10；PPI 11/13、12/15；FOMC 12/09；NFP 12/04 |

**扫描链路**：`options_watch.json`（60 只，right=PC，expiries 11/13、11/20）→ 推 `price_fetch_trigger.txt` → `fetch-options.yml`（期权链 + 财报日历 + IV 历史）→ `python3 tools/option_quote.py --right P|C --bp <可取现金>`（自动标 ⛔财报 / ⚠财报未核实 / ⛔基本面 / ⛔IV低位 / ⛔IV不贵 / ⛔报价差 / ⛔保证金，带 ⛔ 不推）→ 用户下单 → `tools/scale_check.py open/close` 记账。COO 流水线：`.claude/skills/coo/references/pipeline-options.md`。

**基本面名单（11/05 复核）**：不卖 put = INTC AMD PLTR NVDA RIVN RIOT CLF MP AAL DKNG；不卖 call = AMD NVDA MU SNDK；可卖 put = T GM KO UBER WMT；谨慎 = F HOOD ORCL XYZ KHC LYFT；数据缺口 = SOFI BIDU WFC BAC C。

## 3. 已做（已提交，勿重做）

- 10/27–10/31：止损统一 2×；predictions 规则 11 搬入；COO 总调度（hub + 4 流水线 + G1–G6 关卡 + 运行记录）；期权链自动化（CBOE 主 / yfinance 兜底）；歸藏三件 skill + humanizer-zh；C5 路由名核对；价格缓存改读本分支。
- 11/04–11/05：亏损归因 + 回放（`trade_replay_20261105.py`：15 笔实盘旧规则 −$4,240 → 新规则 +$330，最大单笔 −$5,150 → −$304；50% 止盈每 $ 收入 +0.16，样本内未扣成本）；卖 call 纳入；财报日历 + IV/HV 过滤；阶梯加码；大师三原则；巴菲特 + 伯里复核（`watch_fundamentals.py`，多类股用稀释加权股数补缺、yfinance 补价）；期权流动性初筛（`options_liquidity_screen.py`）→ 关注清单扩到 60 只并补审基本面。
- 11/05 新闻标注：`scripts/fetch_news.py`（Finnhub 要闻 + 60 只个股，随 fetch-options 产出 `news.json`）+ `us-options-agent/references/news-channels.md` + pipeline 步骤 7b。**只标注不否决**（用户要求「加以说明标注」）。
- 11/05 重跑优化：`tools/tail_light.py`（机械灯色）；`option_quote.py --all`（全清单汇总）/ `--dte-max` / ⛔期限溢价 / ⚠链不够宽 / ⚠无HV；fetch_options 用 yfinance 算 hv30（原 49/60 只无 HV，IV/HV 过滤静默失效）；candidate_ledger 加「闸门」裁定；band 0.35。
- INTC 财报 Earner 报告 `reports/intc_Copilot_Report.html`（Critic 后修正）。

## 4. 待办

1. **11/05 15:45Z 已排定的提醒**（trig_01NhjWbDsQdfWfs1EdsPyM2r）：盘中验证 60 只买卖报价差——改 `options_seed.json` 的 `_note` 推送触发 `options-liquidity.yml`，读 `options_liquidity_seed.json`；报价差 >10% 的用排名靠后且达标的替换，保持 60 只；同步 options-screen sectors；向用户汇报。
0. **每日定时扫描（11/05 用户定）**：trig_01GTgKrEFkqcZfyHtiLsGaTh，`CRON_TZ=America/New_York 31 10 * * 1-5`（开盘后 1 小时，夏令时自动跟随），**绑定专用会话 session_01GpMt1vxpGD6pxsrhb5hEbN**（挂了仓库、能推送），跑完 PushNotification。⚠ 不要改成「每次新开会话」模式：11/05 首跑实测新会话不挂仓库、推送 403、拿不到 add_repo，整条流水线跑不动。改时间 / 休市表用 update_trigger。
1b. **新仓到期 20–45 天**（11/05 用户定，第 19 条；options_watch `dte` 窗口自动滚动）。待观察：平静日 z≥1.2 时报价差 ≤10% 能过几只；过的太少就请用户定第 7 条口径（÷bid 还是 ÷mid、挂中间价）。
2. **新规则首个可开仓日 = 11/11**（11/05 = NFP 前一日、11/09 = CPI 前一日，均不新开）。开仓前跑 tail-risk 灯 + option_quote。
3. 实盘每笔用 `scale_check.py open/close` 记账；满 20 簇复盘。
4. predictions 待记分：XLE 11/13 ≥63、UBER 11/20 ≥62、AMD 11/13 ≥442.5、INTC Q4 / 情景行。
5. INTC 最后一张平仓价——等用户提供。
6. uSMART API 文档域名需在环境网络里放行后才能评估接入。
7. IV 历史分位过滤满 15 个交易日自动启用（约 11 月底）；options-screen 月度复核 12 月初前。

## 5. 复核命令（交接时结果）

| 命令 | 结果 |
|---|---|
| `python3 tools/self_check.py` | 只剩第三方 hub 超长 P3（kami 等，不改） |
| `python3 tools/scale_check.py report` | 0 笔，阶段 = 1 张 |
| `python3 tools/option_quote.py --right P --bp 5400` | 应能读出 60 只的链与标记（需链在 20 分钟内，否则加 `--max-age`） |

## 6. 已排除的路线（不要再提）

- 帮文章过 AI 检测；编简历数字；INTC 85P 回本单；价差 / 组合单（平台不支持）。
- 买实时期权数据源——用户定用延迟报价 + 平台核实。
- 用「最大购买力」算可开张数。
- 全市场期权初筛作为常规（已做过一次，常规只用 60 只种子清单 + 每周一流动性复核）。
- 加收入门槛（用户 11/04 拒绝）。

## 7. 记忆文件

`memory/profile.md`（教训，含 1.1zc / 1.1zd / 1.2r）｜`memory/state/options-journal.md`｜`memory/state/options-trades.jsonl`｜`memory/state/options-screen.json`｜`memory/state/options-candidates.jsonl`｜`memory/state/predictions.md`｜`memory/state/research-ledger.md`｜`memory/state/runs/`
