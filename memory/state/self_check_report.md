# 自检报告（自动生成，勿手改）

> 由 .github/workflows/self-check.yml 生成 · 2026-11-24T06:32:03Z
> 手动重跑：`python3 tools/self_check.py` 与 `python3 tools/rule_replay.py`

## 自检器
```
自检器 · 2026-11-24 06:32 UTC
==========================================================================

[C1] Skill spoke 路径校验  (R-E3)
  humanizer-zh             hub 408 行   spoke 引用  0 处
  burry                    hub 183 行   spoke 引用  8 处
  tail-risk-monitor        hub 200 行   spoke 引用 12 处
  huashu-report            hub 179 行   spoke 引用 15 处
  sunzi-36ji               hub  65 行   spoke 引用  6 处
  earner                   hub 132 行   spoke 引用  6 处
  guizang-page-skill       hub 208 行   spoke 引用  5 处
  us-options-agent         hub 130 行   spoke 引用 10 处
  restaurant-risk-radar    hub 152 行   spoke 引用 12 处
  merlin                   hub  80 行   spoke 引用  8 处
  viral-content-agent      hub 141 行   spoke 引用  7 处
  tiandao                  hub 128 行   spoke 引用  6 处
  critic                   hub 140 行   spoke 引用  2 处
  long-running-agent-sop   hub 109 行   spoke 引用  3 处
  coo                      hub 104 行   spoke 引用 11 处
  restaurant-research-skill hub 188 行   spoke 引用 16 处
  buffett-analyst          hub 161 行   spoke 引用 10 处
  guizang-ppt-skill        hub 193 行   spoke 引用 22 处
  kami                     hub 210 行   spoke 引用 32 处
  pptagent                 hub  57 行   spoke 引用  0 处
  michael-polanyi-perspective hub 184 行   spoke 引用 16 处
  sleeper                  hub 164 行   spoke 引用  5 处
  expansion-health-tracker hub 140 行   spoke 引用 11 处
  guizang-social-card-skill hub 338 行   spoke 引用 30 处
  合计 232 处 spoke 引用，0 处失效

[C2] 孤儿规则检测：规则存在，但有没有承载物
  预测记分（1.1j）                 ✅ 承载物 predictions.md
  规则回放（1.1o）                 ✅ 承载物 rule_replay.py
  价格缓存刷新（R-D0）               ✅ 承载物 fetch-prices.yml
  spoke 路径校验（R-E3）           ✅ 承载物 self_check.py
  分项加总校验（1.1s）               ✅ 承载物 sum_check.py
  IV 锚漂移判定（1.1w）             ⚠ 人工执行（无法自动化，依赖每次自觉）
  读 JSON 前打印键名（1.1u）         ✅ 承载物 jsonsafe.py

[C3] 阈值漂移：工具与 skill 是否还在说同一套数
  被测阈值 9 个，漂移 0 个

[C4] 预测记分卡  (1.1j：不记分就学不到)
  明细 18 条｜已记分 16（排除⊘）｜✅9 ❌5｜命中率 56.2%｜待验 29 条
  分档：已分档 2 条｜建档前未分档 14 条（不参与分档统计）
        待验 29 条中 26 条已填把握档  ← 新登记都在填，规则在执行
    高 档  1 条｜✅1 ❌0｜命中率 100.0%
    中 档  1 条｜✅0 ❌0｜命中率 0.0%
  样本 2/20，**不对分档有效性下任何结论**（不到门槛就说「我高把握的准」是拿噪声当发现）

[C5] 无触发词的 skill 是否已进 CLAUDE.md 路由表
  critic                   无触发词  ✅ 已在 CLAUDE.md 路由表
  guizang-page-skill       无触发词  ✅ 已在 CLAUDE.md 路由表
  guizang-ppt-skill        无触发词  ✅ 已在 CLAUDE.md 路由表
  guizang-social-card-skill 无触发词  ✅ 已在 CLAUDE.md 路由表
  huashu-report            无触发词  ✅ 已在 CLAUDE.md 路由表
  humanizer-zh             无触发词  ✅ 已在 CLAUDE.md 路由表
  kami                     无触发词  ✅ 已在 CLAUDE.md 路由表
  pptagent                 无触发词  ✅ 已在 CLAUDE.md 路由表
  路由表点名的 skill 5 个，不存在 0 个

[C6] 可证伪判断的登记规则是否还有承载物
  CLAUDE.md 含把握档规则   ✅
  predictions.md 有把握列  ✅
  产出可证伪判断的 skill   7 个，靠 CLAUDE.md 统一约束（各自 SKILL.md 不重复写，避免 upstream 冲突）

[C7] 分项加总校验  (1.1s：加不平就写明差额去向)
  共 56 个文件｜加平 2｜舍入或已说明 1｜**差额未说明 0**｜跳过 30
  ✅ 无「加不平且未说明」的情形
  ⚠ 局限：只核**声明过**的关系。当前 1 份数据表有声明、0 份没有。
     忘了声明就不会触发 —— 这是把「每次记得加一遍」降为「记得声明一次」，不是消灭自觉。

[C8] 键名静默失效防线  (1.1u：.get() 对拼错的键不报错)
  严格加载器：已迁 6 个脚本，未迁 8 个（迁移是渐进的，不判失败）
  不可能值守卫在产出点：✅ 已接
  自测（拿 2026-09-06 真实汇总回放）：✅ 抓得住且正常分布零误报

[C9] 期权候选全量登记  (缓冲÷1σ 排序能否被结算检验)
  已登记 266 条（否决 173）｜最近登记 2026-11-18

[C10] COO 流水线引用与运行记录
  pipeline-content.md        ✅ 7 个 skill
  pipeline-earnings.md       ✅ 2 个 skill
  pipeline-options.md        ✅ 2 个 skill
  pipeline-research.md       ✅ 4 个 skill
  期权基本面名单：上次复核 2026-11-05（19 天前）
  运行记录：20 份｜超过 2 天未完成 2 份

[C11] 反馈台账 memory/state/feedback.jsonl
  64 条｜未关闭 3｜已修有测试 35

[C12] 扫描报告核对 memory/state/scans
  已交付报告 10 份

[C13] 报告机械检查记录 memory/state/report_checks.jsonl
  11/07 起改动的报告 5 份｜有检查记录 2

[C14] 筛选器产物不变量 tools/screen_check.py
  burry：7 项，FAIL 0
  ses：6 项，FAIL 0

[C15] 宏观日历 memory/state/macro_calendar.json
  CPI 未来 45 天：['2026-12-10']
  NFP 未来 45 天：['2026-12-04', '2027-01-08']
  PPI 未来 45 天：['2026-12-15']
  FOMC 未来 9 次｜来源 2026-11-24T04:52:35+00:00｜错误 None

[C16] 天道决策卡 memory/state/tiandao/cards/
  共 1 张

==========================================================================
发现 14 项：

  [P1] predictions.md
        3 条预测已到验证时点但仍标「待验」：2026-11-13 XLE 收盘不低于 63（11/13 收盘；z 1.33；2026-11-20 UBER 收盘不低于 62（11/20 收盘；z 1.2；2026-11-13 AMD 收盘不低于 442.5（11/13 收盘；用户自

  [P1] FB-20261124-M02
        指向的测试不存在：tests/test_merlin_check.py::test_m10_evidence_gap_fails；fixtures good/bad 回归（测试被删或改名，修复失去保护）

  [P1] reports/haidilao_2027_dd_Research_Report.html
        交付的报告没跑过 report_check --record（Critic Step 0）

  [P1] reports/haidilao_h1_2026_review_Research_Report.html
        交付的报告没跑过 report_check --record（Critic Step 0）

  [P1] reports/haidilao_hr_org_2026_Research_Report.html
        交付的报告没跑过 report_check --record（Critic Step 0）

  [P2] memory/state/runs
        运行记录烂尾：2026-11-12_options_daily.md（未写状态，12 天） — 续跑或标「放弃」

  [P2] memory/state/runs
        运行记录烂尾：2026-11-18_options_intraday_1052ET.md（未写状态，6 天） — 续跑或标「放弃」

  [P3] humanizer-zh/SKILL.md
        hub 408 行，超 CLAUDE.md 的 200 行目标 208 行

  [P3] guizang-page-skill/SKILL.md
        hub 208 行，超 CLAUDE.md 的 200 行目标 8 行

  [P3] kami/SKILL.md
        hub 210 行，超 CLAUDE.md 的 200 行目标 10 行

  [P3] guizang-social-card-skill/SKILL.md
        hub 338 行，超 CLAUDE.md 的 200 行目标 138 行

  [P3] FB-20261107-B04
        未关闭：burry_screener 债务标签只认 LongTermDebtNoncurrent / LongTermDebt；｜debt_lt / debt_st 追加 LongTermDebtAndCapitalLeaseOb

  [P3] FB-20261109-B10
        未关闭：TTM 规则（11/09）对 11/07 已交付的 KO 同样适用（FY2025 已结束 10 个月），KO 未重跑｜KO 安全边际 −97%，换基数不改变结论；用户要求时重跑

  [P3] FB-20261111-O03
        未关闭：卖 call 保证金严重低估：option_quote 的 Reg-T 估算 HOOD 108C 每张 $874（10%｜待定：只有 1 个数据点，平台公式未知（20%×现价+权利金 不扣价外额 ≈ $1,714，也对不上

```

## 规则回放
```
```
