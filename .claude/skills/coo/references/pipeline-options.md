# 流水线 · 期权日常扫描

<!-- skills: tail-risk-monitor, us-options-agent -->

**本流水线不生产规则，只串顺序。** 每一步的判据都在各自 skill 里，这里写「先后」和「交接」。
关卡：G5（journal + candidate_ledger）、G4（只登记有门槛+时点的判断）、G6。不走 G2/G3（对话内交付）。

## 步骤（顺序不可调）

| # | 步骤 | 调用 / 命令 | 交接给下一步的东西 |
|---|---|---|---|
| 1 | 仓库核验 | `git rev-parse --is-shallow-repository` 为 true → `git fetch --unshallow origin claude/install-claude-hud-d51E6` | 完整价格历史（否则 candidate_ledger / spread_check 取不到） |
| 2 | 触发抓价并等新鲜 | 改 `price_fetch_trigger.txt` → commit → push **工作分支**；轮询 `git fetch` 后 `git show origin/claude/install-claude-hud-d51E6:stock_prices.json` 的 `updated_at` 晚于今日开盘 | 新鲜的 `stock_prices.json`。**不新鲜不出报告**（R-D0） |
| 3 | 读存量 | `memory/state/options-journal.md` 末尾 + handoff §2 | 持仓表：标的 / 行权 / 到期 / 收入 / 止损价 / 张数 |
| 4 | 尾部闸门 | `tail-risk-monitor` 工作流 Step 1–5 | 灯色 + 期限溢价（≥1.20 才开 30–45 天档） |
| 5 | 宏观日历 | `us-options-agent/references/macro-events.md` | 未来 5 个交易日事件；**事件前一交易日不新开** |
| 6 | 存量复核 | `us-options-agent/references/position-discipline.md` 四条 | 每个仓位：持有 / 减半 / 全平。**有违规存量 → 本次只出存量方案，跳到 9** |
| 7 | 新候选扫描 | `us-options-agent` 每日扫描（`references/daily-scan-template.md`）；价差过 `tools/spread_check.py` | 候选表（含否决的与否决理由） |
| 8 | 全量登记候选 | 每个候选（含否决）`python3 tools/candidate_ledger.py add --ticker … --verdict …` | — |
| 9 | 对话内交付 | 先存量、后新仓；资金/R4/R5 只**提示**不否决（profile 1.1t） | 用户决定 |
| 10 | 等用户决定 | 开仓前必问两句：止损条件单挂在多少？张数按「止损亏损 ≤ 净值 5%」算的吗？ | 用户回复 → 写 journal |
| 11 | 收尾 | G4 / G5 / G6 | — |

## 闸门组合 → 允许的动作

| 灯色 | 事件窗口 | 存量 | 新仓 |
|---|---|---|---|
| 红 | 任意 | 按 position-discipline 处理 | **不新开** |
| 黄 | 任意 | 同上 | 缩量，见 tail-risk `regime-playbook.md` |
| 绿 | 事件前一交易日 | 确认止损条件单已挂 | **不新开** |
| 绿 | 持有期含 CPI/PPI/FOMC | — | 缓冲÷1σ 门槛 1.0 → 1.2 |
| 绿 | 无事件 | — | 正常扫描 |

## G4 在期权流水线里登记什么

只登记**对世界状态的判断**，例如「UBER 10/30 收盘 ≥ $63」——终点条件，按到期概率定档。
不登记止损线、触发线（它们是规则不是预测，规范 6）。
「期间不触及止损」是路径条件，按触线概率定档（规范 11），多数情况只能填「低」或不登记。

## 交接坑

- 价格**读工作分支**，不读 main（profile 1.1f；`daily-scan-template.md` 已于 2026-10-28 改正）。
- 用户说「挂好了」但没截图 → journal 写「用户称已挂，未核验」，不写「已挂」（profile 1.1l）。
- 大亏后 48 小时内不提新仓，不讨论「回本」单（profile 1.1z）。
