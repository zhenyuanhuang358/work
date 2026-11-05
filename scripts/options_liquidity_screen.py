#!/usr/bin/env python3
"""全市场期权流动性初筛：从 SEC 报送人里找出「期权好成交、保证金放得下」的个股，写 options_liquidity.json

为什么（2026-11-05）：候选一直只来自手工攒的 14 只（options_watch.json），规则越来越严之后每天能过的只有 0–2 只。
这是全市场选股的第一层，只回答「这只票的期权能不能做」，不判断该不该卖。

三层：
  1. 股票池：SEC frames 营收 ≥ $1B 的报送人（复用 burry_screener 缓存）+ 常用 ETF；
     yfinance 批量取现价 → 股价 $10–150、市值 ≥ $5B（股价上限对应约 $5.5k 可取现金的单张保证金）
  2. 期权链：CBOE 延迟报价（与 fetch_options 同源）
  3. 流动性门槛（三项全过才算流动性好）：
     - （只标注，不卡）14 天内有到期日 = 有周度期权
     - 最近到期日、价外 0–15% 的 put：买卖报价差 ÷ 中间价 的中位数 ≤ 10%
     - 全链未平仓 ≥ 10,000 张，且当日成交 ≥ 1,000 张
局限：CBOE 延迟约 15 分钟，盘后跑时报价差偏宽（看 quote_time）；成交量是单日快照，宜在盘中跑。
"""
import json
import os
import re
import statistics
import sys
import time
from datetime import date, datetime, timedelta, timezone

import requests
import yfinance as yf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import burry_screener as bs  # noqa: E402

MIN_REV = 1e9
PRICE_MIN, PRICE_MAX = 10, 150
MIN_MCAP = 5e9
MAX_SPREAD = 0.10
MIN_OI, MIN_VOL = 10_000, 1_000
MIN_DTE = 7        # 报价差按 ≥7 天到期日量（我们做 1–6 周的单）
WEEKLY_DAYS = 14
OTM_BAND = 0.15
ETFS = ["SPY", "QQQ", "IWM", "DIA", "XLE", "XLF", "XLK", "XLV", "XLI", "XLU", "XLP", "XLY", "XLB",
        "SMH", "KRE", "XBI", "GLD", "SLV", "GDX", "TLT", "HYG", "EEM", "FXI", "EWZ", "ARKK", "USO"]
OCC = re.compile(r"^([A-Z.]+)(\d{6})([CP])(\d{8})$")


def universe():
    uni = bs.build_universe()
    tick = bs.fetch_ticker_map()
    out = {}
    for cik, e in uni.items():
        t = tick.get(cik)
        if not t or not e.get("revenue") or e["revenue"] < MIN_REV:
            continue
        sh = e.get("shares") or e.get("shares_gaap")
        out[t.replace(".", "-")] = sh
    return out


def prices(tickers):
    px = {}
    syms = sorted(tickers)
    for i in range(0, len(syms), 200):
        batch = syms[i:i + 200]
        df = yf.download(batch, period="5d", progress=False, threads=True, group_by="ticker", auto_adjust=False)
        for t in batch:
            try:
                s = (df[t]["Close"] if len(batch) > 1 else df["Close"]).dropna()
                if len(s):
                    px[t] = float(s.iloc[-1])
            except Exception:  # 个别 ticker 取不到价：跳过，计入 no_price
                pass
    return px


