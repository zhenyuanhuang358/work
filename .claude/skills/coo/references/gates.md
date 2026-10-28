# 公共关卡细则（G1–G6）

每道关卡写三件事：**判据**（过没过怎么看）、**命令**（怎么跑）、**不过怎么办**。
关卡本身不新造规则——全部来自已立的规则，这里只是把它们接到流程里（各条注明出处）。

---

## G1 · 合规红线（handoff §1；用户为绿茶现任品牌运营总经理、前海底捞华南大区运营官）

**判据**：对外交付物里没有 6862.HK 海底捞 / 6831.HK 绿茶的**未公开**经营数据、合同条款、供应商价格。
公开来源（公告、业绩会、交易所披露、公开报道、卖方转述）可以用，但要能指出出处。

**怎么查**：交付前 `grep -n "海底捞\|绿茶\|6862\|6831"` 产物，逐处问「这个数字的公开出处是什么」。
答不出出处的数字 → 当作未公开数据处理。

**不过**：删掉或换成公开口径；客户提纲里直接问未公开数据的题，答「仅能用公开口径」+ 给公开代理，
并在 Merlin 的「可以说 / 不能说」口径框里写明（如鮨、华南两份报告的做法）。**不问用户「要不要留」。**

---

## G2 · Critic 裁定（CLAUDE.md「Critic 质量门控」）

**为什么在子 agent 里跑**：我刚写完的报告，我自己评一定偏宽（profile 1.2c：自评偏差有恒定方向）。
新开一个子 agent，它没有生成过程的上下文，只能看产物本身。

**命令**（Agent 工具，subagent_type 用 general-purpose，前台运行）：
```
你是 Critic。读 .claude/skills/critic/SKILL.md 并严格按它评审：
产物：<reports/xxx.html 绝对路径>
报告类型：<Merlin 模式B / Merlin 模式A / Earner / restaurant-research / buffett / 客户文章>
只输出 SKILL.md 规定的【Critic 裁定】块，不改文件。
<若为客户文章：按 profile 1.1za，只跑 D1/D2，报告模板项（D3b 附注、D4 反馈链接）不适用。>
```

**裁定后分支**：
| 裁定 | 动作 |
|---|---|
| PASS | 进 G3 |
| CONDITIONAL | 在 Verdict Box 下方补「未核实项」说明 → 进 G3 |
| REWRITE | 按 flags 改 → **重新开一个子 agent** 再评（不复用上一个）。最多 2 轮，仍 REWRITE → 停，把 flags 交用户定 |

**不走 Critic 的**：huashu-report（PDF，自带 render.py 自检）——但手工过 D1 / D2 / D3b 三项。
期权扫描结论在对话里交付，不是 HTML 报告，不走 Critic。

**记录**：裁定结果（PASS/CONDITIONAL/REWRITE + flags 数）写进运行记录和 research-ledger 那一条。

---

## G3 · 附 PDF（profile 1.1zb）

**命令**：`node tools/render_pdf.js reports/xxx.html`（可一次传多个）
→ 同目录生成同名 .pdf；<20KB 视为空白，脚本退出码 1。

**交付**：`SendUserFile` 同时发 HTML 与 PDF，PDF 用 `display: "render"`。
PDF 被 .gitignore 忽略，不入库；HTML 是源文件。

**不过**：渲染失败 = 未交付，修好再发，不先发 HTML「PDF 稍后」。

---

## G4 · 可证伪判断登记（CLAUDE.md「可证伪判断必须登记」；predictions.md 规范 1–11）

**判据**：产物里每个「门槛数字 + 验证时点」的判断——目标价、三情景、方向、「X 季度内会 Y」、
期权「到期收在 K 之上」——都在 `memory/state/predictions.md` 待验表里有一行。

**登记时当场定**：门槛 / 验证时点（精确到读数口径，默认收盘或公告值）/ 把握档（高/中/低）。
- 路径条件（「期间每日 ≥ X」）按触线概率定档，成立概率 <50% 的只能填「低」或不登记（规范 11）。
- 预测文字与门槛列必须同为路径或同为终点条件。
- 高档占比 >70% → C4 报警，说明分档失去区分度。

**不过**：没门槛或没时点的判断，从产物里删掉或改写成有门槛的——**不要说出口**（铁律 1）。

**为什么在交付后登记**：交付前数字可能因 Critic 返工而变；登记的必须是客户最终看到的数字。

---

## G5 · 记账

| 流水线 | 写哪里 | 写什么 |
|---|---|---|
| 调研 / 财报 / 内容（含研究事实的） | `memory/state/research-ledger.md` 末尾追加 | 按台账现有格式：标题行 + 交付路径 + Critic 裁定 + 新事实 + 推测（档）+ 冲突 |
| 期权 | `memory/state/options-journal.md` | 当日扫描：闸门读数、存量复核、候选与否决理由、用户决定 |
| 期权 | `python3 tools/candidate_ledger.py add …` | **所有**候选含否决的，全量登记（C9） |
| 出现新事故 / 用户纠正 | `memory/profile.md` | 按 1.1x 编号追加，带承载物 |

**不过**：不记 = 下次研究同一标的从零重做；candidate_ledger 漏登否决项 = 排序规则永远验不了。

---

## G6 · 提交推送 + 运行记录收尾

```
git add -A && git commit -m "<流水线>：<一句话>" && git push -u origin claude/install-claude-hud-d51E6
```
推送被拒（远端常有自动抓价 / 自检提交）→ `git fetch origin <分支> && git merge --no-edit` 后重推。
运行记录状态改「完成」，写交付清单。**未 push 不算完成**——容器回收后本地提交会丢。
