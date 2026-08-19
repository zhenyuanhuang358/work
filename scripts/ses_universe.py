"""
ses_universe.py — Sleeper Phase 0: 全市场 SES 扫描

与 ses_screener.py 的区别：
  ses_screener.py  逐个公司拉 companyfacts（每个 10MB+）→ 只能跑人工候选池
  ses_universe.py  用 SEC frames API，一次拿全市场某科目某年的所有值
                   → 5 个科目 × N 年 = 几十个请求覆盖全部报送人

frames API: https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/CY{year}.json
  返回 {..., "data": [{"cik":..., "entityName":..., "start":..., "end":..., "val":...}, ...]}
  SEC 对每个报送实体挑选"最接近所请求日历期间"的那条事实，
  因此非日历财年公司（如 8 月结账的 COST）也会被纳入，只是期间近似。

⚠ 运行环境: data.sec.gov 在会话容器出口策略封禁名单内，本脚本在 GitHub Actions 跑。
"""

import json
import os
import time
import urllib.request
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Personal Research zhenyuanhuang358@gmail.com"}

YEARS = list(range(2019, 2026))          # CY2019..CY2025
MIN_REVENUE = 1_000_000_000              # 收入下限 10 亿美元，剔除微盘与壳
MIN_YEARS = 5                            # 至少 5 年可用序列
CACHE_DIR = os.environ.get("SES_FRAME_CACHE", ".ses_frames")

# 每个概念给一组候选标签，逐个取 frame 后按 CIK 合并（先到先得，不覆盖）
CONCEPTS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues", "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "gross_profit": ["GrossProfit"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "sga": ["SellingGeneralAndAdministrativeExpense"],
    "operating_income": ["OperatingIncomeLoss"],
}

# 判别器不适用的行业（见 references/failure-modes.md F9）。按 SIC 前两位剔除。
# 60-67 = 银行/保险/券商/地产投资；金融机构没有毛利率与营业利润率的常规口径。
EXCLUDED_SIC_PREFIX = {"60", "61", "62", "63", "64", "65", "67"}


