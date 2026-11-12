#!/usr/bin/env python3
"""通用网页原文抓取：按 pages_request.json 抓正文，写 pages/<slug>.txt + pages/index.json

为什么（2026-11-06 AI 导购提纲调研）：会话容器的网络白名单外的站点（界面、人人都是产品经理、杭州网……）打不开，
profile 1.1y 规定搜索摘要不是来源、关键事实要看到原文。电话会原文已用同一思路（fetch_transcript.py）解决，
这里推广到任意网页：GitHub Actions 网络不受限，会话只读产物。
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone

import requests

H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
     "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}


def extract(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        t.decompose()
    title = (soup.title.get_text(strip=True) if soup.title else "")
    body = max(soup.find_all(["article", "main", "div"]), key=lambda n: len(n.find_all("p")), default=soup)
    # 11/09 NVDA 新闻稿：财务报表在 <table> 里，只取 p/li 会丢掉现金流量表 → 表格逐行输出（单元格用 | 分隔）
    paras = []
    for n in body.find_all(["p", "h1", "h2", "h3", "li", "tr"]):
        if n.name == "tr":
            cells = [c.get_text(" ", strip=True) for c in n.find_all(["td", "th"])]
            paras.append(" | ".join(c for c in cells if c))
        elif not n.find_parent("table"):
            paras.append(n.get_text(" ", strip=True))
    return title, "\n".join(p for p in paras if len(p) > 1)


def main():
    req = json.load(open("pages_request.json"))
    os.makedirs("pages", exist_ok=True)
    idx_path = "pages/index.json"
    idx = json.load(open(idx_path)) if os.path.exists(idx_path) else {}
    for url in req["urls"]:
        slug = re.sub(r"[^a-z0-9]+", "_", url.lower().split("//", 1)[-1])[:60] + "_" + hashlib.md5(url.encode()).hexdigest()[:6]
        rec = {"url": url, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "file": f"pages/{slug}.txt"}
        try:
            r = requests.get(url, headers=H, timeout=40)
            r.raise_for_status()
            if "pdf" in r.headers.get("Content-Type", "").lower() or url.lower().endswith(".pdf"):
                # PDF（11/07：OMB 主要经济指标发布时间表）——逐页抽文字，保留换行便于解析表格
                import io
                from pypdf import PdfReader
                pages = PdfReader(io.BytesIO(r.content)).pages
                title, text = url.rsplit("/", 1)[-1], "\n".join(f"=== p{i + 1}\n" + (pg.extract_text() or "") for i, pg in enumerate(pages))
            else:
                r.encoding = r.apparent_encoding or r.encoding
                title, text = extract(r.text)
            if len(text) < 300:
                raise RuntimeError(f"正文过短 {len(text)} 字符（可能需要登录或被拦）")
            open(rec["file"], "w", encoding="utf-8").write(f"TITLE: {title}\nURL: {url}\n\n{text}")
            rec.update({"title": title, "chars": len(text), "error": None})
        except Exception as e:  # 失败写明原因，不静默
            rec.update({"title": None, "chars": 0, "error": repr(e)[:200]})
        idx[url] = rec
        print(("OK " if not rec["error"] else "ERR"), rec["chars"], url, rec["error"] or "")
    json.dump(idx, open(idx_path, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
