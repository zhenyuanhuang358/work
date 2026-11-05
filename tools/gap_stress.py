#!/usr/bin/env python3
"""跳空压力：卖出的单腿期权，标的一夜跳空后要花多少钱买回、亏多少、止损单还管不管用

为什么（2026-11-05 用户要求做成工具）：pipeline 步骤 9 要求每个推荐都列「标的 −3% / −5% 跳空」的代价，一直是会话临时用 BS 手算，
口径每次不同（IV 放大 1.3 倍还是不放大、按几σ解读）。INTC 104P 就是 CPI 次日跳空，止损条件单直接被跳过。
场景（全部「瞬间跳空、剩余天数不变」，比真实更悲观一点）：
  - 固定档：不利方向 3% / 5%（pipeline 规定的口径）
  - 实证档：该标的近一年单日最差（卖 put 看最大跌幅，卖 call 看最大涨幅；fetch_options 用 yfinance 一年日线算）
  - 每档两种 IV：不变 / ×1.3（跳空时 IV 通常上冲；取更差的当结论）
输出：买回价、每张亏损（相对开仓收入）、是收入的几倍、跳空幅度相当于几个日σ、2× 止损单会不会被一步跳过。
用法：
  python3 tools/gap_stress.py --ticker TLT --strike 78 --expiry 2026-12-04 [--right P] [--credit 0.11]
  （不给 --credit 就用链上 bid）
也被 option_quote.py 汇总模式调用，给每个过关行附一行压力。
"""
import argparse
import json
import math
from datetime import datetime, timezone
from statistics import NormalDist

N = NormalDist()
IV_SHOCK = 1.3


def bs(right, s, k, sig, t):
    d1 = (math.log(s / k) + 0.5 * sig * sig * t) / (sig * math.sqrt(t))
    d2 = d1 - sig * math.sqrt(t)
    return k * N.cdf(-d2) - s * N.cdf(-d1) if right == "P" else s * N.cdf(d1) - k * N.cdf(d2)


def implied(right, px, s, k, t):
    lo, hi = 0.01, 5.0
    if px <= max(0.0, (k - s) if right == "P" else (s - k)):
        return None
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if bs(right, s, k, m, t) < px else (lo, m)
    return (lo + hi) / 2


def scenarios(r):
    """不利方向的跳空档：固定 3% / 5% + 一年实证最差（若有）。"""
    out = [("−3%" if r == "P" else "+3%", 0.03), ("−5%" if r == "P" else "+5%", 0.05)]
    return out


def stress(right, s, k, t, iv, credit, hv=None, move=None):
    """返回每个场景的结果列表。credit 为每股开仓收入（卖出价）。"""
    rows = []
    gaps = scenarios(right)
    if move:
        g = -move["worst_down"] if right == "P" else move["worst_up"]
        if g > 0:
            gaps.append((f"一年最差 {'−' if right == 'P' else '+'}{g:.1%}", g))
    for lbl, g in gaps:
        s2 = s * (1 - g) if right == "P" else s * (1 + g)
        flat, shocked = bs(right, s2, k, iv, t), bs(right, s2, k, iv * IV_SHOCK, t)
        worst = max(flat, shocked)
        loss = (worst - credit) * 100
        sigma_day = (hv or iv) / math.sqrt(252)
        rows.append({"scenario": lbl, "gap": g, "sigmas": g / sigma_day, "buyback": worst, "flat": flat, "loss": loss,
                     "x_credit": worst / credit if credit else None, "skips_stop": worst > 2 * credit})
    return rows


def fmt(rows):
    return "｜".join(f"{x['scenario']}（{x['sigmas']:.1f}σ）买回 {x['flat']:.2f}~{x['buyback']:.2f}、最多亏 ${x['loss']:,.0f}"
                    f"（{x['x_credit']:.1f}×收入{'，跳过 2× 止损' if x['skips_stop'] else ''}）" for x in rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--strike", type=float, required=True)
    ap.add_argument("--expiry", required=True)
    ap.add_argument("--right", choices=["P", "C"], default="P")
    ap.add_argument("--credit", type=float, help="每股开仓收入；不给用链上 bid")
    ap.add_argument("--file", default="options_chain.json")
    a = ap.parse_args()
    j = json.load(open(a.file))
    r = j["tickers"][a.ticker.upper()]
    row = next((x for x in r["rows"] if x["expiry"] == a.expiry and x["strike"] == a.strike
                and x.get("right", "P") == a.right), None)
    if not row:
        raise SystemExit(f"链上没有 {a.ticker} {a.expiry} {a.strike}{a.right}")
    s = r["spot"]
    exp = datetime.fromisoformat(a.expiry).replace(hour=21, tzinfo=timezone.utc)
    t = max((exp - datetime.now(timezone.utc)).total_seconds(), 3600) / (365 * 86400)
    mid = (row["bid"] + row["ask"]) / 2
    iv = implied(a.right, mid, s, a.strike, t)
    credit = a.credit if a.credit is not None else row["bid"]
    print(f"{a.ticker.upper()} {a.expiry} {a.strike}{a.right}｜现价 {s:.2f}｜IV {iv:.1%}｜HV30 {r.get('hv30') or '—'}｜收入 {credit:.2f}/股（${credit*100:.0f}/张）")
    for x in stress(a.right, s, a.strike, t, iv, credit, r.get("hv30"), r.get("move_1y")):
        print(f"  {x['scenario']:14} 相当于 {x['sigmas']:4.1f} 个日σ → 买回 {x['flat']:.2f}（IV 不变）~ {x['buyback']:.2f}（IV×{IV_SHOCK}），每张最多亏 ${x['loss']:,.0f}"
              f"（{x['x_credit']:.1f}× 收入）{'  ⚠ 一步跳过 2× 止损，止损单按市价成交在更差位置' if x['skips_stop'] else ''}")
    print(f"假设：瞬间跳空、剩余天数不变、IV 取不变与 ×{IV_SHOCK} 中更差者。张数 n 的亏损 = 每张 × n。")


if __name__ == "__main__":
    main()
