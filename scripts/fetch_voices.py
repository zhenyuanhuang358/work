#!/usr/bin/env python3
"""政要与知名投资人发言：按人名搜近 2 天报道标题，写 voices.json（期权扫描步骤 7b 新闻标注的原料）

为什么（2026-11-06，feedback FB-20261105-14）：用户 11/05 要求扫描标注「政要、知名金融人士讲话对股市 / 个股的影响」。
美联储讲话已由 fetch_fed.py 解决，政要与投资人仍只靠 WebSearch，两次扫描都「未搜到」。同一做法：Google News RSS 按人名搜，
只留标题里同时出现人名与市场关键词的条目（防同名误匹配，fetch_fed 11/05 Williams 讣告教训）。
名单只放**发言会直接移动市场**的人；改名单就改 PEOPLE，不必改逻辑。标题只作标注原料，影响判断由扫描会话写并注出处。
"""
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests

H = {"User-Agent": "Mozilla/5.0 (options-research)"}
# (搜索名, 标题里必须出现的姓氏, 角色, 典型影响板块)
PEOPLE = [
    ("Donald Trump", "Trump", "美国总统", "关税 / 制裁 / 能源 / 中概"),
    ("Scott Bessent", "Bessent", "财长", "美债 / 美元 / 关税"),
    ("Howard Lutnick", "Lutnick", "商务部长", "关税 / 出口管制 / 半导体"),
    ("Jamieson Greer", "Greer", "贸易代表", "关税 / 中概"),
    ("Warren Buffett", "Buffett", "伯克希尔", "宽基 / 金融 / 消费"),
    ("Ray Dalio", "Dalio", "桥水创始人", "美债 / 黄金 / 宏观"),
    ("Michael Burry", "Burry", "Scion", "个股做空 / AI 估值"),
    ("Bill Ackman", "Ackman", "潘兴广场", "个股 / 美债"),
    ("Jamie Dimon", "Dimon", "摩根大通 CEO", "银行 / 信用 / 宏观"),
    ("Elon Musk", "Musk", "特斯拉 CEO", "TSLA / 自动驾驶 / AI"),
]
MARKET = re.compile(r"tariff|sanction|rate|Fed|inflation|stock|market|shares|bond|Treasury|yield|dollar|oil|China|chip|"
                    r"export|trade|deal|recession|economy|bubble|short|AI|bank|buy|sell|stake|earnings|price", re.I)


def search(name, surname):
    q = f'"{name}" when:2d'
    r = requests.get(f"https://news.google.com/rss/search?q={quote(q)}&hl=en-US&gl=US&ceid=US:en", headers=H, timeout=20)
    r.raise_for_status()
    out = []
    for it in list(ET.fromstring(r.content).iter("item"))[:12]:
        title = it.findtext("title") or ""
        if re.search(rf"\b{surname}\b", title) and MARKET.search(title):
            out.append({"time_utc": parsedate_to_datetime(it.findtext("pubDate")).isoformat(timespec="minutes"),
                        "source": it.findtext("source") or "Google News", "headline": title, "url": it.findtext("link")})
    return out[:5]


def main():
    out = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "people": [], "errors": []}
    try:
        out["trigger"] = open("price_fetch_trigger.txt").read().strip()
    except OSError:
        out["trigger"] = None
    for name, surname, role, sectors in PEOPLE:
        try:
            hl = search(name, surname)
        except Exception as e:  # 单人失败写明原因，不影响其他人
            out["errors"].append(f"{name}: {repr(e)[:120]}")
            hl = []
        out["people"].append({"name": name, "role": role, "sectors": sectors, "headlines": hl})
    json.dump(out, open("voices.json", "w"), ensure_ascii=False, indent=1)
    print(f"共 {sum(len(p['headlines']) for p in out['people'])} 条｜错误 {out['errors']}")
    for p in out["people"]:
        for h in p["headlines"][:2]:
            print(f"  {p['name']:15} {h['time_utc']} {h['headline'][:90]}")


if __name__ == "__main__":
    main()
