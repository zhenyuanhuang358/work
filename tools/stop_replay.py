#!/usr/bin/env python3
"""止损路径回放：「期权价 ≥ 2× 收入」这条止损，实际在到期前被触发了多少次？

为什么（profile 1.2r，2026-11-05）：选单看「到期价内概率」（约 7–13%），止损却是路径条件。
模型估算止损触发概率约 50–60%——本工具用候选账本的真实股价路径回放，检验这个估算。

做法（逐条已到期候选）：
  1. 入场 IV：账本有实测 IV（平台 / 链上反解）就用；没有就用登记日前 30 个收盘日的 HV，标「HV 代」。
  2. 入场收入：账本有 bid 就用；没有就用模型价（同一 IV），标「模型收入」。
  3. 每个交易日：按剩余期限算出「期权价 = 2× 收入」对应的股价止损线；当日 low ≤ 止损线即判触发。
  4. 规则下的结局：先触发止损 → −1× 收入（未计滑点）；否则看到期：价外 +1× 收入，价内（未先触发，罕见）按内在价值。
局限（全部让结果偏乐观，即触发率是下限）：
  - IV 按不变处理。股价下跌时 IV 通常上升，期权价会更早到 2×。
  - 只有抓价日的 low，缺抓价的交易日看不到。
  - 止损按 2× 收入成交，不计滑点和跳空（INTC 实际在 13.8× 收入成交）。
  - 同一 (标的, 到期日) 的多行高度相关，结论按「簇」数判断，满 20 簇才下结论。
用法：python3 tools/stop_replay.py [--verdict 推荐|否决] [--detail]
"""
import argparse
import datetime as dt
import json
import math
import os
import sys
from statistics import NormalDist

sys.path.insert(0, os.path.dirname(__file__))
from candidate_ledger import read_ledger, MIN_CLUSTERS  # noqa: E402
from jev_bench import load_daily_closes  # noqa: E402

N = NormalDist()
MEASURED = {"平台反解", "链上反解"}


def put(S, K, s, T):
    if T <= 1e-6:
        return max(K - S, 0.0)
    d1 = (math.log(S / K) + 0.5 * s * s * T) / (s * math.sqrt(T))
    return K * N.cdf(-(d1 - s * math.sqrt(T))) - S * N.cdf(-d1)


def stop_level(K, s, T, target, hi):
    """期权价 = target 时的股价（put 随股价单调递减，二分）。"""
    lo = K * 0.3
    if put(hi, K, s, T) >= target:
        return hi
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if put(m, K, s, T) > target else (lo, m)
    return (lo + hi) / 2


