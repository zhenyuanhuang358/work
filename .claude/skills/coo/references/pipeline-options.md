# 流水线 · 期权日常扫描

<!-- skills: tail-risk-monitor, us-options-agent -->

**本流水线不生产规则，只串顺序。** 每一步的判据都在各自 skill 里，这里写「先后」和「交接」。
关卡：G5（journal + candidate_ledger）、G4（只登记有门槛+时点的判断）、G6。不走 G2/G3（对话内交付）。

## 步骤（顺序不可调）

| # | 步骤 | 调用 / 命令 | 交接给下一步的东西 |
|---|---|---|---|
| 1 | 仓库核验 | `git rev-parse --is-shallow-repository` 为 true → `git fetch --unshallow origin claude/install-claude-hud-d51E6` | 完整历史（tail_light / candidate_ledger 要用） |
| 2 | 取数 | 先运行 `python3 tools/scan.py reserve --run-id <稳定编号>`，把返回的唯一 trigger 交给 GitHub 连接器；再运行 `fetch --trigger <批次> --run-id <同一编号> --bp <可取现金>`。重复执行必须复用同一编号。 | 六份同批新数据 + blob SHA + fetch 回执（R-D0） |
| 3 | 读存量 | `memory/state/current_positions.json` 是当前状态唯一入口；`options-journal.md` 只作历史。未确认或超过24小时，允许市场扫描但禁止给具体张数。 | 持仓状态 + 数据年龄 + 最新可取现金 |
| 4 | 存量复核 | `us-options-agent/references/position-discipline.md`「存量先于新仓」 | 每个仓位：持有 / 减半 / 全平。**有违规存量 → 本次只出存量方案，跳到 7** |
| 5 | 底稿 | `python3 tools/scan.py run --bp <可取现金>`：灯色（tail_light）、事件闸门（fed_speak 高影响数据，前一交易日不开）、60 只 × P/C 全清单筛选（第 1–19 条，期限溢价 < 1.20 自动只取 20–29 天）、跳空压力、1/3/6 张止损亏损、新闻素材 | `memory/state/scans/<id>.json` + `<id>.draft.md` |
| 6 | ✍ 新闻标注 + 结论 | 按 `us-options-agent/references/news-channels.md` 替换草稿全部【待判断】；另存为 `<id>.md`，首行「结论：…」与底稿 can_open 一致。新闻**只标注不否决**；资金 / R4 / R5 只提示（profile 1.1t） | 报告 |
| 7 | 核对 | `python3 tools/scan.py verify memory/state/scans/<id>.md`。报告检查通过后，数据、市场、持仓三道门也必须通过，才会得到 `READY_FOR_BROKER_CHECK`；否则只能是 `VERIFIED_WITH_BLOCKS`。 | scan.json + `.receipt.json` |
| 8 | 登记与交付 | 底稿里每个候选（含否决）`candidate_ledger.py add --verdict 推荐\|否决\|闸门`；报告原文发给用户 | — |
| 9 | 等用户决定 | 开仓前必问两句：止损条件单挂在多少？张数按「止损亏损 ≤ 净值 5%」算的吗？ | 用户回复 → 写 journal |
| 10 | 收尾 | 开平仓记进 `options-trades.jsonl`（scale_check open/close）；G4 / G5 / G6 | — |

## Codex 连接器触发与接收

1. 先执行 `python3 tools/scan.py reserve --run-id <UTC日期时间或任务编号>`。它会原子写入 `<run-id>.fetch.json` 并返回稳定 trigger；重复20次仍是同一个 trigger。通过 GitHub 连接器读取工作分支 `claude/install-claude-hud-d51E6` 的 `price_fetch_trigger.txt` 和 blob SHA，只把这个预留 trigger 写入一次。
2. 在原工作区运行 `python3 tools/scan.py fetch --trigger '<批次>' --bp <可取现金>`。脚本自动创建临时副本，使用原仓库 `origin` 只读取 GitHub。默认环境禁止联网时，为这一条命令申请网络权限。原工作区的 Git 分支、触发文件和未提交修改均不需要移动。
3. 命令检查同一个远端提交里的期权链、股价、新闻、美联储讲话、宏观实际值与公开人物动态。六份齐了才在临时副本运行筛选，底稿保存到原工作区 `memory/state/scans/`，再按步骤核验与登记。若另一批取数已替代本批，或等待超时，查本次提交对应的两项取数工作流；批次不匹配时停止筛选。

## v2 交付状态（2026-11-28）

- `DRAFT_ONLY`：只有机器底稿或草稿，绝不能当开仓结论。
- `FAILED_VERIFY`：报告数字、方向、章节或事件检查失败。
- `VERIFIED_WITH_BLOCKS`：报告本身已核，但数据、市场或持仓至少一道门未通过；只能说明为什么不能行动。
- `READY_FOR_BROKER_CHECK`：四道门全部通过，仍须在券商平台核实实时 bid/ask、保证金和张数，不代表自动下单。
- 每次运行写 `<run-id>.manifest.json`。中断或失败保留现场；同一 run-id 重跑从现场恢复，不重新触发。
- scan.json 的 `actionable` 只有在数据、市场、持仓与报告全部通过时才可为 true。`verification=null`、持仓未确认或行情陈旧时严禁输出“可以开仓”。

### 连接器写入异常

- 遇到 `ReadTimeout`、MCP `-32603 Internal error` 或写入结果不明确，先回读同一分支的触发文件，比较目标批次、原批次及 blob SHA。目标批次已存在就直接接收，避免重复触发。
- 文件仍是原批次且 blob SHA 未变时，用同一个目标批次和回读的 SHA 重试一次。出现其他批次、回读失败或状态不明确时，停止写入并记录实际状态，防止覆盖其他运行。
- 重试也失败时再回读。如果目标批次已写入就接收。如果仍是原批次且已验证终端具有该分支的写权限，可用 `fetch --git-fallback --bp <可取现金>`。终端认证缺失时，记录两条入口的失败原因并停止触发。旧行情可以用于风险复核，不能作为本批扫描结果。


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

## 日常执行耗时与输出

取数工作流已将独立步骤并行运行。财报日历优先一次批量请求，失败后逐个标的兜底。Finnhub 共享限流及 news → fed → macro 的依赖顺序保留。

用户说「今日期权」时，连接器触发后用一条 fetch --trigger --bp 命令等到扫描完成。正常等待用现有会话每 30–45 秒获取输出。仅在命令失败、超过预计耗时或批次不符时查询工作流步骤，不逐步重复获取全文、重读历史、运行全套回归或重复触发。报告先给灯色、账户动作、关键事件与候选摘要，完整底稿另存。

2026-11-18 优化验收：GitHub 期权工作流运行 107 秒，触发至扫描落盘 118 秒；六份同批数据、扫描报价年龄 1.3 分钟。此为一次实测，耗时受数据源和 GitHub 排队影响。
