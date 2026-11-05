#!/usr/bin/env python3
"""财报日历：给 options_watch.json 里的标的抓未来 60 天的财报日，写 earnings_calendar.json

为什么（2026-11-05）：财报日靠搜索核实，已经错两次——INTC 记成 10/22（实为 10/29）、AMD 未核实就被开仓。
主源 Finnhub /calendar/earnings（抓价已用同一个 FINNHUB_TOKEN）；兜底 yfinance Ticker.calendar。
两源都取不到的标的写 null，并在 errors 里注明——option_quote 会把「无财报数据」当成未核实，不当成「没有财报」。
"""
import json
import os
import time
from datetime import date, datetime, timedelta, timezone

import requests
import yfinance as yf

TOKEN = os.environ.get("FINNHUB_TOKEN", "")


def from_finnhub(t, frm, to):
    if not TOKEN:
        raise RuntimeError("无 FINNHUB_TOKEN")
    r = requests.get("https://finnhub.io/api/v1/calendar/earnings",
                     params={"from": frm, "to": to, "symbol": t, "token": TOKEN}, timeout=20)
    r.raise_for_status()
    rows = r.json().get("earningsCalendar") or []
    # hour：bmo 盘前 / amc 盘后 / dmh 盘中；空表示未公布时段
    return [{"date": x["date"], "hour": x.get("hour") or ""} for x in rows if x.get("symbol") == t]


def from_yf(t, frm, to):
    cal = yf.Ticker(t).calendar or {}
    ds = cal.get("Earnings Date") or []
    out = []
    for d in ds if isinstance(ds, list) else [ds]:
        s = str(d)[:10]
        if frm <= s <= to:
            out.append({"date": s, "hour": ""})
    return out


def main():
    w = json.load(open("options_watch.json"))
    frm = date.today().isoformat()
    to = (date.today() + timedelta(days=60)).isoformat()
    out = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "window": [frm, to], "tickers": {}}
    for t in w["tickers"]:
        time.sleep(1.1)  # Finnhub 免费档 60 次/分钟（关注清单 60 只）
        errs = []
        for name, fn in (("finnhub", from_finnhub), ("yfinance", from_yf)):
            try:
                ev = fn(t, frm, to)
                out["tickers"][t] = {"source": name, "earnings": ev, "errors": errs}
                break
            except Exception as e:  # 单个标的失败不影响其他；失败原因写进产物
                errs.append(f"{name}: {repr(e)[:160]}")
        else:
            out["tickers"][t] = {"source": None, "earnings": None, "errors": errs}
    with open("earnings_calendar.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for t, r in out["tickers"].items():
        print(f"{t:6} {r['source']!s:9} {r['earnings']} {'; '.join(r['errors'])}")


if __name__ == "__main__":
    main()
