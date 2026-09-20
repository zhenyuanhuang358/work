#!/usr/bin/env python3
"""自检器 — 把 profile.md 里「答应记住的规则」变成会自己跑的检查。

## 为什么需要它

2026-09-15 的诊断：profile.md 739 行、24 条事故教训，但其中**大多数规则没有任何承载物**，
全靠「我记得」。后果已经出现过两次：

  · 期限溢价 ≥1.20 这条每天用于开仓裁定的规则，三周里从未被写进任何 skill 文件
  · profile 1.1j 立的「预测必须逐条记分」，从 2026-08-25 至今从未被执行过一次

> **一条规则在拿到承载物之前不算立住。承诺记住不是机制。**

本脚本承载可自动化的那部分；不可自动化的，至少要在这里被点名。

用法：
    python3 tools/self_check.py            # 全部检查
    python3 tools/self_check.py --quiet    # 只输出问题
"""
import os, re, sys, subprocess, json

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUIET = "--quiet" in sys.argv
findings = []


def say(*a):
    if not QUIET:
        print(*a)


def flag(level, where, msg):
    findings.append((level, where, msg))


# ── C1 · Skill spoke 路径校验（profile R-E3，此前全靠人工） ──────────────────
def check_spokes():
    say("\n[C1] Skill spoke 路径校验  (R-E3)")
    skdir = os.path.join(REPO, ".claude/skills")
    n_ref = n_bad = 0
    for root, _, files in os.walk(skdir):
        if "SKILL.md" not in files:
            continue
        hub = os.path.join(root, "SKILL.md")
        txt = open(hub, encoding="utf-8").read()
        name = os.path.basename(root)
        for m in re.finditer(r"`(references/[A-Za-z0-9_\-./]+\.md)`", txt):
            n_ref += 1
            tgt = os.path.join(root, m.group(1))
            if not os.path.exists(tgt):
                n_bad += 1
                flag("P1", f"{name}/SKILL.md", f"spoke 路径不存在：{m.group(1)}")
        # hub 行数（CLAUDE.md 目标 ≤200）
        ln = len(txt.splitlines())
        if ln > 200:
            flag("P3", f"{name}/SKILL.md", f"hub {ln} 行，超 CLAUDE.md 的 200 行目标 {ln-200} 行")
        say(f"  {name:<24} hub {ln:>3} 行   spoke 引用 {len(re.findall(r'`references/', txt)):>2} 处")
    say(f"  合计 {n_ref} 处 spoke 引用，{n_bad} 处失效")


# ── C2 · 孤儿规则检测：profile 里有规则，仓库里没有承载物 ────────────────────
# 这是本脚本最「元」的一项：它检查的是改进机制本身有没有落地。
CARRIERS = [
    # (规则关键词, 规则名, 承载物判据 — 文件名片段或 None 表示「必须人工执行」)
    (r"逐条记分|必须逐条|不记分就学不到", "预测记分（1.1j）", "predictions.md"),
    (r"回放|触发率|一刀切.*触发",           "规则回放（1.1o）", "rule_replay.py"),
    (r"期权扫描前.*必须先.*(价格|缓存)",     "价格缓存刷新（R-D0）", "fetch-prices.yml"),
    (r"spoke 路径是否真实存在|主动验证所有 spoke", "spoke 路径校验（R-E3）", "self_check.py"),
    (r"自己先加一遍|分项加总",               "分项加总校验（1.1s）", None),
    (r"OTM 漂移超 5pct|锚失效",             "IV 锚漂移判定（1.1w）", None),
    (r"print\(list\(d\.keys|先 `print",      "读 JSON 前打印键名（1.1u）", None),
]


