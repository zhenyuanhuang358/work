#!/usr/bin/env python3
"""期权链抓取：按 options_watch.json 抓候选的 put（或 call）买卖价，写 options_chain.json

为什么有它：期权报价曾是 COO 期权流水线唯一要用户手动截图的数据（2026-10-29 首跑发现）。
数据源（2026-10-29 在 Actions 上实测两源同一合约 bid/ask 基本一致，均约 15 分钟延迟）：
  主：CBOE 官方延迟报价 JSON —— 交易所发布，带报价时间戳与希腊字母
  兜底：yfinance option_chain —— 抓价脚本已在用，零新依赖；无时间戳
只存买卖价等原始字段，不信任任一源自带的 IV（两源算法不同，UBER 同一合约 64% vs 67%）；
IV 一律由 tools/option_quote.py 从中间价反解，口径与「平台报价反解」一致（profile 1.1x）。
"""
import json
import math
import re
import time
from datetime import datetime, timezone

import requests
import yfinance as yf

OCC = re.compile(r"^([A-Z.]+)(\d{6})([CP])(\d{8})$")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def from_cboe(t, expiries, right, band):
    # 关注清单扩到 60 只（2026-11-05）：CBOE 会对连续请求回 429，退避重试
    for i in range(6):
        r = requests.get(f"https://cdn.cboe.com/api/global/delayed_quotes/options/{t}.json",
                         timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 429:
            break
        time.sleep(2 ** i)
    r.raise_for_status()
    j = r.json()
    data = j["data"]
    spot = float(data["current_price"])
    want = {e[2:4] + e[5:7] + e[8:10]: e for e in expiries}
    rows = []
    for o in data.get("options", []):
        m = OCC.match(o.get("option", ""))
        if not m or m.group(2) not in want or m.group(3) not in right:
            continue
        k = int(m.group(4)) / 1000
        if abs(k / spot - 1) > band:
            continue
        rows.append({"expiry": want[m.group(2)], "right": m.group(3), "strike": k, "bid": o.get("bid"), "ask": o.get("ask"),
                     "delta": o.get("delta"), "oi": o.get("open_interest"), "volume": o.get("volume"),
                     "last_trade": o.get("last_trade_time")})
    # CBOE 顶层 timestamp 是 UTC（2026-10-29 实测：14:39:11 对应运行时刻 14:39:35Z）；
    # 而每个合约的 last_trade_time 是美东时间——两者口径不同，别混用
    return {"source": "cboe", "quote_time_utc": j.get("timestamp"), "spot": spot, "rows": rows}


def from_yf(t, expiries, right, band):
    tk = yf.Ticker(t)
    spot = float(tk.fast_info["last_price"])
    avail = set(tk.options)
    rows = []
    for e in expiries:
        if e not in avail:
            continue
        ch = tk.option_chain(e)
        for rt, df in (("P", ch.puts), ("C", ch.calls)):
            if rt not in right:
                continue
            for _, r in df.iterrows():
                k = float(r["strike"])
                if abs(k / spot - 1) <= band:
                    rows.append({"expiry": e, "right": rt, "strike": k, "bid": float(r["bid"]), "ask": float(r["ask"]),
                                 "delta": None, "oi": int(r["openInterest"] or 0), "volume": None,
                                 "last_trade": str(r["lastTradeDate"])})
    return {"source": "yfinance", "quote_time_utc": None, "spot": spot, "rows": rows}


def _put(S, K, s, T):
    from statistics import NormalDist
    N = NormalDist()
    d1 = (math.log(S / K) + 0.5 * s * s * T) / (s * math.sqrt(T))
    return K * N.cdf(-(d1 - s * math.sqrt(T))) - S * N.cdf(-d1)


def atm_iv(res):
    """最近到期日、最接近平值的 put 中间价反解 IV——给 option_quote 的 IV 历史分位用（2026-11-05）。"""
    rows = [r for r in res["rows"] if r.get("right", "P") == "P" and r["bid"] and r["ask"]]
    if not rows:
        return None, None
    exp = min(r["expiry"] for r in rows)
    r = min((r for r in rows if r["expiry"] == exp), key=lambda r: abs(r["strike"] - res["spot"]))
    T = max((datetime.fromisoformat(exp).replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).days, 1) / 365
    mid, lo, hi = (r["bid"] + r["ask"]) / 2, 0.01, 5.0
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if _put(res["spot"], r["strike"], m, T) < mid else (lo, m)
    return exp, round((lo + hi) / 2, 4)


def main():
    w = json.load(open("options_watch.json"))
    # right：「P」「C」或「PC」（两侧都抓，2026-11-05 起卖 call 纳入策略）
    expiries, right, band = w["expiries"], w.get("right", "P"), w.get("band", 0.2)
    out = {"updated_at": now(), "watch": w, "tickers": {}}
    for t in w["tickers"]:
        time.sleep(0.4)
        errs = []
        for fn in (from_cboe, from_yf):
            try:
                res = fn(t, expiries, right, band)
                if res["rows"]:
                    res["errors"] = errs
                    out["tickers"][t] = res
                    break
                errs.append(f"{fn.__name__}: 无匹配合约")
            except Exception as e:  # 单个标的失败不影响其他标的；失败原因写进产物
                errs.append(f"{fn.__name__}: {repr(e)[:200]}")
        else:
            out["tickers"][t] = {"source": None, "rows": [], "errors": errs}
    with open("options_chain.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open("options_iv_history.jsonl", "a") as f:
        for t, r in out["tickers"].items():
            if r["rows"]:
                exp, iv = atm_iv(r)
                if iv:
                    f.write(json.dumps({"date": out["updated_at"][:10], "ticker": t, "expiry": exp, "atm_iv": iv}) + "\n")
    for t, r in out["tickers"].items():
        print(f"{t:6} {r['source']!s:9} {len(r['rows']):3} 行  {'; '.join(r['errors'])}")


if __name__ == "__main__":
    main()
