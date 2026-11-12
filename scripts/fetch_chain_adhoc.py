#!/usr/bin/env python3
"""单标的期权链（指定到期日）：按 chain_request.json 抓，写 chains/<TICKER>.json

为什么单独一个：options_watch.json 是每日卖方扫描的标的池，加进去会改扫描范围；
财报前算「市场定价的跳空幅度」、比较价差结构时，只需要临时抓一只、到期在财报后第一个周五。
复用 fetch_options.from_cboe，口径一致（买卖价原始字段，IV 由本地工具反解）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from fetch_options import from_cboe, now  # noqa: E402


def main():
    req = json.load(open("chain_request.json"))
    os.makedirs("chains", exist_ok=True)
    exp = set(req["expiries"])
    for t in req["tickers"]:
        try:
            out = from_cboe(t, lambda e: e in exp, req.get("right", "PC"), req.get("band", 0.25))
            out.update(fetched_at=now(), trigger=req.get("trigger"))
        except Exception as e:  # noqa: BLE001
            out = {"error": str(e), "fetched_at": now(), "trigger": req.get("trigger")}
        json.dump(out, open(f"chains/{t}.json", "w"), indent=1)
        print(t, len(out.get("rows", [])), out.get("error", ""))


if __name__ == "__main__":
    main()