def check_orphan_rules():
    say("\n[C2] 孤儿规则检测：规则存在，但有没有承载物")
    prof = open(os.path.join(REPO, "memory/profile.md"), encoding="utf-8").read()
    inventory = []
    for d in ("tools", "scripts", ".github/workflows", "memory/state"):
        p = os.path.join(REPO, d)
        if os.path.isdir(p):
            inventory += os.listdir(p)
    blob = " ".join(inventory)
    for pat, name, carrier in CARRIERS:
        exists = bool(re.search(pat, prof))
        if not exists:
            say(f"  {name:<26} 规则未在 profile 中找到 — 跳过")
            continue
        if carrier is None:
            say(f"  {name:<26} ⚠ 人工执行（无法自动化，依赖每次自觉）")
            continue
        if carrier in blob:
            say(f"  {name:<26} ✅ 承载物 {carrier}")
        else:
            flag("P2", name, f"规则在 profile 中存在，但仓库里找不到承载物（预期 {carrier}）"
                             f" — 这条规则目前只靠「我记得」，历史上这类规则的失效率是 100%")


# ── C3 · 阈值漂移：skill 里的数字 vs 工具里的数字 ────────────────────────────
def check_threshold_drift():
    say("\n[C3] 阈值漂移：工具与 skill 是否还在说同一套数")
    rr = os.path.join(REPO, "tools/rule_replay.py")
    sk = os.path.join(REPO, ".claude/skills/tail-risk-monitor/SKILL.md")
    if not (os.path.exists(rr) and os.path.exists(sk)):
        return
    rtxt, stxt = open(rr, encoding="utf-8").read(), open(sk, encoding="utf-8").read()
    lits = set(re.findall(r"\b(?:0\.95|1\.00|1\.20|140|150|100|120|20|25)\b",
                          rtxt.split("# ── 被测规则")[1].split("def ")[0]))
    bad = [l for l in sorted(lits) if l not in stxt]
    if bad:
        flag("P2", "rule_replay vs SKILL.md", f"工具使用的阈值在 SKILL.md 中找不到：{', '.join(bad)}")
    say(f"  被测阈值 {len(lits)} 个，漂移 {len(bad)} 个")


