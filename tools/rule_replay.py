#!/usr/bin/env python3
"""规则回放器 — 拿历史数据回放我自己定的规则，看它们实际触发成什么样。

为什么需要它（来自三次同类事故）：
  2026-09-01  VIX9D 用 10% 通用门槛 → 实测触发率 33%，那不是警报是噪音
  2026-09-08  混龄「一刀切作废」规则 → 首次使用即发现它每次盘中都会触发
  2026-09-11  加速度条款未限定方向 → 波动率崩塌时反而要上调灯色

三次都是「规则在真实场景里跑出了与立意相反的结果」，而且三次都是
**用到了才发现**。这个脚本把「用到才发现」变成「写完就能测」。

判据不是代码整洁度，是：**这条规则会不会静默地产出错误结论。**

用法：
    python3 tools/rule_replay.py              # 回放 + 报告
    python3 tools/rule_replay.py --json       # 机器可读输出
"""
import json, subprocess, sys, os
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANCH = "claude/install-claude-hud-d51E6"

# ── 被测规则：与 .claude/skills/tail-risk-monitor/SKILL.md 保持同步 ────────────
# 若 SKILL.md 改了阈值而这里没改，DRIFT 检查会报警。
BANDS = {
    # 指标名: [(上界, 灯色分), ...] 升序，最后一档为 None 表示无上界
    "term_structure": [(0.95, 0), (1.00, 1), (None, 2)],
    "skew":           [(140,  0), (150,  1), (None, 2)],
    "vvix":           [(100,  0), (120,  1), (None, 2)],
    "vix":            [(20,   0), (25,   1), (None, 2)],
}
SCORED = list(BANDS)                    # 加速度条款的定义域（VIX9D 已于 9/1 排除）
ACCEL_1D = 0.10                         # 单日 >10%
ACCEL_3D = 0.20                         # 三日累计 >20%
ACCEL_UPWARD_ONLY = True                # 9/11 修正：方向限定为上行
RESONANCE_MIN = 2                       # ≥2 项共振才变灯
RESIDENT_WINDOW = 20                    # 常驻项判定窗口（必须与 SKILL.md 的「近 20 个交易日」一致）
RESIDENT_THRESHOLD = 0.80               # 窗口内 >80% 非绿档 → 常驻项
SKEW_NEVER_ALONE = True                 # 铁律：SKEW 不得单独触发红灯
TERM_PREMIUM_OPEN = 1.20                # 30-45 天窗口开启线


def load_history():
    out = subprocess.run(["git", "log", "--format=%H", "--reverse", BRANCH,
                          "--", "stock_prices.json"],
                         capture_output=True, text=True, cwd=REPO).stdout.split()
    rows = []
    for c in out:
        raw = subprocess.run(["git", "show", f"{c}:stock_prices.json"],
                             capture_output=True, text=True, cwd=REPO).stdout
        try:
            d = json.loads(raw)
        except Exception:
            continue
        t = d.get("tail_risk") or {}
        if not t or d.get("vix") is None:
            continue
        vix, v3m, v9d = d["vix"], t.get("vix3m"), t.get("vix9d")
        rows.append({
            "ts": d.get("updated_at", ""),
            "vix": vix, "vix9d": v9d, "vix3m": v3m,
            "skew": t.get("skew"), "vvix": t.get("vvix"),
            "term_structure": (vix / v3m) if v3m else None,
            "term_premium":   (v3m / vix) if vix else None,
        })
    return rows


def daily_closes(rows):
    """每个自然日取最后一条读数作为当日收盘。"""
    by_day = {}
    for r in rows:
        by_day[r["ts"][:10]] = r
    return [by_day[d] for d in sorted(by_day)]


def band_of(metric, v):
    if v is None:
        return None
    for hi, score in BANDS[metric]:
        if hi is None or v < hi:
            return score
    return None


def replay(days):
    recs = []
    for i, d in enumerate(days):
        scores = {m: band_of(m, d.get(m)) for m in SCORED}
        avail = {m: s for m, s in scores.items() if s is not None}
        # 共振数 = 非绿档（得分≥1）的指标个数
        non_green = [m for m, s in avail.items() if s >= 1]
        light = 0
        if len(non_green) >= RESONANCE_MIN:
            light = max(avail[m] for m in non_green)
        if SKEW_NEVER_ALONE and non_green == ["skew"]:
            light = 0
        # 加速度
        accel = []
        if i >= 1:
            for m in SCORED:
                a, b = days[i-1].get(m), d.get(m)
                if a and b:
                    ch = b / a - 1
                    if abs(ch) > ACCEL_1D and (ch > 0 or not ACCEL_UPWARD_ONLY):
                        accel.append((m, "1d", ch))
        if i >= 3:
            for m in SCORED:
                a, b = days[i-3].get(m), d.get(m)
                if a and b:
                    ch = b / a - 1
                    if abs(ch) > ACCEL_3D and (ch > 0 or not ACCEL_UPWARD_ONLY):
                        accel.append((m, "3d", ch))
        recs.append({"day": d["ts"][:10], "scores": scores, "non_green": non_green,
                     "light": min(2, light + (1 if accel else 0)), "base_light": light,
                     "accel": accel, "term_premium": d.get("term_premium")})
    return recs


