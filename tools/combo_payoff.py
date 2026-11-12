#!/usr/bin/env python3
"""三种看涨组合的到期盈亏对照（只做分析与列出，不进候选、不登记 candidate_ledger、不改 position-discipline）

用户 2026-11-12 定：财报等事件前，把同一对行权价 K1 < K2 的三种结构按真实买卖价摆出来——
  牛市看涨价差 bull ：买 1 K1、卖 1 K2（付权利金，赌涨）
  熊市看涨价差 bear ：卖 1 K1、买 1 K2（收权利金，赌不涨；用户最初描述的结构）
  看涨比例反向 back ：卖 1 K1、买 N K2（赌大涨；最怕温和上涨停在 K2）
成交口径：买按 ask、卖按 bid（不按中间价，和 candidate_ledger 一致）。到期盈亏只看内在价值。

为什么要现价核对（11/12 NVDA 实测）：CBOE 的 current_price 是盘后价 158.78，而期权报价停在 16:00 收盘（平价反推 173.9）。
用错现价，ATM、市场定价的跳空幅度、情景表全错。所以先用平价反推现价，差 >2% 就报警并以反推值为准。

用法：
  python3 tools/combo_payoff.py NVDA --expiry 2026-11-20 [--pre 2026-11-13] [--k1 175 --k2 190] [--ratio 2] [--json]
  不给 --k1/--k2：K1 = 现价上方第一档，K2 = 现价 × (1 + 市场定价跳空幅度) 最近的一档。
  --pre：事件前到期日，用于扣掉平常波动、单算事件本身的跳空幅度。
"""
import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import gap_stress as gs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOVES = (-0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20)
PARITY_WARN = 0.02


def load_chain(ticker, path=None):
    if path:
        return json.load(open(path))
    p = os.path.join(ROOT, "chains", f"{ticker}.json")
    if os.path.exists(p):
        return json.load(open(p))
    return json.load(open(os.path.join(ROOT, "options_chain.json")))["tickers"][ticker]


def index(chain, expiry):
    return {(x["right"], x["strike"]): x for x in chain["rows"] if x["expiry"] == expiry
            and x.get("bid") is not None and x.get("ask") is not None}


def mid(x):
    return (x["bid"] + x["ask"]) / 2


def parity_spot(ix, spot):
    """离 spot 最近的 3 档同时有 call 与 put 的行权价：S ≈ K + C − P（短期，忽略利率与股息）"""
    ks = sorted({k for r, k in ix if ("C", k) in ix and ("P", k) in ix}, key=lambda k: abs(k - spot))[:3]
    if not ks:
        return None
    return sum(k + mid(ix[("C", k)]) - mid(ix[("P", k)]) for k in ks) / len(ks)


def years(expiry, asof):
    return max((datetime.fromisoformat(expiry + "T21:00:00+00:00") - asof).total_seconds() / 86400 / 365, 1 / 365 / 24)


def atm_iv(ix, s, t):
    ks = sorted({k for r, k in ix if r == "C"}, key=lambda k: abs(k - s))[:2]
    ivs = [gs.implied("C", mid(ix[("C", k)]), s, k, t) for k in ks]
    ivs = [v for v in ivs if v]
    return sum(ivs) / len(ivs) if ivs else None


def straddle(ix, s):
    ks = [k for r, k in ix if r == "C" and ("P", k) in ix]
    k = min(ks, key=lambda k: abs(k - s))
    return k, mid(ix[("C", k)]) + mid(ix[("P", k)])


def legs(kind, k1, k2, ratio):
    # (数量, 行权价)：正 = 买，负 = 卖
    return {"bull": [(1, k1), (-1, k2)], "bear": [(-1, k1), (1, k2)], "back": [(-1, k1), (ratio, k2)]}[kind]


def open_cash(ix, lg):
    """开仓现金流（每股）：卖收 bid、买付 ask；正 = 净收入"""
    return sum(-q * ix[("C", k)]["ask"] if q > 0 else -q * ix[("C", k)]["bid"] for q, k in lg)


