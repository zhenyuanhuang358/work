#!/usr/bin/env python3
"""一次性探测（2026-11-05）：美联储讲话三个候选源在 Actions 上能否取到、内容是否带当天时间戳。不进生产流程。"""
import json, re, requests
from datetime import datetime, timezone
H = {"User-Agent": "Mozilla/5.0 (options-research probe)"}
out = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "src": {}}
def get(name, url):
    try:
        r = requests.get(url, headers=H, timeout=30)
        out["src"][name] = {"url": url, "status": r.status_code, "bytes": len(r.content), "head": r.text[:3000]}
        return r
    except Exception as e:
        out["src"][name] = {"url": url, "error": repr(e)[:200]}
get("board_rss", "https://www.federalreserve.gov/feeds/speeches_and_testimony.xml")
get("board_calendar", "https://www.federalreserve.gov/newsevents/calendar.htm")
get("stl_fomcspeak", "https://www.stlouisfed.org/fomcspeak")
r = get("ff_week", "https://nfs.faireconomy.media/ff_calendar_thisweek.json")
try:
    ev = r.json()
    out["src"]["ff_week"]["usd_speak"] = [e for e in ev if e.get("country") == "USD" and re.search(r"Speaks|Fed|FOMC|Powell", e.get("title", ""))]
    out["src"]["ff_week"]["head"] = ""
except Exception as e:
    out["src"]["ff_week"]["parse_error"] = repr(e)[:200]
json.dump(out, open("fed_probe.json", "w"), ensure_ascii=False, indent=1)
for k, v in out["src"].items():
    print(k, v.get("status"), v.get("bytes"), v.get("error", ""))