def pct(n, d):
    return 0.0 if not d else n / d * 100


def main():
    rows = load_history()
    days = daily_closes(rows)
    recs = replay(days)
    N = len(recs)
    findings = []

    print(f"规则回放 · {N} 个交易日 · {recs[0]['day']} 至 {recs[-1]['day']}")
    print("=" * 78)

    # ── 1. 每个指标各档位的停留比例 ──────────────────────────────────────
    # ⚠ 死条款的判据不是「从未触发」——样本期平静也会导致从未触发。
    #   真正的死条款是「阈值远离观测区间，实际上够不着」。
    #   2026-09-15 首跑时原判据把 term_structure 与 VIX 报成死条款，是假阳性：
    #   二者阈值距观测极值仅 5.1% / 12.1%，完全够得着。
    #   修检测器而不是修规则（profile 1.1p：会喊狼来了的检测器最终会被忽略）。
    DEAD_GAP = 0.25   # 阈值距观测极值超过此比例才判死条款
    print("\n[1] 各指标在三档中的停留比例（死条款 / 恒触发条款检测）")
    for m in SCORED:
        vals = [r_["scores"][m] for r_ in recs if r_["scores"][m] is not None]
        raw = [days[i].get(m) for i in range(len(days)) if days[i].get(m) is not None]
        c = Counter(vals)
        n = len(vals)
        g, y, rd = pct(c[0], n), pct(c[1], n), pct(c[2], n)
        first_thr = BANDS[m][0][0]
        # SKEW 方向相反：值越低越好，绿档是 < 阈值
        lower_is_green = True
        gap = (first_thr - max(raw)) / max(raw) if raw else 0
        print(f"  {m:<16} 绿 {g:5.1f}%   黄 {y:5.1f}%   红 {rd:5.1f}%"
              f"   观测 {min(raw):.2f}–{max(raw):.2f}  首档阈值 {first_thr}  距极值 {gap:+.1%}")
        if g == 100.0:
            if gap > DEAD_GAP:
                findings.append(("死条款", m,
                                 f"{n} 个交易日全部在绿档，且阈值 {first_thr} 距观测极值 "
                                 f"{max(raw):.2f} 还有 {gap:.0%} — 阈值够不着，该指标对灯色无贡献"))
            else:
                print(f"  {'':<16} └ 样本期未触发，但阈值距极值仅 {gap:.1%}，够得着，不判死条款")
        # ⚠ 常驻项判定必须用与规则相同的窗口。
        #   SKILL.md 定义的是「近 20 个交易日 >80% 非绿档」，而本检测器一度用了全部历史，
        #   导致本地（22 天）与 CI（34 天，fetch-depth:0）给出相反结论。
        #   2026-09-15 CI 首跑暴露——工具与规则的窗口必须一致，同阈值漂移是同一类问题。
        w = vals[-RESIDENT_WINDOW:]
        if w:
            ng_ratio = sum(1 for v in w if v >= 1) / len(w)
            print(f"  {'':<16} └ 近 {len(w)} 日非绿档占比 {ng_ratio:.0%}"
                  f"（常驻线 {RESIDENT_THRESHOLD:.0%}）"
                  f"{'  → 判为常驻项，应剔除出共振计数' if ng_ratio > RESIDENT_THRESHOLD else ''}")
            if ng_ratio > RESIDENT_THRESHOLD:
                findings.append(("常驻项", m,
                                 f"近 {len(w)} 个交易日 {ng_ratio:.0%} 处于非绿档（全期 {100-g:.0f}%）— "
                                 f"它是常态水平不是异常信号，在共振计数里构成常驻 +1，"
                                 f"使「≥{RESONANCE_MIN} 项共振」退化为「≥{RESONANCE_MIN-1} 项」。"
                                 f"按 SKILL.md「常驻项剔除」应降为观察项"))

    # ── 2. 灯色分布 ─────────────────────────────────────────────────────
    print("\n[2] 灯色分布")
    c = Counter(r["light"] for r in recs)
    for k, name in [(0, "绿"), (1, "黄"), (2, "红")]:
        print(f"  {name}灯  {c[k]:3d} 天  {pct(c[k], N):5.1f}%")
    if pct(c[0], N) == 100.0:
        findings.append(("闸门空转", "light", "全期绿灯 — 这个闸门在观测区间内从未改变过任何决策"))

    # ── 3. 共振结构：谁在贡献非绿档 ─────────────────────────────────────
    print("\n[3] 非绿档由谁贡献（共振规则的真实基础）")
    contrib = Counter()
    for r in recs:
        for m in r["non_green"]:
            contrib[m] += 1
    for m in SCORED:
        print(f"  {m:<16} {contrib[m]:3d}/{N} 天贡献非绿档  ({pct(contrib[m], N):5.1f}%)")
    solo = Counter(tuple(sorted(r["non_green"])) for r in recs)
    print("\n  非绿档组合分布：")
    for combo, n in solo.most_common():
        label = "（全绿）" if not combo else " + ".join(combo)
        print(f"    {label:<34} {n:3d} 天  {pct(n, N):5.1f}%")

    # ── 4. 加速度条款触发率 ─────────────────────────────────────────────
    print("\n[4] 加速度条款触发率（1.1o 的门槛校准检查）")
    at = Counter()
    for r in recs:
        for m, kind, ch in r["accel"]:
            at[(m, kind)] += 1
    any_accel = sum(1 for r in recs if r["accel"])
    print(f"  任一触发：{any_accel}/{N} 天  ({pct(any_accel, N):.1f}%)")
    for m in SCORED:
        for kind, thr in (("1d", ACCEL_1D), ("3d", ACCEL_3D)):
            n = at[(m, kind)]
            print(f"    {m:<16} {kind} >{thr:.0%}  {n:3d} 天  {pct(n, N):5.1f}%")
            if pct(n, N) > 25:
                findings.append(("噪音门槛", f"{m}/{kind}",
                                 f"触发率 {pct(n, N):.0f}% — 高于 25% 即为噪音而非警报（1.1o 判据）"))
    # 各指标自身日波动量级，用于判断门槛是否该共用
    print("\n  各指标平均单日绝对变动（门槛是否该共用的依据）：")
    for m in SCORED:
        ch = [abs(days[i][m] / days[i-1][m] - 1)
              for i in range(1, len(days)) if days[i].get(m) and days[i-1].get(m)]
        if ch:
            avg = sum(ch) / len(ch)
            print(f"    {m:<16} {avg:.2%}   (10% 门槛 = 其常态的 {0.10/avg:.1f} 倍)")

    # ── 5. 期限溢价开窗率 ───────────────────────────────────────────────
    print("\n[5] 期限溢价开窗率（VIX3M/VIX ≥ 1.20）")
    tp = [r["term_premium"] for r in recs if r["term_premium"]]
    opened = sum(1 for v in tp if v >= TERM_PREMIUM_OPEN)
    print(f"  开窗 {opened}/{len(tp)} 天  ({pct(opened, len(tp)):.1f}%)   "
          f"区间 {min(tp):.3f} – {max(tp):.3f}")
    if opened == 0:
        findings.append(("死条款", "term_premium",
                         f"{len(tp)} 个交易日从未达到 {TERM_PREMIUM_OPEN}（最高仅 {max(tp):.3f}）— "
                         f"该条款在观测区间内恒为「不开仓」，等价于一个无条件否决"))

    # ── 6. 与 SKILL.md 的阈值漂移检查 ───────────────────────────────────
    print("\n[6] 阈值漂移检查（本脚本 vs SKILL.md）")
    skill = os.path.join(REPO, ".claude/skills/tail-risk-monitor/SKILL.md")
    txt = open(skill, encoding="utf-8").read() if os.path.exists(skill) else ""
    for lit in ["0.95", "140", "150", "100", "120", "20", "25", "1.20"]:
        if lit not in txt:
            findings.append(("阈值漂移", lit, f"本脚本使用的阈值 {lit} 在 SKILL.md 中找不到"))
    print("  " + ("未发现漂移" if not any(f[0] == "阈值漂移" for f in findings)
                  else "发现漂移，见下"))

    # ── 结论 ────────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    if not findings:
        print("回放未发现结构性问题。")
    else:
        print(f"发现 {len(findings)} 项，按严重度排列：\n")
        for i, (kind, where, msg) in enumerate(findings, 1):
            print(f"  {i}. [{kind}] {where}")
            print(f"     {msg}\n")
    if "--json" in sys.argv:
        print(json.dumps({"n_days": N, "findings": findings}, ensure_ascii=False))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
