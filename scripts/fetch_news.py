#!/usr/bin/env python3
"""新闻快照：市场要闻 + 关注清单个股新闻，写 news.json（期权扫描「新闻标注」一步的原料）

为什么（2026-11-05 用户要求）：扫描只看价格、IV、财报，看不见地缘（美伊战事 → 油价）、美联储理事讲话、
知名投资人 / 政要发言这类会让标的跳空的消息。用户要的是「标注说明」，不是自动否决——判断相关性与方向
需要读懂内容，由扫描会话完成；本脚本只负责把带时间戳、带出处的原文抓齐，避免凭记忆或搜索摘要下结论。
数据源：Finnhub /news（general 要闻）与 /company-news（个股，近 3 天），与抓价、财报日历共用 FINNHUB_TOKEN。
"""
import json
import os
import time
from datetime import date, datetime, timedelta, timezone

import requests

TOKEN = os.environ.get("FINNHUB_TOKEN", "")
API = "https://finnhub.io/api/v1"


def get(path, **params):
    r = requests.get(f"{API}/{path}", params={**params, "token": TOKEN}, timeout=20)
    r.raise_for_status()
    return r.json() or []


def slim(x):
    return {"time_utc": datetime.fromtimestamp(x.get("datetime", 0), timezone.utc).isoformat(timespec="minutes"),
            "source": x.get("source"), "headline": x.get("headline"),
            "summary": (x.get("summary") or "")[:300], "url": x.get("url")}


def main():
    try:  # 扫描会话据此确认三份产物（链 / 价格 / 新闻）都是自己触发的那次（11/05 重跑问题）
        trig = open("price_fetch_trigger.txt").read().strip()
    except OSError:
        trig = None
    out = {"trigger": trig, "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "market": [], "tickers": {},
           "errors": []}
    if not TOKEN:
        out["errors"].append("无 FINNHUB_TOKEN")
    else:
        cutoff = datetime.now(timezone.utc).timestamp() - 36 * 3600
        try:  # 要闻：只留近 36 小时，按时间倒序取 60 条
            rows = [x for x in get("news", category="general") if x.get("datetime", 0) >= cutoff]
            out["market"] = [slim(x) for x in sorted(rows, key=lambda x: -x["datetime"])[:60]]
        except Exception as e:
            out["errors"].append(f"general: {repr(e)[:160]}")
        frm, to = (date.today() - timedelta(days=3)).isoformat(), date.today().isoformat()
        for t in json.load(open("options_watch.json"))["tickers"]:
            time.sleep(1.1)  # 免费档 60 次/分钟
            try:
                rows = sorted(get("company-news", symbol=t, **{"from": frm, "to": to}), key=lambda x: -x.get("datetime", 0))
                out["tickers"][t] = [slim(x) for x in rows[:8]]
            except Exception as e:
                out["tickers"][t] = []
                out["errors"].append(f"{t}: {repr(e)[:160]}")
    with open("news.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"market {len(out['market'])} 条；个股 {sum(len(v) for v in out['tickers'].values())} 条；错误 {len(out['errors'])}")


if __name__ == "__main__":
    main()
