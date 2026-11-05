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


def call_price(s, k, sig, t):
    return put_price(s, k, sig, t) + s - k  # 平价关系（r = 0）


def price(right, s, k, sig, t):
    return put_price(s, k, sig, t) if right == "P" else call_price(s, k, sig, t)


def implied_vol(px, s, k, t, right="P"):
    intrinsic = max(k - s, 0.0) if right == "P" else max(s - k, 0.0)
    if px <= intrinsic:
        return None
    lo, hi = 0.01, 5.0
    for _ in range(100):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if price(right, s, k, m, t) < px else (lo, m)
    return (lo + hi) / 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--expiry", help="不给 = 扫 options_watch.json 的 dte 窗口内全部到期日（2026-11-05 起新仓 20–45 天）")
    ap.add_argument("--strikes", type=float, nargs="*")
    ap.add_argument("--z-min", type=float, default=1.0, help="持有期含 CPI/PPI/FOMC/非农时用 1.2")
    ap.add_argument("--max-age", type=float, default=20, help="报价最长可接受分钟数")
    ap.add_argument("--file", default="options_chain.json")
    ap.add_argument("--right", choices=["P", "C"], default="P", help="P 卖 put / C 卖 call（2026-11-05 起纳入）")
    ap.add_argument("--bp", type=float, help="平台「可取现金」（美元，不是「最大购买力」）；给了就按 Reg-T 保证金做可执行性硬过滤（profile 1.1zc）")
    a = ap.parse_args()

    j = json.load(open(a.file))
    r = j["tickers"].get(a.ticker.upper())
    if not r or not r.get("rows"):
        sys.exit(f"{a.ticker}: options_chain.json 里没有数据（{r and r.get('errors')}）——把它加进 options_watch.json 并推送")

    if a.expiry:
        run(a, j, r)
        return
    try:
        lo, hi = json.load(open("options_watch.json")).get("dte", [20, 45])
    except OSError:
        lo, hi = 20, 45
    today = datetime.now(timezone.utc).date()
    exps = sorted({row["expiry"] for row in r["rows"] if row.get("right", "P") == a.right
                   and lo <= (datetime.fromisoformat(row["expiry"]).date() - today).days <= hi})
    if not exps:
        sys.exit(f"{a.ticker}: 链上没有 {lo}–{hi} 天的到期日——等 fetch-options 按 dte 窗口重抓")
    for e in exps:
        a.expiry = e
        d = (datetime.fromisoformat(e).date() - today).days
        print(f"\n==== {e}（{d} 天）" + ("｜30–45 天档：期限溢价 VIX3M/VIX < 1.20 时不做（tail-risk）" if d >= 30 else "")
              + ("｜≥35 天：剩 21 天未止盈就平" if d >= 35 else "") + " ====")
        run(a, j, r)