def payoff(lg, cash, s_end):
    return (cash + sum(q * max(s_end - k, 0.0) for q, k in lg)) * 100


def breakevens(lg, cash, lo, hi):
    pts, step = [], (hi - lo) / 4000
    prev = payoff(lg, cash, lo)
    x = lo
    while x < hi:
        x2 = x + step
        cur = payoff(lg, cash, x2)
        if (prev < 0) != (cur < 0):
            pts.append(round(x - prev * step / (cur - prev), 2))
        prev, x = cur, x2
    return pts


def analyze(chain, expiry, pre=None, k1=None, k2=None, ratio=2, asof=None):
    asof = asof or datetime.now(timezone.utc)
    ix = index(chain, expiry)
    if not ix:
        raise SystemExit(f"链里没有 {expiry} 的报价")
    reported = chain["spot"]
    ps = parity_spot(ix, reported)
    warn = None
    s = reported
    if ps and abs(ps / reported - 1) > PARITY_WARN:
        warn = (f"⚠ 链上现价 {reported:.2f} 与期权平价反推 {ps:.2f} 差 {ps / reported - 1:+.1%}：期权报价与现价不同时"
                f"（常见于盘后大涨大跌）。本表按反推 {ps:.2f} 计算；开盘后报价会重定价，要重抓再看")
        s = ps
    t = years(expiry, asof)
    kst, st = straddle(ix, s)
    out = {"expiry": expiry, "spot_reported": reported, "spot_used": round(s, 2), "warn": warn,
           "straddle_strike": kst, "straddle": round(st, 2), "straddle_pct": st / s,
           "iv": atm_iv(ix, s, t), "quote_time_utc": chain.get("quote_time_utc")}
    move = st / s
    if pre:
        px = index(chain, pre)
        if px:
            tp = years(pre, asof)
            iv_pre, iv_post = atm_iv(px, s, tp), out["iv"]
            if iv_pre and iv_post and iv_post ** 2 * t > iv_pre ** 2 * t:
                ev = math.sqrt(iv_post ** 2 * t - iv_pre ** 2 * t)
                out.update(event_1sd=ev, event_abs=ev * math.sqrt(2 / math.pi), iv_pre=iv_pre)
                move = ev
    out["move"] = move
    calls = sorted(k for r, k in ix if r == "C")
    if k1 is None:
        k1 = min((k for k in calls if k >= s), default=calls[-1])
    if k2 is None:
        k2 = min((k for k in calls if k > k1), key=lambda k: abs(k - s * (1 + move)), default=None)
    if k2 is None or k2 <= k1 or ("C", k1) not in ix or ("C", k2) not in ix:
        raise SystemExit(f"行权价不可用：K1={k1} K2={k2}")
    out.update(k1=k1, k2=k2, ratio=ratio, quotes={k: {"bid": ix[("C", k)]["bid"], "ask": ix[("C", k)]["ask"]} for k in (k1, k2)})
    scen = list(MOVES) + [round(move, 4), round(-move, 4)]
    scen = sorted(set(scen))
    lo, hi = s * 0.5, s * 1.6
    out["structures"] = {}
    for kind in ("bull", "bear", "back"):
        lg = legs(kind, k1, k2, ratio)
        cash = open_cash(ix, lg)
        # 盈亏是分段线性的，极值只会出现在折点（行权价）或区间端点 → 精确取这些点，不靠网格
        pts = [lo, hi, k1, k2]
        grid = [payoff(lg, cash, x) for x in pts]
        out["structures"][kind] = {
            "legs": lg, "open_cash": round(cash * 100, 2),
            "max_profit": None if kind == "back" else round(max(grid), 2),
            "max_loss": round(min(grid), 2),
            "breakevens": breakevens(lg, cash, lo, hi),
            "scenarios": [(m, round(s * (1 + m), 2), round(payoff(lg, cash, s * (1 + m)), 2)) for m in scen],
        }
    return out


