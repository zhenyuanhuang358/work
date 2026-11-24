# Merlin · Decision Mode（假设驱动闭环，2026-11-24 新增）

> **统一入口**：客户调研只要服务一个具体决策（投资尽调、立项评估、访谈决策），默认走本模式，不再走普通 Mode B；与 Mode B 的边界由 hub 判据表定。
> 只在客户调研的**决策类任务**使用：投资尽调、访谈准备、立项评估。产物除报告外，还有假设台账、证据底账、冲突表、红队记录、决策备忘。
> 目标：以可控成本降低决策不确定性；**不是**"搜网页→拼总结"。

## 五阶段（必须按序，门不过不前进）

| 阶段 | 动作 | 产物 | 门 |
|---|---|---|---|
| 1 Frame | 锁定服务什么决策；拆 MECE 可证伪假设；每条写证伪条件与所需证据 | `hypotheses.json` | G0：决策与假设经用户确认 |
| 2 Source | 分层检索：一手优先（财报/招股书/监管/专利/招投标/访谈原文），二手媒体降权；每条证据结构化 | `evidence.jsonl` | G1：核心假设 ≥2 源且 ≥1 一手 |
| 3 Triangulate | 口径拉齐后交叉验真；数值必须由 `calc.py` 计算并落 `calc.json`；冲突进 `conflicts.json` | `conflicts.json`、`calc.json` | G2：冲突有结论、计算可复算 |
| 4 RedTeam | 强制反向检索：反例、做空逻辑、失败案例、失效边界；检查是否触发证伪条件 | `redteam.md` | G3：≥3 反向检索、≥2 反证、证伪复核 |
| 5 Synthesize | 结论先行；每条核心论断绑定 claim_id；三层切分（硬事实/推演/盲区）；写"什么会推翻结论" | `report.html`、`decision_memo.md` | G4：核心论断 100% 绑定；G5：预算/轮次 |

## 两个回环（状态机强制，禁止无限循环）

- **回环 1 补采**：核心 claim 一手源 <2 或数字冲突 >2% 且口径解释不通 → 定向补采；**最多 2 轮**；到顶写盲区 + 对结论影响。
- **回环 2 重构**：红队证据触发某条核心假设的证伪条件 → 回 Frame 重构；**最多 1 次**；再被推翻 → 交付「暂不决策/需访谈验证」选项。

## 全局预算（超限即停，出盲区版）

≤90 分钟、≤30 个来源、≤8 次原文抓取、≤2 次补采、≤1 次重构。全部记入 `state.json`。

## 数据格式

`hypotheses.json`
```json
{"decision":"...","hypotheses":[{"id":"H1","statement":"...","falsifier":"什么证据出现即推翻","evidence_needed":["..."],"core":true,"status":"待验"}]}
```
`evidence.jsonl`（每行）
```json
{"claim_id":"C1","hypothesis_id":"H1","metric":"2026H1 收入","value":"223.37","unit":"亿元","period":"2026H1","source_type":"primary","url":"https://...","published_at":"2026-09-22","quote":"原文摘录","file":"pages/..."}
```
`conflicts.json`：`claim / values[] / sources[] / 口径差异 / resolution（resolved/blind_spot） / impact`
`calc.json`：由 `calc.py` 生成的全部计算值；报告里的数字必须能在其中找到。

## 工具

```bash
python3 tools/dr_state.py init <task> --decision "..."
python3 tools/dr_state.py gate <task> frame|source|triangulate|redteam|synthesize [--confirm]
python3 tools/dr_state.py status <task>
```
外加 `merlin_check`（M0–M10）、`report_check --record`、Critic 独立评审；客户交付附「可以说/不能说」口径。
