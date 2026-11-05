#!/usr/bin/env python3
"""美联储讲话：谁、什么时候讲（日程）+ 讲了什么（理事原文 / 新闻标题），写 fed_speak.json

为什么（2026-11-05 用户要求「去搞定源头」）：扫描步骤 7b 靠 WebSearch 找美联储讲话，两次扫描都只搜到 7 月旧闻
（Barkin / Logan / Hammack），当天谁讲了什么一概不知。11/05 在 Actions 上实测三个源（scripts/probe_fed.py，已删）：
  - FF 周历 JSON（nfs.faireconomy.media）：全部 FOMC 参与者（理事 + 12 位地区联储主席）的讲话时间，含本周与下周
    → 唯一能覆盖地区联储主席日程的免费结构化源；只有「谁、何时」，没有内容
  - 美联储理事会 RSS（federalreserve.gov/feeds/speeches_and_testimony.xml）：理事讲话原文链接 + 发布时间；不含地区主席
  - 圣路易斯联储 FOMC Speak：全员但为 HTML，需另写解析，暂不用
内容层：① news.json（Finnhub）按讲话人姓氏匹配标题；② Google News RSS 按讲话人搜近 2 天报道（Finnhub 几乎不报联储官员讲话，
实测 0/60）——路透 / 彭博 / CNBC 的「Fed's X says …」就是当天讲了什么。标题只作标注原料，鹰鸽判断由扫描会话读标题后写明出处。
"""
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

H = {"User-Agent": "Mozilla/5.0 (options-research)"}
FF = ["https://nfs.faireconomy.media/ff_calendar_thisweek.json", "https://nfs.faireconomy.media/ff_calendar_nextweek.json"]
BOARD = "https://www.federalreserve.gov/feeds/speeches_and_testimony.xml"
SPEAK = re.compile(r"(?:FOMC Member|Fed Chair|Fed Vice Chair|Fed Governor)\s+([A-Z][a-z]+)|([A-Z][a-z]+) Speaks")


def main():
    now = datetime.now(timezone.utc)
    out = {"updated_at": now.isoformat(timespec="seconds"), "schedule": [], "usd_high": [], "board": [], "headlines": [],
           "errors": []}
    try:
        out["trigger"] = open("price_fetch_trigger.txt").read().strip()
    except OSError:
        out["trigger"] = None

    for url in FF:  # 日程：本周 + 下周
        try:
            r = requests.get(url, headers=H, timeout=30)
            if r.status_code == 404:  # 下周历在周中前可能还没发布
                continue
            r.raise_for_status()
            for e in r.json():
                if e.get("country") != "USD":
                    continue
                m = SPEAK.search(e.get("title", ""))
                if m and "Speaks" in e["title"]:
                    out["schedule"].append({"time": e["date"], "speaker": m.group(1) or m.group(2), "title": e["title"]})
                elif e.get("impact") == "High":  # 顺带：高影响美国数据（CPI / 非农 / FOMC），与 macro-events 日历互相核对
                    out["usd_high"].append({"time": e["date"], "title": e["title"], "forecast": e.get("forecast"),
                                            "previous": e.get("previous")})
        except Exception as ex:
            out["errors"].append(f"ff {url[-25:]}: {repr(ex)[:150]}")

    try:  # 理事讲话原文（近 10 天）
        r = requests.get(BOARD, headers=H, timeout=30)
        r.raise_for_status()
        root = ET.fromstring(r.content.decode("utf-8-sig").encode())
        for it in root.iter("item"):
            pub = parsedate_to_datetime(it.findtext("pubDate").strip())
            if now - pub <= timedelta(days=10):
                out["board"].append({"time_utc": pub.isoformat(timespec="minutes"), "title": it.findtext("title"),
                                     "where": it.findtext("description"), "url": it.findtext("link")})
    except Exception as ex:
        out["errors"].append(f"board rss: {repr(ex)[:150]}")

    # 内容：近 7 天日程里的讲话人 + 近期理事，在 news.json 标题 / 摘要里按姓氏匹配
    names = {s["speaker"] for s in out["schedule"]} | {b["title"].split(",")[0] for b in out["board"]}
    names |= {"Powell", "Jefferson", "Barr", "Bowman", "Cook", "Waller", "Miran"}  # 理事会常驻成员，日程不全时兜底
    try:
        news = json.load(open("news.json"))
        items = news.get("market", []) + [x for v in news.get("tickers", {}).values() for x in v]
        seen = set()
        for x in items:
            text = f"{x.get('headline', '')} {x.get('summary', '')}"
            for n in names:
                if re.search(rf"\b{n}\b", text) and re.search(r"\bFed\b|Federal Reserve|FOMC|rate", text) and x["headline"] not in seen:
                    seen.add(x["headline"])
                    out["headlines"].append({"speaker": n, **{k: x.get(k) for k in ("time_utc", "source", "headline", "url")}})
    except OSError:
        out["errors"].append("news.json 不存在（fetch_news 未先跑）")
    # Google News RSS（11/05 加：Finnhub 要闻 60 条里一条美联储讲话都没有）：近 2 天讲过 / 即将讲的人 + 主席，每人一查
    recent = {s["speaker"] for s in out["schedule"]
              if abs((datetime.fromisoformat(s["time"]) - now).total_seconds()) <= 2 * 86400} | {"Powell"}
    for n in sorted(recent):
        try:
            r = requests.get("https://news.google.com/rss/search", headers=H, timeout=20,
                             params={"q": f'"{n}" Fed when:2d', "hl": "en-US", "gl": "US", "ceid": "US:en"})
            r.raise_for_status()
            for it in list(ET.fromstring(r.content).iter("item"))[:6]:
                title = it.findtext("title") or ""
                if not re.search(rf"\b{n}\b", title) or not re.search(r"Fed|FOMC|[Rr]ate|[Ii]nflation|[Pp]olicy", title):
                    continue  # 同姓误匹配（11/05 Williams 讣告）
                pub = parsedate_to_datetime(it.findtext("pubDate"))
                out["headlines"].append({"speaker": n, "time_utc": pub.isoformat(timespec="minutes"),
                                         "source": (it.findtext("source") or "Google News"), "headline": title,
                                         "url": it.findtext("link")})
        except Exception as ex:
            out["errors"].append(f"gnews {n}: {repr(ex)[:120]}")
    out["headlines"].sort(key=lambda x: x.get("time_utc") or "", reverse=True)

    with open("fed_speak.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"日程 {len(out['schedule'])}｜高影响数据 {len(out['usd_high'])}｜理事原文 {len(out['board'])}｜匹配标题 {len(out['headlines'])}｜错误 {out['errors']}")
    for s in out["schedule"]:
        print("  ", s["time"], s["title"])
    for h in out["headlines"][:10]:
        print("  ", h["time_utc"], h["speaker"], h["headline"][:100])


if __name__ == "__main__":
    main()
