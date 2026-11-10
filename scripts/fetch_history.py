#!/usr/bin/env python3
"""按 history_request.json 取日线历史（收盘价 + 分红），写 history/<ticker>.json。

为什么（2026-11-10 SPYI 回撤测试）：回撤和税后收益要用逐日价格与每笔分配重算，容器里连不上行情源，走 Actions。
来源：Yahoo Finance（yfinance），未复权收盘价 + 单列分红，复权由分析端自己做（税后情景要改分红金额）。
请求：{"tickers": ["SPYI", "SPY"], "start": "2022-08-01"}
"""
import json
import os
from datetime import datetime, timezone

import yfinance as yf


def main():
    req = json.load(open("history_request.json"))
    os.makedirs("history", exist_ok=True)
    for t in req["tickers"]:
        h = yf.Ticker(t).history(start=req.get("start", "2015-01-01"), auto_adjust=False, actions=True)
        rows = [{"d": str(i.date()), "c": round(float(r["Close"]), 4), "div": round(float(r["Dividends"]), 5)} for i, r in h.iterrows()]
        out = {"ticker": t, "source": "Yahoo Finance 日线（yfinance，未复权收盘价 + 分红）", "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "start": rows[0]["d"] if rows else None, "end": rows[-1]["d"] if rows else None, "rows": rows}
        json.dump(out, open(f"history/{t.lower()}.json", "w"))
        print(t, len(rows), out["start"], out["end"])


if __name__ == "__main__":
    main()
