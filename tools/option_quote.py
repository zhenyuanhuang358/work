#!/usr/bin/env python3
"""读 options_chain.json，按中间价反解 IV，算缓冲 / z / 到期价外概率 —— 卖方候选的定价入口

为什么：profile 1.1x 规定「反解是唯一合法的定价入口」。此前链上价只能靠用户截图；
2026-10-29 起 fetch-options 工作流抓 CBOE 延迟报价（约 15 分钟），本工具把它变成可裁定的数字。

两道保护（缺一不可，否则就是把旧报价当实测）：
  1. 报价时间超过 --max-age 分钟（默认 20）→ 整个标的标「报价过期」，不出 IV / z
  2. 买价为 0 或买卖价倒挂 → 该行不出数字（无法反解）
下单价永远以平台为准：本工具用于筛选与裁定，不替代下单前看平台。

用法：
  python3 tools/option_quote.py --ticker F --expiry 2026-11-06 [--strikes 11 11.5] [--z-min 1.2]
  价差另跑 tools/spread_check.py（卖腿 bid、买腿 ask 从本工具输出里取）
"""
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from statistics import NormalDist
from zoneinfo import ZoneInfo

N = NormalDist()
ET = ZoneInfo("America/New_York")


def put_price(s, k, sig, t):
    d1 = (math.log(s / k) + 0.5 * sig * sig * t) / (sig * math.sqrt(t))
    return k * N.cdf(-(d1 - sig * math.sqrt(t))) - s * N.cdf(-d1)


def implied_vol(px, s, k, t):
    intrinsic = max(k - s, 0.0)
    if px <= intrinsic:
        return None
    lo, hi = 0.01, 5.0
    for _ in range(100):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if put_price(s, k, m, t) < px else (lo, m)
    return (lo + hi) / 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--expiry", required=True)
    ap.add_argument("--strikes", type=float, nargs="*")
    ap.add_argument("--z-min", type=float, default=1.0, help="持有期含 CPI/PPI/FOMC/非农时用 1.2")
    ap.add_argument("--max-age", type=float, default=20, help="报价最长可接受分钟数")
    ap.add_argument("--file", default="options_chain.json")
    a = ap.parse_args()

    j = json.load(open(a.file))
    r = j["tickers"].get(a.ticker.upper())
    if not r or not r.get("rows"):
        sys.exit(f"{a.ticker}: options_chain.json 里没有数据（{r and r.get('errors')}）——把它加进 options_watch.json 并推送")

    now = datetime.now(timezone.utc)
    qt = r.get("quote_time_utc")
    if qt:
        qdt = datetime.fromisoformat(qt).replace(tzinfo=timezone.utc)
    else:  # yfinance 兜底没有报价时间，退而用抓取时间（偏乐观，故标注）
        qdt = datetime.fromisoformat(j["updated_at"])
    age = (now - qdt).total_seconds() / 60
    stale = age > a.max_age
    exp = datetime.fromisoformat(a.expiry).replace(hour=16, tzinfo=ET)
    t = (exp - qdt).total_seconds() / (365 * 86400)
    s = r["spot"]

    print(f"{a.ticker.upper()} {a.expiry}P  源 {r['source']}  报价 {qt or '无时间戳(用抓取时刻)'} UTC  "
          f"距今 {age:.0f} 分钟{'  ⛔ 报价过期，不出定价' if stale else ''}  现价 {s:.2f}  剩 {t*365:.2f} 天")
    if stale:
        sys.exit(1)
    print(f"{'行权':>8} {'bid':>6} {'ask':>6} {'中间价':>6} {'IV':>6} {'缓冲':>6} {'z':>5} {'价外概率':>7} {'每张收入':>7}")
    for row in sorted(r["rows"], key=lambda x: -x["strike"]):
        if row["expiry"] != a.expiry or (a.strikes and row["strike"] not in a.strikes):
            continue
        if row["strike"] >= s:  # 卖 put 只看价外；价内行的「IV」受价差和内在价值主导，没有参考价值
            continue
        k, b, ak = row["strike"], row["bid"] or 0, row["ask"] or 0
        if b <= 0 or ak < b:
            print(f"{k:8.2f} {b:6.2f} {ak:6.2f}   — 买价为 0 或倒挂，无法反解")
            continue
        mid = (b + ak) / 2
        iv = implied_vol(mid, s, k, t)
        if iv is None:
            print(f"{k:8.2f} {b:6.2f} {ak:6.2f} {mid:6.2f}   — 中间价不高于内在价值，无法反解")
            continue
        sig = iv * math.sqrt(t)
        buf = (s - k) / s
        z = buf / sig
        p_otm = N.cdf((math.log(s / k) - 0.5 * sig * sig) / sig)
        mark = "✅" if z >= a.z_min else "  "
        print(f"{k:8.2f} {b:6.2f} {ak:6.2f} {mid:6.3f} {iv:6.1%} {buf:6.1%} {z:5.2f} {p_otm:7.1%} {b*100:7.0f} {mark}")
    print(f"✅ = z ≥ {a.z_min}。收入按 bid 计（卖出成交按 bid，不按中间价）。下单价以平台为准。")


if __name__ == "__main__":
    main()
