# 流水线 · 期权日常扫描

<!-- skills: tail-risk-monitor, us-options-agent -->

**本流水线不生产规则，只串顺序。** 每一步的判据都在各自 skill 里，这里写「先后」和「交接」。
关卡：G5（journal + candidate_ledger）、G4（只登记有门槛+时点的判断）、G6。不走 G2/G3（对话内交付）。

## 步骤（顺序不可调）

| # | 步骤 | 调用 / 命令 | 交接给下一步的东西 |
|---|---|---|---|
| 1 | 仓库核验 | `git rev-parse --is-shallow-repository` 为 true → `git fetch --unshallow origin claude/install-claude-hud-d51E6` | 完整历史（tail_light / candidate_ledger 要用） |
| 2 | 取数 | `python3 tools/scan.py fetch`（触发 → 等链 / 价格 / 新闻 / 美联储讲话四份 trigger 全对上 → merge；超时即停，不用旧数据） | 四份同批新数据（R-D0） |
| 3 | 读存量 | `memory/state/options-journal.md` 末尾 + `python3 tools/scale_check.py report` | 持仓表 + 当前张数阶段 + 最新可取现金（注明截图日期） |
| 4 | 存量复核 | `us-options-agent/references/position-discipline.md`「存量先于新仓」 | 每个仓位：持有 / 减半 / 全平。**有违规存量 → 本次只出存量方案，跳到 7** |
| 5 | 底稿 | `python3 tools/scan.py run --bp <可取现金>`：灯色（tail_light）、事件闸门（fed_speak 高影响数据，前一交易日不开）、60 只 × P/C 全清单筛选（第 1–19 条，期限溢价 < 1.20 自动只取 20–29 天）、跳空压力、1/3/6 张止损亏损、新闻素材 | `memory/state/scans/<id>.json` + `<id>.draft.md` |
| 6 | ✍ 新闻标注 + 结论 | 按 `us-options-agent/references/news-channels.md` 替换草稿全部【待判断】；另存为 `<id>.md`，首行「结论：…」与底稿 can_open 一致。新闻**只标注不否决**；资金 / R4 / R5 只提示（profile 1.1t） | 报告 |
| 7 | 核对 | `python3 tools/scan.py verify memory/state/scans/<id>.md`：V1–V10 全过才交付；改报告就重跑（self_check C12 查 sha） | 核对结果写回底稿 |
| 8 | 登记与交付 | 底稿里每个候选（含否决）`candidate_ledger.py add --verdict 推荐\|否决\|闸门`；报告原文发给用户 | — |
| 9 | 等用户决定 | 开仓前必问两句：止损条件单挂在多少？张数按「止损亏损 ≤ 净值 5%」算的吗？ | 用户回复 → 写 journal |
| 10 | 收尾 | 开平仓记进 `options-trades.jsonl`（scale_check open/close）；G4 / G5 / G6 | — |

## 非交易时段被喊「今日期权」（2026-10-29 首次真实运行发现）

盘前 / 盘后 / 周末没有期权实时报价，也开不了仓。**不等，也不硬出定价**：
- **盘前段**（现在就做）：步骤 1–6 用最近收盘快照；步骤 7 只做 HV 初筛（z_HV 行权价上限 + 否决理由），**不给权利金 / PoP 数字**（1.1x）。
- **开盘段**（10:00 ET 后）：同一份运行记录续跑——重新触发抓价，拿平台报价反解 IV，完成步骤 7 定价、8 登记、9–11。
- 两段共用一份运行记录；定时任务写「续跑」，不要让它新建记录。

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

- 价格**读工作分支**，不读 main（profile 1.1f）。
- 用户说「挂好了」但没截图 → journal 写「用户称已挂，未核验」，不写「已挂」（profile 1.1l）。
- 大亏后 48 小时内不提新仓，不讨论「回本」单（profile 1.1z）。