NAMES = {"bull": "牛市看涨价差（买 K1 卖 K2，赌涨）", "bear": "熊市看涨价差（卖 K1 买 K2，赌不涨）", "back": "看涨比例反向价差（卖 1 K1 买 N K2，赌大涨）"}


def fmt(o, ticker):
    L = [f"# {ticker} {o['expiry']} 三种看涨组合到期盈亏（只做分析，不进候选、不改规则）", ""]
    if o["warn"]:
        L += [o["warn"], ""]
    L.append(f"- 现价 {o['spot_used']:.2f}（报价时间 {o['quote_time_utc']} UTC）｜平值 {o['straddle_strike']:g} 跨式 {o['straddle']:.2f} = {o['straddle_pct']:.1%}"
             + (f"｜IV {o['iv']:.0%}" if o["iv"] else ""))
    if "event_1sd" in o:
        L.append(f"- 事件本身（扣掉 {o['iv_pre']:.0%} 的平常波动）：1σ ±{o['event_1sd']:.1%}，平均预期涨跌 {o['event_abs']:.1%}")
    q = o["quotes"]
    L.append(f"- K1 = {o['k1']:g}（{q[o['k1']]['bid']} / {q[o['k1']]['ask']}），K2 = {o['k2']:g}（{q[o['k2']]['bid']} / {q[o['k2']]['ask']}），反向价差比例 1:{o['ratio']}"
             f"｜成交口径：买按卖价、卖按买价；每组 1 套，单位美元")
    L.append("")
    kinds = ("bull", "bear", "back")
    L.append("| 到期涨跌 | 股价 | " + " | ".join(NAMES[k].split("（")[0] for k in kinds) + " |")
    L.append("|---|---|" + "---|" * len(kinds))
    st = o["structures"]
    for i, (m, px, _) in enumerate(st["bull"]["scenarios"]):
        tag = "（市场定价）" if abs(abs(m) - round(o["move"], 4)) < 1e-9 else ""
        L.append(f"| {m:+.1%}{tag} | {px:.2f} | " + " | ".join(f"{st[k]['scenarios'][i][2]:+,.0f}" for k in kinds) + " |")
    L.append("")
    for k in kinds:
        s = st[k]
        cash = s["open_cash"]
        L.append(f"- **{NAMES[k]}**：开仓{'净收' if cash >= 0 else '净付'} ${abs(cash):,.0f}｜最大盈利 "
                 + ("不封顶" if s["max_profit"] is None else f"${s['max_profit']:,.0f}")
                 + f"｜最大亏损 ${-s['max_loss']:,.0f}｜盈亏平衡 {', '.join(f'{b:.2f}' for b in s['breakevens']) or '无'}")
    L += ["", "边界：盈立无组合单，两条腿分开下，卖出腿可能按裸卖收保证金（11/11 实测卖 call 为 Reg-T 估算的 2.13 倍）；"
          "到期盈亏只算内在价值，持有期间受 IV 变化影响（财报后 IV 骤降）。本表不构成候选，不登记 candidate_ledger。"]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--expiry", required=True)
    ap.add_argument("--pre")
    ap.add_argument("--k1", type=float)
    ap.add_argument("--k2", type=float)
    ap.add_argument("--ratio", type=int, default=2)
    ap.add_argument("--chain")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    ch = load_chain(a.ticker, a.chain)
    asof = None
    if ch.get("quote_time_utc"):
        asof = datetime.fromisoformat(ch["quote_time_utc"].replace(" ", "T") + "+00:00")
    o = analyze(ch, a.expiry, a.pre, a.k1, a.k2, a.ratio, asof)
    print(json.dumps(o, ensure_ascii=False, indent=1, default=str) if a.json else fmt(o, a.ticker))


if __name__ == "__main__":
    main()
