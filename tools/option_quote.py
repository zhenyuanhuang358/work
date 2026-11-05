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
import os
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


_HV_CACHE = {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", help="不给 = --all 模式下扫 options_watch.json 全部标的")
    ap.add_argument("--all", action="store_true", help="汇总模式：扫全部标的 × dte 窗口，只列全部过关的行 + 各标的挡掉原因（2026-11-05）")
    ap.add_argument("--expiry", help="不给 = 扫 options_watch.json 的 dte 窗口内全部到期日（2026-11-05 起新仓 20–45 天）")
    ap.add_argument("--strikes", type=float, nargs="*")
    ap.add_argument("--z-min", type=float, default=1.2, help="默认 1.2：20–45 天持有期必含 CPI/PPI/FOMC 之一（第 19 条）；确无事件时可给 1.0")
    ap.add_argument("--max-age", type=float, default=20, help="报价最长可接受分钟数")
    ap.add_argument("--file", default="options_chain.json")
    ap.add_argument("--right", choices=["P", "C"], default="P", help="P 卖 put / C 卖 call（2026-11-05 起纳入）")
    ap.add_argument("--bp", type=float, help="平台「可取现金」（美元，不是「最大购买力」）；给了就按 Reg-T 保证金做可执行性硬过滤（profile 1.1zc）")
    ap.add_argument("--dte-max", type=int, help="期限溢价 VIX3M/VIX < 1.20 时给 29：只扫 20–29 天（tail-risk 闸门）")
    a = ap.parse_args()

    j = json.load(open(a.file))
    if a.all or not a.ticker:  # 不给 --ticker 默认走汇总（11/05：旧定时指令只写 --right P，免得逐只跑 120 次）
        return summary(a, j)
    r = j["tickers"].get(a.ticker.upper())
    if not r or not r.get("rows"):
        sys.exit(f"{a.ticker}: options_chain.json 里没有数据（{r and r.get('errors')}）——把它加进 options_watch.json 并推送")

    main_one(a, j, r)


def main_one(a, j, r):
    if a.expiry:
        run(a, j, r)
        return
    try:
        lo, hi = json.load(open("options_watch.json")).get("dte", [20, 45])
    except OSError:
        lo, hi = 20, 45
    if a.dte_max:
        hi = min(hi, a.dte_max)
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
    # 利率敏感（macro-events：HOOD / SOFI 持有期含 CPI / FOMC 只观察）与「谨慎」名单（只提示）——11/05 第三次重跑发现都靠手工
    try:
        rs = scr.get("rate_sensitive", {})
        rate_hit = [f"{d} {n}" for d, n in rs.get("events", {}).items() if a.ticker.upper() in rs.get("tickers", [])
                    and now.date().isoformat() <= d <= a.expiry]
        caution = scr.get("caution", {}).get(a.ticker.upper())
    except NameError:  # options-screen.json 读不到
        rate_hit, caution = [], None
    if caution:
        earn_flag = (earn_flag + "｜" if earn_flag else "") + f"⚠ 谨慎名单（只提示）：{caution}"

    # 排雷四：IV 历史分位（Tastytrade：IV 处在自身高位才卖）。历史不足 15 个交易日时只显示「积累中」
    try:
        hist = [json.loads(l) for l in open("options_iv_history.jsonl") if l.strip()]
        ivs = sorted({h["date"]: h["atm_iv"] for h in hist if h["ticker"] == a.ticker.upper() and h.get("atm_iv")}.items())
        ivs = [v for _, v in ivs]
    except OSError:
        ivs = []

    # 排雷二：IV ÷ HV。卖方的优势来自「期权卖贵了」；IV 不高于实际波动 1.1 倍就没有优势
    hv = r.get("hv30")  # fetch_options 用 yfinance 日线算的（2026-11-05 起）；没有再退回仓库收盘历史
    if not hv:  # 退回仓库收盘历史（读 git 历史，慢）：按标的缓存，--all 模式下每只只算一次
        key = a.ticker.upper()
        if key not in _HV_CACHE:
            try:
                from spread_check import hv_from_history
                _HV_CACHE[key] = hv_from_history(key)
            except (Exception, SystemExit):
                _HV_CACHE[key] = None
        hv = _HV_CACHE[key]
    t = (exp - qdt).total_seconds() / (365 * 86400)
    s = r["spot"]
    # 期限溢价闸门（tail-risk：VIX3M/VIX ≥ 1.20 才做 30–45 天档）——11/05 重跑发现只打说明不拦，30–45 天行照样 ✅
    term_block = False
    if (exp.date() - now.date()).days >= 30:
        try:
            tr = json.load(open("stock_prices.json"))
            prem = tr["tail_risk"]["vix3m"] / tr["vix"]
            term_block = prem < 1.20
        except (OSError, KeyError, TypeError, ZeroDivisionError):
            term_block = True  # 读不到就按关闭处理：宁可少做，不静默放行
    zmax = None

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
        if ratio is None:
            mark = "⚠无HV"  # IV/HV 过滤没法做：不能当作通过（11/05 49/60 只静默漏检）
        if len(ivs) >= 15 and sum(1 for v in ivs if v <= iv) / len(ivs) < 0.5:
            mark = "⛔IV低位"
        if black:
            mark = "⛔基本面"
        if earn_flag.startswith("⛔ 持有期内有财报"):
            mark = "⛔财报"
        # 平台实际保证金比 Reg-T 估算高：AMD 442.5P +7%（11/04）、HOOD 80C +13%（11/05）→ 按 ×1.15 比可取现金
        if a.bp is not None and margin * 1.15 > a.bp:
            mark = "⛔保证金"
        if rate_hit:
            mark = "⛔利率敏感"
        if term_block:
            mark = "⛔期限溢价"
        if mark == "✅" and caution:
            mark = "✅⚠谨慎"
        zmax = z if zmax is None else max(zmax, z)
        if getattr(a, "collect", None) is not None:
            a.collect.append({"ticker": a.ticker.upper(), "expiry": a.expiry, "strike": k, "bid": b, "ask": ak, "iv": iv,
                              "ivhv": ratio, "z": z, "p_otm": p_otm, "income": b * 100, "margin": margin,
                              "spread": spread, "mark": mark.strip() or "z不够",
                              "spot": s, "t": t, "right": a.right, "hv30": r.get("hv30"), "move": r.get("move_1y")})
        print(f"{k:8.2f} {b:6.2f} {ak:6.2f} {mid:6.3f} {iv:6.1%} {(f'{ratio:.2f}' if ratio else '—'):>6} {buf:6.1%} {z:5.2f} {p_otm:7.1%} {b*100:7.0f} {margin:7.0f} {spread:6.0%} {mark}")
    # 链不够宽：最远一档价外仍到不了 z 门槛（高 IV 标的 + 长到期，band 不够）——不能当成「没有合格行权价」
    if zmax is not None and zmax < a.z_min:
        print(f"⚠ 链不够宽：最远一档 z 只有 {zmax:.2f} < {a.z_min}——加大 options_watch.json 的 band")
        if getattr(a, "collect", None) is not None:
            a.collect.append({"ticker": a.ticker.upper(), "mark": "⚠链不够宽"})
    print(f"✅ = z ≥ {a.z_min}。收入按 bid 计（卖出成交按 bid，不按中间价）。保证金为 Reg-T 估算，以平台下单预览为准。"
          + (f"\n⛔保证金 = 单张保证金 > 可取现金 ${a.bp:,.0f}：平台不收这张单（可执行性硬过滤，不是资金偏好）。" if a.bp is not None else
             "\n未给 --bp：没做可执行性过滤。"))



def summary(a, j):
    """全清单汇总：每个 (标的, 到期) 只保留过关行；其余按挡掉原因计数。过关行附跳空压力（tools/gap_stress.py）。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import gap_stress as gs
    import contextlib
    import io
    from collections import Counter
    tick = json.load(open("options_watch.json"))["tickers"]
    a.collect, why = [], {}
    for t in tick:
        r = j["tickers"].get(t)
        if not r or not r.get("rows"):
            why[t] = Counter({"无链": 1})
            continue
        a.ticker, a.expiry = t, None
        before = len(a.collect)
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                main_one(a, j, r)
            except SystemExit:
                pass
        why[t] = Counter(x["mark"] for x in a.collect[before:] if not x["mark"].startswith("✅"))
    ok = [x for x in a.collect if x["mark"].startswith("✅")]
    print(f"== {a.right} 汇总｜z ≥ {a.z_min}｜bp {a.bp}｜过关 {len(ok)} 行 / {len(a.collect)} 行，{len({x['ticker'] for x in ok})} 只标的")
    print(f"{'标的':6} {'到期':10} {'行权':>7} {'bid':>5} {'ask':>5} {'IV/HV':>5} {'z':>5} {'价外概率':>6} {'收入':>5} {'保证金':>6} {'报价差':>5}")
    for x in sorted(ok, key=lambda x: (-x["income"] / x["margin"])):
        print(f"{x['ticker']:6} {x['expiry']:10} {x['strike']:7.2f} {x['bid']:5.2f} {x['ask']:5.2f} {x['ivhv'] or 0:5.2f} {x['z']:5.2f} "
              f"{x['p_otm']:6.1%} {x['income']:5.0f} {x['margin']:6.0f} {x['spread']:5.0%} {x['mark'][1:]}")
        print("        跳空压力：" + gs.fmt(gs.stress(x["right"], x["spot"], x["strike"], x["t"], x["iv"], x["bid"], x["hv30"], x["move"])))
    tot = Counter()
    for c in why.values():
        tot.update({k: 1 for k in c})
    print("挡掉原因（按标的计，一只可有多因）：", dict(tot.most_common()))
    # 主因不算期限溢价：那道闸门只管 30–45 天档，算进来会盖住 20–29 天的真实原因（11/05 XLE 被误显示为期限溢价）
    gate = sum(1 for c in why.values() if c.get("⛔期限溢价"))
    print(f"⛔期限溢价（30–45 天档闸门）涉及 {gate} 只标的；下面的主因只看闸门以外的行")
    okt = {x['ticker'] for x in ok}
    print("无过关行的标的主因：", {t: (Counter({k: v for k, v in c.items() if k != "⛔期限溢价"}).most_common(1) or [("仅期限溢价",)])[0][0]
                                    for t, c in why.items() if c and t not in okt})


if __name__ == "__main__":
    main()
