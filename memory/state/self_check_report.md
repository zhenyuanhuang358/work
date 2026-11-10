# 自检报告（自动生成，勿手改）

> 由 .github/workflows/self-check.yml 生成 · 2026-11-10T17:23:40Z
> 手动重跑：`python3 tools/self_check.py` 与 `python3 tools/rule_replay.py`

## 自检器
```
自检器 · 2026-11-10 17:23 UTC
==========================================================================

[C1] Skill spoke 路径校验  (R-E3)
  tail-risk-monitor        hub 200 行   spoke 引用 12 处
  guizang-page-skill       hub 208 行   spoke 引用  5 处
  pptagent                 hub  57 行   spoke 引用  0 处
  sleeper                  hub 164 行   spoke 引用  5 处
  expansion-health-tracker hub 140 行   spoke 引用 11 处
  kami                     hub 210 行   spoke 引用 32 处
  long-running-agent-sop   hub 109 行   spoke 引用  3 处
  us-options-agent         hub 127 行   spoke 引用  8 处
  merlin                   hub 181 行   spoke 引用  1 处
  humanizer-zh             hub 408 行   spoke 引用  0 处
  huashu-report            hub 179 行   spoke 引用 15 处
  guizang-social-card-skill hub 338 行   spoke 引用 30 处
  coo                      hub 104 行   spoke 引用 11 处
  buffett-analyst          hub 161 行   spoke 引用 10 处
  michael-polanyi-perspective hub 184 行   spoke 引用 16 处
  viral-content-agent      hub 141 行   spoke 引用  7 处
  restaurant-research-skill hub 187 行   spoke 引用 16 处
  earner                   hub 132 行   spoke 引用  6 处
  critic                   hub 140 行   spoke 引用  2 处
  guizang-ppt-skill        hub 193 行   spoke 引用 22 处
  tiandao                  hub 128 行   spoke 引用  6 处
  restaurant-risk-radar    hub 152 行   spoke 引用 12 处
  burry                    hub 183 行   spoke 引用  8 处
  合计 217 处 spoke 引用，0 处失效

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
  明细 18 条｜已记分 16（排除⊘）｜✅9 ❌5｜命中率 56.2%｜待验 28 条
  无到期未记分项
  分档：已分档 2 条｜建档前未分档 14 条（不参与分档统计）
        待验 28 条中 25 条已填把握档  ← 新登记都在填，规则在执行
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
  共 52 个文件｜加平 2｜舍入或已说明 1｜**差额未说明 0**｜跳过 30
  ✅ 无「加不平且未说明」的情形
  ⚠ 局限：只核**声明过**的关系。当前 1 份数据表有声明、0 份没有。
     忘了声明就不会触发 —— 这是把「每次记得加一遍」降为「记得声明一次」，不是消灭自觉。

[C8] 键名静默失效防线  (1.1u：.get() 对拼错的键不报错)
  严格加载器：已迁 6 个脚本，未迁 8 个（迁移是渐进的，不判失败）
  不可能值守卫在产出点：✅ 已接
  自测（拿 2026-09-06 真实汇总回放）：✅ 抓得住且正常分布零误报

[C9] 期权候选全量登记  (缓冲÷1σ 排序能否被结算检验)
  已登记 236 条（否决 165）｜最近登记 2026-11-10

[C10] COO 流水线引用与运行记录
  pipeline-content.md        ✅ 7 个 skill
  pipeline-earnings.md       ✅ 2 个 skill
  pipeline-options.md        ✅ 2 个 skill
  pipeline-research.md       ✅ 4 个 skill
  期权基本面名单：上次复核 2026-11-05（5 天前）
  运行记录：11 份｜超过 2 天未完成 0 份

[C11] 反馈台账 memory/state/feedback.jsonl
  60 条｜未关闭 2｜已修有测试 33

[C12] 扫描报告核对 memory/state/scans
  已交付报告 7 份

[C13] 报告机械检查记录 memory/state/report_checks.jsonl
  11/07 起改动的报告 1 份｜有检查记录 1

[C14] 筛选器产物不变量 tools/screen_check.py
  burry：7 项，FAIL 0
  ses：6 项，FAIL 0

[C15] 宏观日历 memory/state/macro_calendar.json
  CPI 未来 45 天：['2026-11-10', '2026-12-10']
  NFP 未来 45 天：['2026-12-04']
  PPI 未来 45 天：['2026-11-13', '2026-12-15']
  FOMC 未来 9 次｜来源 2026-11-10T17:17:04+00:00｜错误 None

[C16] 天道决策卡 memory/state/tiandao/cards/
  共 1 张

==========================================================================
发现 6 项：

  [P3] guizang-page-skill/SKILL.md
        hub 208 行，超 CLAUDE.md 的 200 行目标 8 行

  [P3] kami/SKILL.md
        hub 210 行，超 CLAUDE.md 的 200 行目标 10 行

  [P3] humanizer-zh/SKILL.md
        hub 408 行，超 CLAUDE.md 的 200 行目标 208 行

  [P3] guizang-social-card-skill/SKILL.md
        hub 338 行，超 CLAUDE.md 的 200 行目标 138 行

  [P3] FB-20261107-B04
        未关闭：burry_screener 债务标签只认 LongTermDebtNoncurrent / LongTermDebt；｜debt_lt / debt_st 追加 LongTermDebtAndCapitalLeaseOb

  [P3] FB-20261109-B10
        未关闭：TTM 规则（11/09）对 11/07 已交付的 KO 同样适用（FY2025 已结束 10 个月），KO 未重跑｜KO 安全边际 −97%，换基数不改变结论；用户要求时重跑

```

