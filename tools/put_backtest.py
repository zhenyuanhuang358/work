#!/usr/bin/env python3
"""卖 put 规则回测：比较止损方式、入场环境、到期周期对期望值的影响（profile 1.2r，2026-11-05）

两种样本：
  --source ledger     候选账本里已到期的真实候选（真实入场日 / 行权价 / 收入，IV 缺则用 HV 代）
  --source synthetic  价格历史里所有抓价标的，每 STEP 个交易日在 z 处卖一张 put（IV = HV30 × --iv-mult）
规则：
  --stop 2x     期权价 ≥ 2× 收入即止损（按当日 low 判断，按 2× 成交）
  --stop stock  正股收盘跌破「入场价与行权价的中点」即止损（按当日收盘的模型价成交）
  --stop none   不止损，持有到期
  --tp 0.5      期权价 ≤ (1 − 0.5) × 收入即止盈（按当日 high 判断）；不给则不止盈
  --regime green  只在入场日尾部闸门为绿（VIX < 20、期限结构 < 0.95、VVIX < 100）时开仓
  --regime tp120  另加期限溢价 VIX3M / VIX ≥ 1.20
输出：每 $1 收入的净结果、胜率、止损率、按簇数。
局限：模型价用不变 IV（下跌时 IV 上升被忽略 → 止损偏晚、亏损偏小）；合成样本的收入用 HV 估，
实际 IV 通常高于 HV（收入偏低）；只有抓价日的 high / low；样本期 2026-05 起，覆盖的行情阶段有限。
"""
import argparse
import datetime as dt
import math
import os
import sys
from statistics import NormalDist

sys.path.insert(0, os.path.dirname(__file__))
from candidate_ledger import read_ledger  # noqa: E402
from jev_bench import load_daily_closes  # noqa: E402

N = NormalDist()
MEASURED = {"平台反解", "链上反解"}


def put(S, K, s, T):
    if T <= 1e-6:
        return max(K - S, 0.0)
    d1 = (math.log(S / K) + 0.5 * s * s * T) / (s * math.sqrt(T))
    return K * N.cdf(-(d1 - s * math.sqrt(T))) - S * N.cdf(-d1)


def call(S, K, s, T):
    return put(S, K, s, T) + S - K  # 平价关系（r = 0）


def opt(right, S, K, s, T):
    return put(S, K, s, T) if right == "P" else call(S, K, s, T)


def load():
    days = {}  # date -> payload（每天取最后一个快照，收盘快照优先）
    for d, kind, p in load_daily_closes():
        if d not in days or kind == "close":
            days[d] = p
    dates = sorted(days)
    return dates, days


def hv(dates, days, t, upto, n=30):
    xs = [days[d]["prices"][t]["price"] for d in dates if d < upto and t in days[d]["prices"]][-(n + 1):]
    if len(xs) < 15:
        return None
    r = [math.log(b / a) for a, b in zip(xs, xs[1:]) if a > 0 and b > 0]
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1) * 252)


def regime_ok(p, mode):
    if not mode:
        return True
    tr, vix = p.get("tail_risk") or {}, p.get("vix")
    if not tr or vix is None:
        return False
    green = vix < 20 and tr.get("term_structure", 9) < 0.95 and tr.get("vvix", 999) < 100
    if mode == "green":
        return green
    return green and tr.get("vix3m") and tr["vix3m"] / vix >= 1.20


def simulate(t, K, S0, credit, iv, entry, expiry, dates, days, stop, tp, right="P"):
    """返回 (结果 / 收入, 结局)。right = P 卖 put / C 卖 call（不利方向分别看 low / high）。"""
    e = dt.date.fromisoformat(expiry)
    mid = (S0 + K) / 2
    path = [d for d in dates if entry < d <= expiry and t in days[d]["prices"]]
    if not path or path[-1] != expiry and expiry <= dates[-1]:
        pass
    for d in path:
        q = days[d]["prices"][t]
        T = max((e - dt.date.fromisoformat(d)).days, 0) / 365
        low, high, close = q.get("low") or q["price"], q.get("high") or q["price"], q["price"]
        bad, good = (low, high) if right == "P" else (high, low)
        if stop == "2x" and opt(right, bad, K, iv, T) >= 2 * credit:
            return -1.0, "止损"
        if stop == "stock" and (close <= mid if right == "P" else close >= mid):
            return (credit - opt(right, close, K, iv, T)) / credit, "止损"
        if tp and opt(right, good, K, iv, T) <= (1 - tp) * credit:
            return tp, "止盈"
    if expiry > dates[-1]:
        return None, "未到期"
    last = days[path[-1]]["prices"][t]["price"] if path else S0
    intrinsic = max(K - last, 0) if right == "P" else max(last - K, 0)
    return (credit - intrinsic) / credit, ("到期价内" if intrinsic > 0 else "到期价外")


