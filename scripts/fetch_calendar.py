#!/usr/bin/env python3
"""宏观事件日历唯一来源：memory/state/macro_calendar.json（FOMC 自动 + BLS 三项人工维护）

为什么（2026-11-06）：事件日期有三份手抄副本（macro-events.md / options-screen.json rate_sensitive / FF 周历），
FF 只覆盖本周 + 下周，而新仓持有期 20–45 天——持有期内有没有 CPI / FOMC 全靠手抄日期，会悄悄过期、会互相对不上。
  - FOMC：解析美联储官网 fomccalendars.htm（各年面板 → 月份 + 日期，决议日取会期第二天）
  - CPI / PPI / 非农：BLS 网站对自动访问返回 403（需在请求头留联系邮箱，不代填用户邮箱），保留人工维护的 manual 段；
    self_check C15 检查未来 45 天覆盖，缺了就点名补齐——过期不再静默。
"""
import json
import os
import re
from datetime import date, datetime, timezone

import requests

PATH = "memory/state/macro_calendar.json"
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September",
                                      "October", "November", "December"], 1)}


def parse_fomc(html):
    """返回 [(决议日 ISO, 是否含经济预测 SEP)]。会期如 '27-28'、'16-17*'、跨月 'Apr/May 29-30'。"""
    out = []
    for ym in re.finditer(r"(\d{4}) FOMC Meetings", html):
        year = int(ym.group(1))
        nxt = re.search(r"\d{4} FOMC Meetings", html[ym.end():])
        block = html[ym.end(): ym.end() + nxt.start()] if nxt else html[ym.end():]
        for m in re.finditer(r'fomc-meeting__month[^>]*>\s*(?:<strong>)?\s*([A-Za-z/]+)\s*(?:</strong>)?.*?'
                             r'fomc-meeting__date[^>]*>\s*([\d\-\s*]+)', block, re.S):
            mon, days = m.group(1).split("/")[-1], m.group(2)
            nums = [int(x) for x in re.findall(r"\d+", days)]
            if mon not in MONTHS or not nums:
                continue
            out.append((date(year, MONTHS[mon], nums[-1]).isoformat(), "*" in days))
    return sorted(set(out))


OMB_ROWS = {"NFP": "The Employment Situation", "PPI": "Producer Price Indexes", "CPI": "Consumer Price Index"}


def parse_omb(text):
    """OMB《主要联邦经济指标发布时间表》PDF 文本 → {"CPI": [ISO 日期…], …}。
    格式：标题含年份；每个指标名后两行内有一行 12 个数（1–12 月的日，'--' 为当月无）。
    2026-11-07 起 BLS 三项用它自动化（BLS 网站拒绝自动访问，OMB 时间表是政府统一公布的口径）。"""
    year = int(re.search(r"PRINCIPAL FEDERAL ECONOMIC INDICATORS FOR (\d{4})", text).group(1))
    lines = text.splitlines()
    out = {}
    for key, name in OMB_ROWS.items():
        i = next(i for i, l in enumerate(lines) if l.strip() == name)
        row = next(l for l in lines[i + 1:i + 4] if len(re.findall(r"\d+|--", l)) == 12)
        out[key] = [date(year, m, int(d)).isoformat() for m, d in enumerate(re.findall(r"\d+|--", row), 1) if d != "--"]
    return year, out


def main():
    cal = json.load(open(PATH)) if os.path.exists(PATH) else {"manual": {}, "fomc": [], "fomc_source": None}
    try:
        r = requests.get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", headers=H, timeout=40)
        r.raise_for_status()
        meetings = parse_fomc(r.text)
        if len(meetings) < 8:
            raise RuntimeError(f"只解析到 {len(meetings)} 次会议，页面结构可能变了")
        cal["fomc"] = [{"date": d, "sep": sep} for d, sep in meetings]
        cal["fomc_source"] = {"url": r.url, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "error": None}
    except Exception as e:  # 失败保留上次结果，写明原因
        cal.setdefault("fomc_source", {})
        cal["fomc_source"] = dict(cal.get("fomc_source") or {}, error=repr(e)[:200])
    # BLS 三项：解析已抓取的 OMB 时间表（pages/ 里由 fetch_pages.py 抓到的 PFEI PDF），并入 manual 段
    import glob
    for f in sorted(glob.glob("pages/*pfei*.txt")):
        try:
            year, rows = parse_omb(open(f, encoding="utf-8").read())
        except Exception as e:
            print("OMB 解析失败", f, repr(e)[:120])
            continue
        for k, ds in rows.items():
            cal["manual"][k] = sorted(set(cal["manual"].get(k, [])) | set(ds))
        cal["manual"]["_source"] = (cal["manual"].get("_source", "").split("；OMB")[0]
                                    + f"；OMB 主要联邦经济指标发布时间表 {year}（{f}）")
    json.dump(cal, open(PATH, "w"), ensure_ascii=False, indent=1)
    print("FOMC", len(cal["fomc"]), "次", (cal["fomc_source"] or {}).get("error"))
    print("未来:", [m["date"] for m in cal["fomc"] if m["date"] >= date.today().isoformat()][:4])


if __name__ == "__main__":
    main()
