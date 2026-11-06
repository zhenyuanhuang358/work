#!/usr/bin/env python3
"""财报电话会原文抓取：按 transcript_request.json 抓原文，写 transcripts/<ticker>_<period>.txt + .json

为什么（2026-11-06 用户：「电话会原话一定要拿到」）：UBER Q3 报告的语气评分只能依据新闻稿和媒体转述，
因为 fool.com / sec.gov 不在会话容器的网络白名单里。GitHub Actions 网络不受限（期权链、BLS 同样走这里），
所以原文统一由 Actions 抓，会话只读产物——和其他数据源同一架构，不改环境权限。
源（按顺序）：
  1. 请求里直接给的 url
  2. Motley Fool 免费原文：Google News RSS 搜「<公司> <季度> earnings call transcript」找 fool.com 链接
  3. 公司 IR / 8-K 附件里的 PDF（请求里给 pdf_url；常见为 prepared remarks）
产物带说话人分段（Motley Fool 的「姓名 -- 职位」格式），供 Earner 引用原话；全部失败写 errors，不静默。
"""
import io
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote

import requests

H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def from_fool(url):
    from bs4 import BeautifulSoup
    r = requests.get(url, headers=H, timeout=40)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    body = soup.select_one("div.article-body") or soup.select_one("article") or soup
    paras = [p.get_text(" ", strip=True) for p in body.find_all(["p", "h2", "h3"])]
    text = "\n".join(p for p in paras if p)
    if len(text) < 5000:
        raise RuntimeError(f"正文过短 {len(text)} 字符，可能被拦或页面结构变了")
    return text


def find_fool(company, period):
    q = f'{company} {period} earnings call transcript site:fool.com'
    r = requests.get(f"https://news.google.com/rss/search?q={quote(q)}&hl=en-US&gl=US&ceid=US:en", headers=H, timeout=30)
    r.raise_for_status()
    for it in ET.fromstring(r.content).iter("item"):
        link, title = it.findtext("link") or "", it.findtext("title") or ""
        if "transcript" in title.lower():
            # Google News 链接是跳转页，跟随到 fool.com 原址
            rr = requests.get(link, headers=H, timeout=30, allow_redirects=True)
            m = re.search(r"https://www\.fool\.com/earnings/call-transcripts/[^\"'<>\s]+", rr.url + " " + rr.text)
            if m:
                return m.group(0).rstrip("/") + "/"
    raise RuntimeError("Google News 未找到 fool.com 原文链接")


def from_pdf(url):
    from pypdf import PdfReader
    r = requests.get(url, headers=H, timeout=60)
    r.raise_for_status()
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(r.content)).pages)


def speakers(text):
    """Motley Fool 格式：说话人单独成段「Name -- Title」或「Name: 」；返回 [(说话人, 发言)]。"""
    out, cur, buf = [], None, []
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Za-z.'\- ]{2,40}) -- (.{2,80})$", line.strip())
        if m:
            if cur and buf:
                out.append({"speaker": cur, "text": " ".join(buf)})
            cur, buf = f"{m.group(1)}（{m.group(2)}）", []
        elif cur:
            buf.append(line.strip())
    if cur and buf:
        out.append({"speaker": cur, "text": " ".join(buf)})
    return out


def main():
    req = json.load(open("transcript_request.json"))
    os.makedirs("transcripts", exist_ok=True)
    for job in req["jobs"]:
        t, period = job["ticker"].upper(), job["period"]
        out = {"ticker": t, "period": period, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "source": None, "url": None, "chars": 0, "speakers": [], "errors": []}
        text = None
        tries = []
        if job.get("url"):
            tries.append(("给定 url", lambda: (job["url"], from_fool(job["url"]))))
        tries.append(("Motley Fool", lambda: (lambda u: (u, from_fool(u)))(find_fool(job.get("company", t), period))))
        if job.get("pdf_url"):
            tries.append(("IR PDF", lambda: (job["pdf_url"], from_pdf(job["pdf_url"]))))
        for name, fn in tries:
            try:
                url, text = fn()
                out.update({"source": name, "url": url})
                break
            except Exception as e:  # 每个源失败都写明原因
                out["errors"].append(f"{name}: {repr(e)[:200]}")
        base = f"transcripts/{t.lower()}_{period.lower().replace(' ', '')}"
        if text:
            out["chars"] = len(text)
            out["speakers"] = [s["speaker"] for s in speakers(text)][:40]
            open(base + ".txt", "w").write(text)
        json.dump(out, open(base + ".json", "w"), ensure_ascii=False, indent=1)
        print(t, period, out["source"], out["chars"], "字符", out["errors"])


if __name__ == "__main__":
    main()