def run(a):
    dates, days = load()
    trades = []
    if a.source == "ledger":
        for r in read_ledger():
            if r.get("right", "P") != "P" or r["expiry"] > dates[-1]:
                continue
            entry = r["logged"][:10]
            p0 = days.get(entry) or days.get(max([d for d in dates if d <= entry], default=dates[0]))
            if not regime_ok(p0, a.regime):
                continue
            iv = r["iv"] if (r.get("iv") and r.get("iv_src") in MEASURED) else hv(dates, days, r["ticker"], entry)
            if not iv:
                continue
            T0 = max((dt.date.fromisoformat(r["expiry"]) - dt.date.fromisoformat(entry)).days, 1) / 365
            credit = r["bid"] or put(r["spot"], r["strike"], iv, T0)
            if credit < 0.005:
                continue
            res, how = simulate(r["ticker"], r["strike"], r["spot"], credit, iv, entry, r["expiry"],
                                dates, days, a.stop, a.tp)
            if res is not None:
                trades.append((r["ticker"], r["expiry"], res, how, credit))
    else:
        tickers = sorted({t for d in dates for t in days[d]["prices"]})
        for t in tickers:
            tdays = [d for d in dates if t in days[d]["prices"]]
            for i in range(30, len(tdays), a.step):
                entry = tdays[i]
                if not regime_ok(days[entry], a.regime):
                    continue
                vol = hv(dates, days, t, entry)
                if not vol:
                    continue
                iv = vol * a.iv_mult
                S0 = days[entry]["prices"][t]["price"]
                expiry = (dt.date.fromisoformat(entry) + dt.timedelta(days=a.dte)).isoformat()
                # 到期日落在周末时取之前最近的交易日
                ex = max([d for d in dates if d <= expiry], default=None) if expiry <= dates[-1] else expiry
                T0 = a.dte / 365
                legs = {"P": ["P"], "C": ["C"], "strangle": ["P", "C"]}[a.right]
                got = []
                for rt in legs:
                    K = S0 * math.exp((-1 if rt == "P" else 1) * a.z * iv * math.sqrt(T0))
                    credit = opt(rt, S0, K, iv, T0)
                    if credit < 0.005:
                        break
                    res, how = simulate(t, K, S0, credit, iv, entry, ex, dates, days, a.stop, a.tp, rt)
                    if res is None:
                        break
                    got.append((res * credit, how, credit))
                if len(got) == len(legs):
                    # 宽跨按一笔合并：两腿盈亏相加 ÷ 两腿收入相加
                    c = sum(g[2] for g in got)
                    how = "止损" if any(g[1] == "止损" for g in got) else got[0][1]
                    trades.append((t, ex, sum(g[0] for g in got) / c, how, c))
    return trades


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["ledger", "synthetic"], default="ledger")
    ap.add_argument("--stop", choices=["2x", "stock", "none"], default="2x")
    ap.add_argument("--tp", type=float)
    ap.add_argument("--regime", choices=["green", "tp120"])
    ap.add_argument("--dte", type=int, default=10)
    ap.add_argument("--z", type=float, default=1.2)
    ap.add_argument("--iv-mult", type=float, default=1.1)
    ap.add_argument("--step", type=int, default=5)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--right", choices=["P", "C", "strangle"], default="P", help="合成样本：卖 put / 卖 call / 同时卖两腿（宽跨）")
    a = ap.parse_args()
    tr = run(a)
    label = f"{a.source}｜止损 {a.stop}｜止盈 {a.tp or '无'}｜环境 {a.regime or '不限'}" + \
            (f"｜{a.dte} 天 z {a.z}｜{ {'P':'卖 put','C':'卖 call','strangle':'宽跨'}[a.right]}" if a.source == "synthetic" else "")
    if not tr:
        print(f"{label}：无样本")
        return
    n = len(tr)
    cl = len({(t, e) for t, e, *_ in tr})
    # 主口径：按金额加权（总盈亏 ÷ 总收入）＝ 每张做一样多时的真实盈亏；等权平均仅作参考。
    # 2026-11-05：首版用等权平均，与 stop_replay（金额加权）对不上（−0.33 vs −0.52），已统一。
    ev = sum(r * c for _, _, r, _, c in tr) / sum(c for *_, c in tr)
    ev_eq = sum(r for _, _, r, _, _ in tr) / n
    win = sum(1 for _, _, r, _, _ in tr if r > 0) / n
    stops = sum(1 for _, _, _, h, _ in tr if h == "止损") / n
    worst = min(r for _, _, r, _, _ in tr)
    print(f"{label}\n  样本 {n} 笔 / {cl} 簇｜每 $1 收入净 {ev:+.2f}（等权 {ev_eq:+.2f}）｜赚钱比例 {win:.0%}｜止损 {stops:.0%}｜最差一笔 {worst:+.1f}× 收入")


if __name__ == "__main__":
    main()