def chain_stats(t):
    # 2026-11-05 首跑 500 只里 438 只被 CBOE 限流（429）：请求之间留间隔，429 时指数退避重试
    for i in range(6):
        r = requests.get(f"https://cdn.cboe.com/api/global/delayed_quotes/options/{t}.json",
                         timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 429:
            break
        time.sleep(2 ** i)
    r.raise_for_status()
    j = r.json()
    d = j["data"]
    spot = float(d["current_price"])
    today = date.today()
    exps, oi, vol, near = set(), 0, 0, {}
    for o in d.get("options", []):
        m = OCC.match(o.get("option", ""))
        if not m:
            continue
        e = date(2000 + int(m.group(2)[:2]), int(m.group(2)[2:4]), int(m.group(2)[4:]))
        exps.add(e)
        oi += o.get("open_interest") or 0
        vol += o.get("volume") or 0
        k = int(m.group(4)) / 1000
        if m.group(3) == "P" and spot * (1 - OTM_BAND) <= k <= spot:
            near.setdefault(e, []).append((o.get("bid") or 0, o.get("ask") or 0))
    future = sorted(e for e in exps if e >= today)
    weekly = bool(future) and (future[0] - today).days <= WEEKLY_DAYS
    spread = None
    if near:
        # 口径 = 我们实际交易的期限：最近一个 ≥ MIN_DTE 天的到期日（2026-11-05 修：原取最近到期日，
        #   周四跑时取到次日到期的合约，权利金几分钱，报价差动辄 50%+，76 只挂 75 只——量的不是我们要卖的东西）
        cand = [e for e in near if (e - today).days >= MIN_DTE]
        e0 = min(cand) if cand else None
        if e0:
            sp = [(a - b) / ((a + b) / 2) for b, a in near[e0] if b > 0 and a >= b]
            spread = statistics.median(sp) if sp else None
    return {"spot": spot, "quote_time_utc": j.get("timestamp"), "next_expiry": future[0].isoformat() if future else None,
            "weekly": weekly, "n_expiries": len(future), "open_interest": oi, "volume": vol,
            "median_spread_otm_put": spread, "spread_expiry": e0.isoformat() if near and e0 else None}


def main():
    t0 = time.time()
    # 清单模式（2026-11-05 用户：先把备选库扩到 60 只，不跑全市场）：只筛 options_seed.json 里的人工候选
    seed = None
    if len(sys.argv) > 1 and sys.argv[1] == "--seed":
        seed = json.load(open("options_seed.json"))["tickers"]
    if seed:
        shares = {t: None for t in seed}
        px = prices(seed)
        pool = [t for t in seed if px.get(t) and PRICE_MIN <= px[t] <= PRICE_MAX]
        print(f"清单 {len(seed)}｜有价 {len(px)}｜股价 ${PRICE_MIN}–{PRICE_MAX}：{len(pool)}")
    else:
        shares = universe()
        px = prices(list(shares) + ETFS)
        pool = []
        for t, sh in shares.items():
            p = px.get(t)
            if p and PRICE_MIN <= p <= PRICE_MAX and sh and p * sh >= MIN_MCAP:
                pool.append(t)
        pool += [e for e in ETFS if e in px and PRICE_MIN <= px[e] <= PRICE_MAX * 5]  # ETF 不卡市值；高价 ETF 下游由保证金过滤
        print(f"SEC 营收 ≥ $1B：{len(shares)}｜有价：{len(px)}｜股票池（价格 / 市值 + ETF）：{len(pool)}")

    rows, errs = {}, {}
    for t in pool:
        try:
            rows[t] = chain_stats(t.replace("-", "."))
        except Exception as ex:  # 无期权或接口失败：记原因，不中断
            errs[t] = repr(ex)[:120]
        time.sleep(0.5)
    # 周度期权只标注、不卡门槛：只有月度期权的中盘股一样能做 2–4 周的单（首跑 41/62 只因此被误挡）
    for t, r in rows.items():
        r["pass"] = {
            "spread": r["median_spread_otm_put"] is not None and r["median_spread_otm_put"] <= MAX_SPREAD,
            "oi_vol": r["open_interest"] >= MIN_OI and r["volume"] >= MIN_VOL,
        }
        r["liquid"] = all(r["pass"].values())
    liquid = sorted([t for t, r in rows.items() if r["liquid"]], key=lambda t: -rows[t]["volume"])
    out = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": "seed" if seed else "全市场",
           "prices": {t: px.get(t) for t in (seed or [])},
           "criteria": {"price": [PRICE_MIN, PRICE_MAX], "min_mcap": MIN_MCAP, "min_revenue": MIN_REV,
                        "weekly_within_days": WEEKLY_DAYS, "spread_min_dte": MIN_DTE, "max_median_spread": MAX_SPREAD,
                        "min_open_interest": MIN_OI, "min_volume": MIN_VOL, "otm_band": OTM_BAND},
           "counts": {"sec_rev_ge_1b": len(shares), "pool": len(pool), "chain_ok": len(rows),
                      "chain_error": len(errs), "liquid": len(liquid),
                      "weekly": sum(1 for r in rows.values() if r["weekly"]),
                      "fail_spread": sum(1 for r in rows.values() if not r["pass"]["spread"]),
                      "fail_oi_vol": sum(1 for r in rows.values() if not r["pass"]["oi_vol"])},
           "liquid": liquid, "stats": rows, "errors": errs, "runtime_s": round(time.time() - t0)}
    with open("options_liquidity_seed.json" if seed else "options_liquidity.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out["counts"], ensure_ascii=False))
    print("流动性好：", ", ".join(liquid[:80]))


if __name__ == "__main__":
    main()
