#!/usr/bin/env python3
"""美国宏观数据实际值（非农 / 失业率 / 时薪 / CPI / PPI），写 macro_actuals.json

为什么（2026-11-06 用户：「非农数据这么重要，怎么可以抓不到就算了」）：11/06 非农公布当天，扫描只拿到 SeekingAlpha
标题「超预期」，具体数字 WebSearch 搜不到，报告写了「未核实」——事件日最关键的数字缺席。
源（都是官方或官方镜像、免费、免注册）：
  主：BLS 公共 API v1（api.bls.gov，劳工统计局官方，发布即更新；无 key 每日 25 次，一次请求取全部序列）
  兜底：FRED CSV（圣路易斯联储，fredgraph.csv 免 key；通常发布后数分钟到一小时内更新）
预期值取 fed_speak.json 的 usd_high（FF 周历 forecast），与实际值并列，算超预期 / 不及预期。
序列：
  PAYEMS / CES0000000001  非农就业人数（千人，季调）→ 当月变化 = 本月 − 上月
  UNRATE / LNS14000000    失业率
  CES0500000003           平均时薪（环比 %）
  CPIAUCSL / CUSR0000SA0  CPI（季调，环比 %）；CUSR0000SA0L1E 核心 CPI
  PPIFIS / WPUFD4         PPI 最终需求（环比 %）
"""
import csv
import io
import json
import re
from datetime import datetime, timezone

import requests

H = {"User-Agent": "Mozilla/5.0 (options-research; macro actuals)", "Content-Type": "application/json"}
BLS = {"payrolls": "CES0000000001", "unrate": "LNS14000000", "ahe": "CES0500000003",
       "cpi": "CUSR0000SA0", "core_cpi": "CUSR0000SA0L1E", "ppi": "WPUFD4"}
FRED = {"payrolls": "PAYEMS", "unrate": "UNRATE", "ahe": "CES0500000003", "cpi": "CPIAUCSL", "core_cpi": "CPILFESL",
        "ppi": "PPIFIS"}
# FF 周历标题 → 指标（预期值对照）
FF_MAP = [(r"Non-Farm Employment Change", "payrolls"), (r"Unemployment Rate", "unrate"),
          (r"Average Hourly Earnings m/m", "ahe"), (r"^CPI m/m", "cpi"), (r"Core CPI m/m", "core_cpi"),
          (r"^PPI m/m", "ppi")]


def from_bls():
    y = datetime.now(timezone.utc).year
    r = requests.post("https://api.bls.gov/publicAPI/v1/timeseries/data/", headers=H, timeout=30,
                      data=json.dumps({"seriesid": list(BLS.values()), "startyear": str(y - 1), "endyear": str(y)}))
    r.raise_for_status()
    j = r.json()
    if j.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS {j.get('status')}: {j.get('message')}")
    out = {}
    inv = {v: k for k, v in BLS.items()}
    for s in j["Results"]["series"]:
        pts = [(f"{d['year']}-{d['period'][1:]}", float(d["value"])) for d in s["data"] if d["period"].startswith("M")
               and d["value"] not in ("-", "")]
        out[inv[s["seriesID"]]] = sorted(pts)
    return out


def from_fred():
    out = {}
    for k, sid in FRED.items():
        r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": sid}, headers=H, timeout=30)
        r.raise_for_status()
        rows = list(csv.reader(io.StringIO(r.text)))[1:]
        out[k] = [(d[:7], float(v)) for d, v in rows[-15:] if v not in (".", "")]
    return out


def summarize(series):
    """每个指标：最新月份、实际值（按市场口径：非农=人数变化千人、失业率=水平、其余=环比 %）、上月同口径。"""
    res = {}
    for k, pts in series.items():
        if len(pts) < 3:
            continue
        (m2, v2), (m1, v1), (m0, v0) = pts[-1], pts[-2], pts[-3]
        if k == "payrolls":
            act, prev = v2 - v1, v1 - v0
            unit = "千人"
        elif k == "unrate":
            act, prev = v2, v1
            unit = "%"
        else:
            act, prev = (v2 / v1 - 1) * 100, (v1 / v0 - 1) * 100
            unit = "% 环比"
        res[k] = {"month": m2, "actual": round(act, 2), "previous_recomputed": round(prev, 2), "unit": unit}
    return res


def parse_num(s):
    m = re.match(r"(-?[\d.]+)\s*([KkMm%]?)", s or "")
    if not m:
        return None
    v = float(m.group(1))
    return v  # K 单位与「千人」一致；% 原样


def main():
    out = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": None, "indicators": {},
           "errors": []}
    try:
        out["trigger"] = open("price_fetch_trigger.txt").read().strip()
    except OSError:
        out["trigger"] = None
    series = None
    for name, fn in (("BLS API", from_bls), ("FRED", from_fred)):
        try:
            series = fn()
            out["source"] = name
            break
        except Exception as e:  # 主源失败写明原因再走兜底，绝不静默
            out["errors"].append(f"{name}: {repr(e)[:200]}")
    if series:
        out["indicators"] = summarize(series)
    try:  # 预期值：FF 周历（fed_speak.json 的 usd_high）
        fs = json.load(open("fed_speak.json"))
        for e in fs.get("usd_high", []):
            for pat, k in FF_MAP:
                if re.search(pat, e["title"]) and k in out["indicators"]:
                    ind = out["indicators"][k]
                    ind.update({"release_et": e["time"], "forecast": e.get("forecast"), "ff_previous": e.get("previous")})
                    f = parse_num(e.get("forecast"))
                    if f is not None:
                        ind["surprise"] = round(ind["actual"] - f, 2)
    except OSError:
        out["errors"].append("fed_speak.json 不存在：无预期值对照")
    with open("macro_actuals.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"源 {out['source']}｜错误 {out['errors']}")
    for k, v in out["indicators"].items():
        print(f"  {k:9} {v['month']} 实际 {v['actual']}{v['unit']}  预期 {v.get('forecast', '—')}  上月 {v['previous_recomputed']}")


if __name__ == "__main__":
    main()
