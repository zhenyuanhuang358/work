#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""牛市看跌价差的期望值门槛 —— 替代「R/R ≥ 0.25」（2026-10-19 用户批准）。

**为什么换**：「用价差 + 缓冲÷1σ ≥ 1.0 + 收益/风险 ≥ 0.25」三条同时满足几乎不可能——
R/R 0.25 对应净收入 = 宽度 20%，卖腿 Δ≈0.25、z≈0.6–0.7；z ≥ 1.0 的价差 R/R 一般只有 0.1–0.15。
10/16 SPY、NVDA 都卡死在这里。R/R 是个比例，不衡量「这笔钱收得够不够」。

**新门槛（期望值）**：
    净收入 ÷ 宽度  ≥  按 HV 算的卖腿到期价内概率 + 3 个百分点
直觉：每 $1 宽度，最坏亏掉（宽度 − 收入）。若到期价内概率是 p，
保守地把价内当成亏满，则期望 ≈ 收入 − p × 宽度。收入 ÷ 宽度 > p 才有正期望；+3pct 是安全垫。
用 **HV** 而不是 IV 算 p：IV 是市场给的价，HV 是标的实际在怎么动。
**IV 高于 HV 的部分，就是卖方的优势**——这条门槛正好把它量出来。

用法：
  python3 tools/spread_check.py --ticker SPY --spot 767.81 --short 755 --long 752 \\
      --short-bid 4.13 --long-ask 3.59 --dte 4 [--hv 0.11]
  （不给 --hv 时，从 stock_prices.json 的 git 历史算近 30 个收盘日的 HV）
"""
import argparse
import math
import os
import sys
from statistics import NormalDist

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
N = NormalDist().cdf
MARGIN = 0.03


def hv_from_history(ticker, n=30):
    from jev_bench import load_daily_closes
    px = [p["prices"][ticker]["price"] for d, b, p in load_daily_closes()
          if b == "close" and ticker in p["prices"]][-(n + 1):]
    if len(px) < 15:
        sys.exit(f"{ticker} 收盘历史不足 15 天，请用 --hv 手动给")
    r = [math.log(b / a) for a, b in zip(px, px[1:])]
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(252)


def p_itm(spot, strike, sigma, dte):
    """到期收在行权价下方的概率（对数正态、零漂移）。"""
    t = dte / 365
    d2 = (math.log(spot / strike) - 0.5 * sigma ** 2 * t) / (sigma * math.sqrt(t))
    return N(-d2)


def check(spot, short, long, short_bid, long_ask, dte, hv):
    width = short - long
    credit = short_bid - long_ask
    out = {"width": width, "credit": round(credit, 2), "max_loss": round((width - credit) * 100),
           "hv": hv, "p_itm_hv": p_itm(spot, short, hv, dte),
           "buffer": (spot - short) / spot}
    out["credit_ratio"] = credit / width if width > 0 else float("nan")
    out["need"] = out["p_itm_hv"] + MARGIN
    out["edge"] = out["credit_ratio"] - out["p_itm_hv"]
    out["pass"] = credit > 0 and out["credit_ratio"] >= out["need"]
    return out


def main():
    ap = argparse.ArgumentParser(description="牛市看跌价差期望值门槛")
    ap.add_argument("--ticker", default="")
    ap.add_argument("--spot", type=float, required=True)
    ap.add_argument("--short", type=float, required=True, help="卖出的 put 行权价（较高）")
    ap.add_argument("--long", type=float, required=True, help="买入的 put 行权价（较低）")
    ap.add_argument("--short-bid", type=float, required=True)
    ap.add_argument("--long-ask", type=float, required=True)
    ap.add_argument("--dte", type=float, required=True, help="剩余日历天数")
    ap.add_argument("--hv", type=float)
    ap.add_argument("--max-loss-cap", type=float, help="单笔最大亏损上限（美元），如净值 5%")
    a = ap.parse_args()
    hv = a.hv if a.hv is not None else hv_from_history(a.ticker.upper())
    o = check(a.spot, a.short, a.long, a.short_bid, a.long_ask, a.dte, hv)
    print(f"{a.ticker} {a.short:g}/{a.long:g}  净收 {o['credit']:.2f}（宽 {o['width']:g}）  最大亏损 ${o['max_loss']}"
          f"  缓冲 {o['buffer']:.1%}")
    print(f"  HV {hv:.0%} → 到期价内概率 {o['p_itm_hv']:.1%}；净收/宽度 {o['credit_ratio']:.1%}；"
          f"门槛 {o['need']:.1%}；优势 {o['edge']:+.1%}")
    cap_ok = a.max_loss_cap is None or o["max_loss"] <= a.max_loss_cap
    verdict = "✅ 过线" if o["pass"] and cap_ok else "⛔ 不过线"
    why = [] if o["pass"] else ["期望值不够"]
    if not cap_ok:
        why.append(f"最大亏损超上限 ${a.max_loss_cap:g}")
    print(f"  {verdict}" + (f"（{'；'.join(why)}）" if why else ""))


if __name__ == "__main__":
    main()