def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def fetch_frame(tag, year, taxonomy="us-gaap", unit="USD"):
    """取一个 frame，落盘缓存。返回 {cik: (val, entityName)}。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{taxonomy}_{tag}_CY{year}.json")
    if os.path.exists(path):
        with open(path) as f:
            raw = json.load(f)
    else:
        url = f"https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/CY{year}.json"
        try:
            raw = _get(url)
        except Exception as e:
            print(f"    {tag} CY{year}: {type(e).__name__} {e}")
            raw = {"data": []}
        with open(path, "w") as f:
            json.dump(raw, f)
        time.sleep(0.15)                 # SEC 限流礼貌等待
    return {str(d["cik"]).zfill(10): (d["val"], d.get("entityName", ""))
            for d in raw.get("data", [])}


def build_universe():
    """返回 {cik: {"name":..., "revenue":{year:val}, "gross_profit":{...}, ...}}"""
    uni = {}
    for concept, tags in CONCEPTS.items():
        for year in YEARS:
            merged = {}
            for tag in tags:
                for cik, (val, name) in fetch_frame(tag, year).items():
                    merged.setdefault(cik, (val, name))   # 先到先得：标签按优先级排序
            print(f"  {concept:<17} CY{year}: {len(merged):>6} 家")
            for cik, (val, name) in merged.items():
                e = uni.setdefault(cik, {"name": name})
                e.setdefault(concept, {})[year] = val
                if name and not e.get("name"):
                    e["name"] = name
    return uni


def _series(d, years):
    return [(y, d[y]) for y in years if y in d]


def compute(entry):
    """在收入与毛利都可得的年份交集上计算全部趋势（窗口对齐）。"""
    rev = entry.get("revenue", {})
    gp = dict(entry.get("gross_profit", {}))
    notes = []

    # GrossProfit 缺失时由 收入 − 成本 推导（亚马逊等公司不单独 tag GrossProfit）
    if len(gp) < MIN_YEARS:
        cor = entry.get("cost_of_revenue", {})
        derived = {y: rev[y] - cor[y] for y in cor if y in rev}
        if len(derived) > len(gp):
            gp = derived
            notes.append("毛利由 收入−成本 推导")

    common = sorted(set(rev) & set(gp))
    if len(common) < MIN_YEARS:
        return None
    lo, hi = common[0], common[-1]
    n = hi - lo
    if n < 3 or rev[lo] <= 0 or rev[hi] < MIN_REVENUE:
        return None

    def ratio(m):
        s = [(y, m[y] / rev[y]) for y in common if y in m and rev.get(y)]
        return s if len(s) >= 2 else None

    gm = ratio(gp)
    opm = ratio(entry.get("operating_income", {}))
    sga = ratio(entry.get("sga", {}))
    if not gm or not opm:
        return None
    # 基期营业利润率必须为正：从负值或近零基数出发算百分点变化会炸成天文数字
    # （首跑实证：LCID 营利Δ +5360pct、ALNY +441pct，全部是这个成因）
    if opm[0][1] <= 0.01:
        return None

    return {
        "window": f"{lo}-{hi}", "years": n,
        "revenue_latest": rev[hi],
        "revenue_cagr": (rev[hi] / rev[lo]) ** (1 / n) - 1,
        "gm_trend": gm[-1][1] - gm[0][1],
        "gm_latest": gm[-1][1],
        "opm_trend": opm[-1][1] - opm[0][1],
        "opm_latest": opm[-1][1],
        "sga_trend": (sga[-1][1] - sga[0][1]) if sga else None,
        "gm_series": [round(v, 4) for _, v in gm],
        "opm_series": [round(v, 4) for _, v in opm],
        "notes": notes,
    }


# SES 是"薄毛利、高周转"的现象：机制是规模压低单位成本→让价→上量→更大规模，
# 这要求 COGS 是主要成本项。毛利率 80-98% 的生物医药/软件公司成本结构由 R&D 与
# S&M 主导，其规模收益体现在费用杠杆而非毛利率，本判别器对它们不适用。
GM_CEILING = 0.50      # 高于此：非 COGS 主导，换赛道
GM_FLOOR = 0.02        # 低于此：多为总额法计收入的标记口径问题
OPM_TREND_CEILING = 0.03   # SES 要求营业利润率稳定，不是扭亏反转
GM_TREND_FLOOR = -0.08     # 低于此是毛利崩塌，不是让利


def flag(s):
    """与 ses_screener.ses_flag 同一套判别器，口径必须保持一致。"""
    cagr, gm, opm, sga = (s["revenue_cagr"], s["gm_trend"],
                          s["opm_trend"], s["sga_trend"])
    gml = s["gm_latest"]
    if not (GM_FLOOR < gml < GM_CEILING):
        return "赛道外"     # 非 COGS 主导，或毛利率读数不可信
    if opm > OPM_TREND_CEILING:
        return "灰"         # 营业利润率大幅扩张 = 扭亏或收割，不是让利
    if gm < GM_TREND_FLOOR:
        return "红"         # 毛利崩塌
    if gm > 0:
        return "灰"
    if gm <= -0.03 and opm < -0.03 and (sga is None or sga >= 0):
        return "红"
    if cagr >= 0.08 and opm >= -0.01:
        return "绿"
    if cagr >= 0.08 and -0.03 <= opm < -0.01:
        return "黄"
    return "灰"


def load_ticker_map():
    """CIK -> ticker。company_tickers.json 只含有上市代码的实体，正好当作上市过滤器。"""
    raw = _get("https://www.sec.gov/files/company_tickers.json")
    m = {}
    for v in raw.values():
        m.setdefault(str(v["cik_str"]).zfill(10), v["ticker"].upper())
    return m


def main():
    print("拉取 frames …")
    uni = build_universe()
    print(f"\n全市场实体（至少命中一个科目）: {len(uni):,}")

    tick = load_ticker_map()
    rows = []
    for cik, e in uni.items():
        t = tick.get(cik)
        if not t:                        # 无上市代码 → 非公开交易，跳过
            continue
        s = compute(e)
        if not s:
            continue
        s.update(cik=cik, ticker=t, name=e.get("name", ""), flag=flag(s))
        rows.append(s)

    print(f"通过口径与规模门槛（收入≥10亿、序列≥{MIN_YEARS}年）: {len(rows):,}")
    from collections import Counter
    print("分布:", dict(Counter(r["flag"] for r in rows)))

    # 绿灯内部排序：SG&A 比率降幅越大 → 规模带来的经营杠杆越确凿；其次看增速
    # 排序按增速降序：飞轮还在转的排前面。不做加权打分（判别器不是评分公式）。
    green = sorted([r for r in rows if r["flag"] == "绿"],
                   key=lambda r: -r["revenue_cagr"])
    yellow = sorted([r for r in rows if r["flag"] == "黄"],
                    key=lambda r: -r["revenue_cagr"])

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "years": YEARS, "min_revenue": MIN_REVENUE,
        "universe_size": len(uni), "screened": len(rows),
        "distribution": dict(Counter(r["flag"] for r in rows)),
        "green": green, "yellow": yellow[:60],
    }
    with open("ses_universe.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"\n{'代码':<7}{'CAGR':>7}{'毛利Δ':>8}{'营利Δ':>8}{'SG&AΔ':>8}{'毛利率':>8}  {'窗口':<10}公司")
    print("-" * 112)
    for r in green[:40]:
        sg = f"{r['sga_trend']*100:+.1f}" if r["sga_trend"] is not None else "  --"
        print(f"{r['ticker']:<7}{r['revenue_cagr']*100:>6.1f}%{r['gm_trend']*100:>7.1f}"
              f"{r['opm_trend']*100:>8.1f}{sg:>8}{r['gm_latest']*100:>7.1f}%  "
              f"{r['window']:<10}{r['name'][:34]}")
    print(f"\n绿灯 {len(green)} 家 / 黄灯 {len(yellow)} 家。已写入 ses_universe.json")
    print("⚠ 灯不是结论，是分诊。绿灯只意味着值得进 Phase 2。")


if __name__ == "__main__":
    main()
