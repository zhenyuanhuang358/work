#!/usr/bin/env python3
"""期权链数据源探测（2026-10-29，最小验证，不进生产流程）

为什么：期权报价是 COO 期权流水线唯一必须用户手动截图喂的数据。
候选两个免费、零注册的源，在 GitHub Actions 上各抓一次同一批合约，比较：
  A. yfinance option_chain（抓价脚本已在用 yfinance，零新依赖）
  B. CBOE 官方延迟报价 JSON（cdn.cboe.com，交易所自己发的，15 分钟延迟）
判据：能否拿到 bid / ask / IV；时间戳多旧；两源同一合约的 bid/ask 差多少。
产物：options_probe.json（只写这一个文件）。
"""
import json
import re
import time
from datetime import datetime, timezone

import requests
import yfinance as yf

TICKERS = ["UBER", "F", "SPY"]
EXPIRY = "2026-11-06"
BAND = 0.15  # 只取现价 ±15% 的 put，够覆盖卖方候选
OCC = re.compile(r"^([A-Z.]+)(\d{6})([CP])(\d{8})$")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def probe_yf(t, spot):
    t0 = time.time()
    tk = yf.Ticker(t)
    exps = list(tk.options)
    if EXPIRY not in exps:
        return {"ok": False, "err": f"无 {EXPIRY}，可选：{exps[:6]}"}
    puts = tk.option_chain(EXPIRY).puts
    rows = []
    for _, r in puts.iterrows():
        k = float(r["strike"])
        if abs(k / spot - 1) <= BAND:
            rows.append({"strike": k, "bid": float(r["bid"]), "ask": float(r["ask"]),
                         "iv": round(float(r["impliedVolatility"]), 4),
                         "last_trade": str(r["lastTradeDate"]), "oi": int(r["openInterest"] or 0)})
    return {"ok": True, "secs": round(time.time() - t0, 2), "n": len(rows), "rows": rows}


def probe_cboe(t, spot):
    t0 = time.time()
    url = f"https://cdn.cboe.com/api/global/delayed_quotes/options/{t}.json"
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code != 200:
        return {"ok": False, "err": f"HTTP {r.status_code}"}
    j = r.json()
    data = j.get("data", {})
    yymmdd = EXPIRY[2:4] + EXPIRY[5:7] + EXPIRY[8:10]
    rows = []
    for o in data.get("options", []):
        m = OCC.match(o.get("option", ""))
        if not m or m.group(2) != yymmdd or m.group(3) != "P":
            continue
        k = int(m.group(4)) / 1000
        if abs(k / spot - 1) <= BAND:
            rows.append({"strike": k, "bid": o.get("bid"), "ask": o.get("ask"), "iv": o.get("iv"),
                         "delta": o.get("delta"), "last_trade": o.get("last_trade_time")})
    return {"ok": True, "secs": round(time.time() - t0, 2), "timestamp": j.get("timestamp"),
            "underlying": data.get("current_price"), "n": len(rows),
            "keys": sorted((data.get("options") or [{}])[0].keys()), "rows": rows}


def main():
    out = {"run_at": now(), "expiry": EXPIRY, "tickers": {}}
    for t in TICKERS:
        res = {}
        try:
            spot = float(yf.Ticker(t).fast_info["last_price"])
        except Exception as e:  # 探测脚本：任何失败都记下来，不中断其他标的
            spot = None
            res["spot_err"] = repr(e)
        res["spot"] = spot
        for name, fn in (("yfinance", probe_yf), ("cboe", probe_cboe)):
            try:
                res[name] = fn(t, spot) if spot else {"ok": False, "err": "无现价"}
            except Exception as e:
                res[name] = {"ok": False, "err": repr(e)[:300]}
        out["tickers"][t] = res
    with open("options_probe.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for t, r in out["tickers"].items():
        print(t, {k: (v.get("ok"), v.get("n"), v.get("err")) for k, v in r.items() if isinstance(v, dict)})


if __name__ == "__main__":
    main()