## 规则回放
```
规则回放 · 74 个交易日 · 2026-08-03 至 2026-11-10
==============================================================================

[1] 各指标在三档中的停留比例（死条款 / 恒触发条款检测）
  term_structure   绿  90.5%   黄   6.8%   红   2.7%   观测 0.77–1.08  首档阈值 0.95  距极值 -12.2%
                   └ 近 20 日非绿档占比 35%（常驻线 80%）
  skew             绿  14.9%   黄  51.4%   红  33.8%   观测 126.41–168.59  首档阈值 140  距极值 -17.0%
                   └ 近 20 日非绿档占比 100%（常驻线 80%）  → 判为常驻项，应剔除出共振计数
  vvix             绿  83.8%   黄  13.5%   红   2.7%   观测 82.59–124.24  首档阈值 100  距极值 -19.5%
                   └ 近 20 日非绿档占比 55%（常驻线 80%）
  vix              绿  93.2%   黄   4.1%   红   2.7%   观测 14.21–26.60  首档阈值 20  距极值 -24.8%
                   └ 近 20 日非绿档占比 25%（常驻线 80%）

[2] 灯色分布
  绿灯   60 天   81.1%
  黄灯    1 天    1.4%
  红灯   13 天   17.6%

[3] 非绿档由谁贡献（共振规则的真实基础）
  term_structure     7/74 天贡献非绿档  (  9.5%)
  skew              63/74 天贡献非绿档  ( 85.1%)
  vvix              12/74 天贡献非绿档  ( 16.2%)
  vix                5/74 天贡献非绿档  (  6.8%)

  非绿档组合分布：
    skew                                50 天   67.6%
    （全绿）                                11 天   14.9%
    skew + vvix                          6 天    8.1%
    skew + term_structure + vix + vvix   5 天    6.8%
    skew + term_structure + vvix         1 天    1.4%
    skew + term_structure                1 天    1.4%

[4] 加速度条款触发率（1.1o 的门槛校准检查）
  任一触发：9/74 天  (12.2%)
    term_structure   1d >10%    1 天    1.4%
    term_structure   3d >20%    0 天    0.0%
    skew             1d >10%    0 天    0.0%
    skew             3d >20%    0 天    0.0%
    vvix             1d >10%    4 天    5.4%
    vvix             3d >20%    2 天    2.7%
    vix              1d >10%    5 天    6.8%
    vix              3d >20%    5 天    6.8%

  各指标平均单日绝对变动（门槛是否该共用的依据）：
    term_structure   2.95%   (10% 门槛 = 其常态的 3.4 倍)
    skew             1.68%   (10% 门槛 = 其常态的 6.0 倍)
    vvix             4.55%   (10% 门槛 = 其常态的 2.2 倍)
    vix              5.89%   (10% 门槛 = 其常态的 1.7 倍)

[5] 期限溢价开窗率（VIX3M/VIX ≥ 1.20）
  开窗 22/74 天  (29.7%)   区间 0.924 – 1.295

[6] 阈值漂移检查（本脚本 vs SKILL.md）
  未发现漂移

==============================================================================
发现 1 项，按严重度排列：

  1. [常驻项] skew
     近 20 个交易日 100% 处于非绿档（全期 85%）— 它是常态水平不是异常信号，在共振计数里构成常驻 +1，使「≥2 项共振」退化为「≥1 项」。按 SKILL.md「常驻项剔除」应降为观察项

```