# ── C4 · 预测记分卡到期提醒（承载 1.1j） ─────────────────────────────────────
def check_predictions():
    say("\n[C4] 预测记分卡  (1.1j：不记分就学不到)")
    p = os.path.join(REPO, "memory/state/predictions.md")
    if not os.path.exists(p):
        flag("P2", "predictions.md", "记分卡不存在 — 1.1j 自 2026-08-25 立规至今从未执行")
        return
    txt = open(p, encoding="utf-8").read()
    # 只解析「## 明细」段：待验表另算，混在一起会把命中率算错
    detail = txt.split("## 明细")[1].split("## 待验")[0] if "## 明细" in txt else ""
    pend   = txt.split("## 待验")[1].split("## 登记规范")[0] if "## 待验" in txt else ""
    rows = re.findall(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|(.+)$", detail, re.M)
    prows = re.findall(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|(.+)$", pend, re.M)
    import datetime
    today = datetime.date.today().isoformat()
    due = [r for r in prows if r[0] <= today]
    scored = [r for r in rows if "待验" not in r[1] and "⊘" not in r[1]]
    hit = sum(1 for r in scored if "✅" in r[1])
    miss = sum(1 for r in scored if "❌" in r[1])
    say(f"  明细 {len(rows)} 条｜已记分 {len(scored)}（排除⊘）｜✅{hit} ❌{miss}"
        + (f"｜命中率 {hit/len(scored)*100:.1f}%" if scored else "") + f"｜待验 {len(prows)} 条")
    # 与文件里手写的汇总对账——自评偏差方向恒定，必须机器核
    m = re.search(r"命中率（✅ ÷ 已记分）\*\* \| \*\*([\d.]+)%", txt)
    if m and scored and abs(float(m.group(1)) - hit/len(scored)*100) > 0.5:
        flag("P1", "predictions.md",
             f"手写汇总命中率 {m.group(1)}% 与机器计算 {hit/len(scored)*100:.1f}% 不符 — "
             f"自评偏差方向恒定对自己有利，以机器为准")
    if due:
        flag("P1", "predictions.md",
             f"{len(due)} 条预测已到验证时点但仍标「待验」：" +
             "；".join(f"{d} {t.split('|')[0].strip()[:28]}" for d, t in due[:5]))
    else:
        say("  无到期未记分项")

    # ── 分档统计（承载登记规范第 10 条，2026-09-20 立）────────────────────
    # 为什么要机器做：第 10 条最容易被违反的方式不是忘记填，是**全填「高」**。
    # 白皮书 8.1 已论证：任务难度分布窄时校准是平凡满足的——
    # 全判高把握就能让高档看起来很准。所以配额检查必须是装置，不是叮嘱。
    TIER_COL = 3                 # 明细表把握列的位置（验证时点|预测|门槛|把握|结果|记分）
    TIERS = ("高", "中", "低")
    tally = {k: [0, 0, 0] for k in TIERS}        # 档 -> [已记分, ✅, ❌]
    unfiled = 0
    for d, rest in rows:
        cells = [c.strip() for c in ("|" + rest).split("|")]
        tier = cells[TIER_COL] if len(cells) > TIER_COL else ""
        if "待验" in rest or "⊘" in rest:
            continue
        if tier not in TIERS:
            unfiled += 1
            continue
        tally[tier][0] += 1
        tally[tier][1] += "✅" in rest
        tally[tier][2] += "❌" in rest
    n_tiered = sum(v[0] for v in tally.values())
    # 待验表里带把握档的条数 —— 这是新规则有没有被执行的**领先指标**。
    # 已记分那边要等验证时点到期才动，等它涨太慢；待验这边是当场就能看出来的。
    pend_tiered = sum(1 for _, rest in prows
                      if any(f"| {k} " in "|" + rest or f"**{k}**" in rest for k in TIERS))
    say(f"  分档：已分档 {n_tiered} 条｜建档前未分档 {unfiled} 条（不参与分档统计）")
    say(f"        待验 {len(prows)} 条中 {pend_tiered} 条已填把握档"
        + ("  ← 新登记都在填，规则在执行" if pend_tiered else
           "  ⚠ 一条都没填 —— 规则立了但没在执行"))
    for k in TIERS:
        n, h, m2 = tally[k]
        if n:
            say(f"    {k} 档  {n} 条｜✅{h} ❌{m2}｜命中率 {h/n*100:.1f}%")
    if n_tiered < 20:
        say(f"  样本 {n_tiered}/20，**不对分档有效性下任何结论**"
            f"（不到门槛就说「我高把握的准」是拿噪声当发现）")
    else:
        hi_share = tally["高"][0] / n_tiered
        if hi_share > 0.70:
            flag("P1", "predictions.md",
                 f"高档占比 {hi_share:.0%} > 70% — 分档失去区分度。"
                 f"若我不敢把任何一条标成「低」，这个分档就是装饰（登记规范第 10 条配额自检）")
        hi = tally["高"]; lo = tally["低"]
        if hi[0] and lo[0]:
            gap = hi[1]/hi[0] - lo[1]/lo[0]
            say(f"  高低档命中率落差 {gap*100:+.1f}pp — "
                + ("差得开，高档可据以行动" if gap > 0.15 else
                   "**差不开：我的自我评估没有信息量，所有判断应一视同仁打折**"))


# ── C6 · 「可证伪判断必须登记并带把握档」这条规则有没有承载物 ─────────────
# 2026-09-20 立。为什么需要它：predictions.md 的登记规范立了近一个月，
# 而 12 个会产出可证伪判断的 skill **零个引用它**——规则有了，
# 该触发它的东西都不知道它存在（profile 1.2a）。
# 解法是把规则写进 CLAUDE.md（永远加载），这个检查确保它不被某次编辑悄悄删掉，
# 且 predictions.md 的表结构与之匹配。
def check_forecast_rule():
    say("\n[C6] 可证伪判断的登记规则是否还有承载物")
    claude = os.path.join(REPO, "CLAUDE.md")
    ctxt = open(claude, encoding="utf-8").read() if os.path.exists(claude) else ""
    ok_rule = "把握档" in ctxt and "predictions.md" in ctxt
    say(f"  CLAUDE.md 含把握档规则   {'✅' if ok_rule else '❌ 规则已从 CLAUDE.md 消失'}")
    if not ok_rule:
        flag("P1", "CLAUDE.md",
             "「可证伪判断必须登记并带把握档」不在 CLAUDE.md 里 —— "
             "12 个 skill 没有一个自己引用 predictions.md，删掉这段等于这条规则失效")

    pf = os.path.join(REPO, "memory/state/predictions.md")
    ptxt = open(pf, encoding="utf-8").read() if os.path.exists(pf) else ""
    has_col = "| 把握 |" in ptxt
    say(f"  predictions.md 有把握列  {'✅' if has_col else '❌ 表结构与规则不符'}")
    if not has_col:
        flag("P1", "predictions.md", "待验/明细表缺「把握」列 —— C4 的分档统计会一直数出 0")

    # 会产出可证伪判断的 skill 清单——数量变了要知道（新装 skill 时提醒）
    skdir = os.path.join(REPO, ".claude/skills")
    pat = re.compile(r"目标价|三情景|内在价值|安全边际|PoP|定价缺口|领先.{0,6}季度")
    producers = [n for n in sorted(os.listdir(skdir))
                 if os.path.exists(os.path.join(skdir, n, "SKILL.md"))
                 and pat.search(open(os.path.join(skdir, n, "SKILL.md"), encoding="utf-8").read())]
    say(f"  产出可证伪判断的 skill   {len(producers)} 个，靠 CLAUDE.md 统一约束"
        f"（各自 SKILL.md 不重复写，避免 upstream 冲突）")


# ── C5 · 无触发词的 skill 必须在 CLAUDE.md 路由表里有一行 ───────────────────
# 2026-09-15 装 huashu-report 时发现的缺口：它的 frontmatter 零触发词，
# 而 Merlin/Earner/restaurant-research 都有，于是「帮我做个报告」永远被前三个截胡。
# 这类缺口在装任何第三方 skill 时都会重现，所以要检测而不是记住。
def check_skill_routing():
    say("\n[C5] 无触发词的 skill 是否已进 CLAUDE.md 路由表")
    claude = os.path.join(REPO, "CLAUDE.md")
    ctxt = open(claude, encoding="utf-8").read() if os.path.exists(claude) else ""
    skdir = os.path.join(REPO, ".claude/skills")
    n_no_trigger = 0
    for name in sorted(os.listdir(skdir)):
        hub = os.path.join(skdir, name, "SKILL.md")
        if not os.path.exists(hub):
            continue
        txt = open(hub, encoding="utf-8").read()
        # ⚠ 首跑假阳性修正（2026-09-15）：michael-polanyi 的触发短语写在 description 里，
        #   用「」逐个列举，只是没用「触发词」这三个字。只认字面串会误报。
        #   判据应是「有没有可匹配的短语」，不是「有没有用某个词来标注它们」。
        #   修检测器不改 skill（1.1p：宁可漏报也不要习惯性误报）。
        fm = txt.split("---")[1] if txt.count("---") >= 2 else txt
        quoted = re.findall(r"[「『][^」』]{2,20}[」』]", fm)
        has_trigger = ("触发词" in txt or "唤醒口令" in txt or len(quoted) >= 3)
        if has_trigger:
            continue
        n_no_trigger += 1
        routed = name in ctxt
        say(f"  {name:<24} 无触发词  {'✅ 已在 CLAUDE.md 路由表' if routed else '❌ 未进路由表'}")
        if not routed:
            flag("P2", name,
                 "该 skill 的 frontmatter 没有触发词，且 CLAUDE.md 里没有它的路由规则 — "
                 "它只能靠 description 语义匹配，会被有触发词的同类 skill 截胡。"
                 "解法：在 CLAUDE.md 路由表加一行（不要改第三方文件，upstream 更新会冲突）")
    if n_no_trigger == 0:
        say("  所有 skill 都有触发词，无需路由兜底")


def main():
    print("自检器 · " + subprocess.run(["date", "-u", "+%Y-%m-%d %H:%M UTC"],
                                     capture_output=True, text=True).stdout.strip())
    print("=" * 74)
    check_spokes()
    check_orphan_rules()
    check_threshold_drift()
    check_predictions()
    check_skill_routing()
    check_forecast_rule()
    print("\n" + "=" * 74)
    if not findings:
        print("全部通过。")
        return 0
    order = {"P1": 0, "P2": 1, "P3": 2}
    findings.sort(key=lambda f: order.get(f[0], 9))
    print(f"发现 {len(findings)} 项：\n")
    for lv, where, msg in findings:
        print(f"  [{lv}] {where}\n        {msg}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