def run(a, j, r):
    now = datetime.now(timezone.utc)
    qt = r.get("quote_time_utc")
    if qt:
        qdt = datetime.fromisoformat(qt).replace(tzinfo=timezone.utc)
    else:  # yfinance 兜底没有报价时间，退而用抓取时间（偏乐观，故标注）
        qdt = datetime.fromisoformat(j["updated_at"])
    age = (now - qdt).total_seconds() / 60
    stale = age > a.max_age
    exp = datetime.fromisoformat(a.expiry).replace(hour=16, tzinfo=ET)

    # 排雷一：持有期内有没有财报（earnings_calendar.json，fetch-options 工作流同步抓）
    # 2026-11-05 加：INTC 财报日记错、AMD 未核实就开仓——财报日不能再靠搜索记忆。
    earn_flag = ""
    try:
        ec = json.load(open("earnings_calendar.json"))["tickers"].get(a.ticker.upper())
    except (OSError, KeyError, ValueError):
        ec = None
    if ec is None or ec.get("earnings") is None:
        earn_flag = "⚠ 财报日未核实（日历里没有该标的）"
    else:
        hits = [e for e in ec["earnings"] if now.date().isoformat() <= e["date"] <= a.expiry]
        if hits:
            earn_flag = "⛔ 持有期内有财报：" + "、".join(f"{e['date']}{(' ' + e['hour']) if e['hour'] else ''}" for e in hits)

    # 排雷三：基本面反向名单（options-screen.json；段永平 / 伯里原则，2026-11-05）
    try:
        scr = json.load(open("memory/state/options-screen.json"))
        black = scr["no_sell_put" if a.right == "P" else "no_sell_call"].get(a.ticker.upper())
    except (OSError, KeyError, ValueError):
        black = None
    if black:
        earn_flag = (earn_flag + "｜" if earn_flag else "") + f"⛔ 基本面名单：{black}"

    # 排雷四：IV 历史分位（Tastytrade：IV 处在自身高位才卖）。历史不足 15 个交易日时只显示「积累中」
    try:
        hist = [json.loads(l) for l in open("options_iv_history.jsonl") if l.strip()]
        ivs = sorted({h["date"]: h["atm_iv"] for h in hist if h["ticker"] == a.ticker.upper() and h.get("atm_iv")}.items())
        ivs = [v for _, v in ivs]
    except OSError:
        ivs = []

    # 排雷二：IV ÷ HV。卖方的优势来自「期权卖贵了」；IV 不高于实际波动 1.1 倍就没有优势
    try:
        from spread_check import hv_from_history
        hv = hv_from_history(a.ticker.upper())
    except (Exception, SystemExit):
        hv = None
    t = (exp - qdt).total_seconds() / (365 * 86400)
    s = r["spot"]

    print(f"{a.ticker.upper()} {a.expiry}{a.right}  源 {r['source']}  报价 {qt or '无时间戳(用抓取时刻)'} UTC  "
          f"距今 {age:.0f} 分钟{'  ⛔ 报价过期，不出定价' if stale else ''}  现价 {s:.2f}  剩 {t*365:.2f} 天")
    if stale:
        return
    pct_note = f"｜IV 历史 {len(ivs)} 天（≥15 天后启用分位过滤）" if len(ivs) < 15 else ""
    print(f"HV30 {hv:.0%}" if hv else "HV30 取不到（需完整价格历史：git fetch --unshallow）", f"｜{earn_flag or '持有期内无财报'}{pct_note}")
    print(f"{'行权':>8} {'bid':>6} {'ask':>6} {'中间价':>6} {'IV':>6} {'IV/HV':>6} {'缓冲':>6} {'z':>5} {'价外概率':>7} {'每张收入':>7} {'保证金':>7} {'报价差':>6}")
    for row in sorted(r["rows"], key=lambda x: -x["strike"] if a.right == "P" else x["strike"]):
        if row["expiry"] != a.expiry or (a.strikes and row["strike"] not in a.strikes):
            continue
        if row.get("right", "P") != a.right:
            continue
        # 只看价外：put 行权价在现价下方，call 在上方。价内的「IV」受内在价值主导，没有参考价值，
        # 而且卖价内期权不是收权利金，是方向性押注（11/05 用户问 HOOD 80C 时的教训）
        if (a.right == "P" and row["strike"] >= s) or (a.right == "C" and row["strike"] <= s):
            continue
        k, b, ak = row["strike"], row["bid"] or 0, row["ask"] or 0
        if b <= 0 or ak < b:
            print(f"{k:8.2f} {b:6.2f} {ak:6.2f}   — 买价为 0 或倒挂，无法反解")
            continue
        mid = (b + ak) / 2
        iv = implied_vol(mid, s, k, t, a.right)
        if iv is None:
            print(f"{k:8.2f} {b:6.2f} {ak:6.2f} {mid:6.2f}   — 中间价不高于内在价值，无法反解")
            continue
        sig = iv * math.sqrt(t)
        buf = (s - k) / s if a.right == "P" else (k - s) / s
        z = buf / sig
        d2 = (math.log(s / k) - 0.5 * sig * sig) / sig
        p_otm = N.cdf(d2) if a.right == "P" else N.cdf(-d2)
        # Reg-T 裸卖 put 保证金：max(20%×现价 − 价外额 + 权利金, 10%×行权价 + 权利金) × 100
        # 2026-10-29 校准：SPY 744P（现价 769、权利金 1.0）→ $12,980，与盈立实际要求「一万多」吻合
        otm_amt = max(s - k, 0) if a.right == "P" else max(k - s, 0)
        margin = max(0.2 * s - otm_amt + b, 0.1 * (k if a.right == "P" else s) + b) * 100
        spread = (ak - b) / b  # 买卖报价差占收入比例（不是价差策略）；>10% 不推（position-discipline 第 7 条）
        mark = "✅" if z >= a.z_min else "  "
        ratio = iv / hv if hv else None
        if spread > 0.10:
            mark = "⛔报价差"
        if ratio is not None and ratio < 1.1:
            mark = "⛔IV不贵"
        if len(ivs) >= 15 and sum(1 for v in ivs if v <= iv) / len(ivs) < 0.5:
            mark = "⛔IV低位"
        if black:
            mark = "⛔基本面"
        if earn_flag.startswith("⛔ 持有期内有财报"):
            mark = "⛔财报"
        # 平台实际保证金比 Reg-T 估算高：AMD 442.5P +7%（11/04）、HOOD 80C +13%（11/05）→ 按 ×1.15 比可取现金
        if a.bp is not None and margin * 1.15 > a.bp:
            mark = "⛔保证金"
        print(f"{k:8.2f} {b:6.2f} {ak:6.2f} {mid:6.3f} {iv:6.1%} {(f'{ratio:.2f}' if ratio else '—'):>6} {buf:6.1%} {z:5.2f} {p_otm:7.1%} {b*100:7.0f} {margin:7.0f} {spread:6.0%} {mark}")
    print(f"✅ = z ≥ {a.z_min}。收入按 bid 计（卖出成交按 bid，不按中间价）。保证金为 Reg-T 估算，以平台下单预览为准。"
          + (f"\n⛔保证金 = 单张保证金 > 可取现金 ${a.bp:,.0f}：平台不收这张单（可执行性硬过滤，不是资金偏好）。" if a.bp is not None else
             "\n未给 --bp：没做可执行性过滤。"))



if __name__ == "__main__":
    main()