def hv_before(series, day, n=30):
    xs = [p for d, p in series if d < day][-(n + 1):]
    if len(xs) < 10:
        return None
    r = [math.log(b / a) for a, b in zip(xs, xs[1:]) if a > 0 and b > 0]
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1) * 252)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdict")
    ap.add_argument("--detail", action="store_true")
    a = ap.parse_args()

    closes = load_daily_closes()
    today = dt.date.today().isoformat()
    series = {}
    for d, kind, p in closes:
        for t, q in p["prices"].items():
            if kind == "close" and q.get("price"):
                series.setdefault(t, []).append((d, q["price"]))

    out = []
    for r in read_ledger():
        if r.get("right", "P") != "P" or r["expiry"] >= today or (a.verdict and r["verdict"] != a.verdict):
            continue
        t, K, start = r["ticker"], r["strike"], r["logged"][:10]
        window = [(d, kind, p["prices"][t]) for d, kind, p in closes
                  if start < d <= r["expiry"] and t in p["prices"]]
        last = [w for w in window if w[0] == r["expiry"] and w[1] == "close"]
        if not window or not last:
            continue
        iv_src = "实测"
        iv = r["iv"] if (r.get("iv") and r.get("iv_src") in MEASURED) else None
        if iv is None:
            iv, iv_src = hv_before(series.get(t, []), start), "HV 代"
        if not iv:
            continue
        e = dt.date.fromisoformat(r["expiry"])
        T0 = max((e - dt.date.fromisoformat(start)).days, 1) / 365
        credit, cr_src = (r["bid"], "实价") if r.get("bid") else (put(r["spot"], K, iv, T0), "模型")
        if credit < 0.005:
            continue
        stop_day = None
        for d, _, q in window:
            T = max((e - dt.date.fromisoformat(d)).days, 0) / 365
            lvl = stop_level(K, iv, T, 2 * credit, r["spot"])
            low = q.get("low") or q.get("price")
            if low is not None and low <= lvl:
                stop_day = d
                break
        px = last[0][2]["price"]
        itm = px < K
        pnl = -credit if stop_day else (credit - max(K - px, 0))
        hold = credit - max(K - px, 0)  # 对照：不止损、持有到期
        # 开仓时模型给的「止损触发概率」（反射原理），与实际对照
        sig0 = iv * math.sqrt(T0)
        lvl0 = stop_level(K, iv, T0 * 0.8, 2 * credit, r["spot"])
        p_touch = min(1.0, 2 * N.cdf(-math.log(r["spot"] / lvl0) / sig0)) if lvl0 < r["spot"] else 1.0
        p_itm = N.cdf(-(math.log(r["spot"] / K) + 0.5 * sig0 * sig0) / sig0)
        out.append(dict(t=t, K=K, e=r["expiry"], v=r["verdict"], iv=iv, iv_src=iv_src, cr=credit, cr_src=cr_src,
                        stop=stop_day, itm=itm, pnl=pnl, hold=hold, p_touch=p_touch, p_itm=p_itm))

    if not out:
        print("没有可回放的已到期候选。")
        return
    clusters = {(o["t"], o["e"]) for o in out}
    n = len(out)
    stops = sum(1 for o in out if o["stop"])
    itms = sum(1 for o in out if o["itm"])
    gain = sum(o["pnl"] for o in out)
    tot_cr = sum(o["cr"] for o in out)
    print(f"可回放 {n} 条｜独立簇 {len(clusters)} 个｜实测 IV {sum(o['iv_src']=='实测' for o in out)} 条，HV 代 {sum(o['iv_src']=='HV 代' for o in out)} 条"
          f"｜实价收入 {sum(o['cr_src']=='实价' for o in out)} 条")
    print(f"到期价内：实际 {itms/n:.0%}｜开仓时模型预期 {sum(o['p_itm'] for o in out)/n:.0%}")
    print(f"止损触发：实际 ≥{stops/n:.0%}（下限）｜开仓时模型预期 {sum(o['p_touch'] for o in out)/n:.0%}")
    print(f"按「2× 收入止损」执行的总结果：{gain/tot_cr:+.0%} × 收入（未计滑点、手续费、跳空）"
          f"｜每 $1 收入净得 ${gain/tot_cr:+.2f}")
    hold_g = sum(o["hold"] for o in out)
    print(f"对照·不止损持有到期：{hold_g/tot_cr:+.0%} × 收入（价内按到期内在价值结算）")
    for src in ("实测", "HV 代"):
        g = [o for o in out if o["iv_src"] == src]
        if g:
            print(f"  IV {src}：{len(g)} 条｜止损触发 ≥{sum(1 for o in g if o['stop'])/len(g):.0%}"
                  f"｜到期价内 实际 {sum(o['itm'] for o in g)/len(g):.0%} vs 模型 {sum(o['p_itm'] for o in g)/len(g):.0%}"
                  f"｜止损规则 {sum(o['pnl'] for o in g)/sum(o['cr'] for o in g):+.0%}｜持有到期 {sum(o['hold'] for o in g)/sum(o['cr'] for o in g):+.0%}")
    # 按簇聚合，防止同一簇多行重复计数
    byc = {}
    for o in out:
        c = byc.setdefault((o["t"], o["e"]), [])
        c.append(o)
    cl_stop = sum(1 for c in byc.values() if any(o["stop"] for o in c))
    print(f"按簇：{cl_stop}/{len(byc)} 个簇至少一行触发止损（{cl_stop/len(byc):.0%}）")
    for v in sorted({o["v"] for o in out}):
        g = [o for o in out if o["v"] == v]
        print(f"  {v}：{len(g)} 条｜止损触发 ≥{sum(1 for o in g if o['stop'])/len(g):.0%}"
              f"｜到期价内 {sum(o['itm'] for o in g)/len(g):.0%}｜净 {sum(o['pnl'] for o in g)/sum(o['cr'] for o in g):+.0%} × 收入")
    if len(clusters) < MIN_CLUSTERS:
        print(f"\n⛔ 独立簇 {len(clusters)} < {MIN_CLUSTERS}，只作方向参考，不下定论。")
    if a.detail:
        print()
        for o in sorted(out, key=lambda o: (o["e"], o["t"])):
            print(f"  {o['t']:5} {o['K']:>7} {o['e']} {o['v']}｜IV {o['iv']:.0%}({o['iv_src']})｜收入 {o['cr']:.2f}({o['cr_src']})"
                  f"｜模型触发 {o['p_touch']:.0%}｜{'止损 ' + o['stop'] if o['stop'] else '未触发'}｜到期{'价内' if o['itm'] else '价外'}"
                  f"｜{o['pnl']:+.2f}")
    print("\n局限：IV 按不变（下跌时 IV 上升会更早止损）、只看抓价日 low、止损按 2× 成交不计滑点——触发率是下限，净结果偏乐观。")


if __name__ == "__main__":
    main()
