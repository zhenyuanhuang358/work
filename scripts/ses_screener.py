"""
ses_screener.py — Phase 1: SES（规模反哺 / Scale Economies Shared）量化预筛

数据源: SEC EDGAR 官方 XBRL companyfacts API (data.sec.gov)
用途:   从候选池里筛出财务特征符合"规模反哺"模式的标的，进入 Phase 2 判别
        不产生买入信号，只产生"值得深挖"的候选名单

⚠ 运行环境: data.sec.gov 在会话容器的出口策略封禁名单内（CONNECT tunnel 403）。
   本脚本设计为在 GitHub Actions 中运行（出口不受限），产物写入 ses_screen.json。
   与 scripts/fetch_prices.py 同一套机制。

相对初版的三处修正（都会静默产生错误结果，不会报错）:
  1. 年度序列改用 start/end 期间识别，不再用 XBRL 的 fy 字段 —— fy 描述的是
     "这个数字出现在哪份报送里"，一份 10-K 里三年的比较数据 fy 全都相同，
     按 fy 去重会串年，CAGR 照样算得出来但是错的。
  2. 接受 20-F / 40-F —— 只筛 10-K 会让外国私人发行人静默返回"数据不足"。
  3. 判定函数接入营业利润率趋势 —— 毛利率下降本身不含信息（主动让利与被动侵蚀
     都会让它下降），只有配上"营业利润率有没有跟着塌"才有分辨力。
     初版计算了 sga_ratio_trend 却没接进判定，等于放弃了唯一的判别维度。
"""

import json
import os
import time
import urllib.request
from datetime import datetime, timezone, date

HEADERS = {"User-Agent": "Personal Research zhenyuanhuang358@gmail.com"}

# ---- 维护区: 候选池，人工加标的 ----
# 候选池是人工策展的，不是全市场扫描：SES 是一种管理层意图，
# 意图不在财务数据里，只能先由人从阅读中提出假设，再由筛选器证伪。
CANDIDATES = [
    "COST",  # 原型案例:会员费+低毛利,持续把规模节省让给客户
    "AMZN",  # Prime+履约网络。⚠ 合并口径毛利率因 AWS/广告占比上升而上行，本筛必然判灰 —— 见 F2
    "WMT",   # EDLP 规模反哺范例
    "MELI",  # 拉美电商+金融科技双轮
    "SE",    # Shopee。20-F 报送；资本周期尚在扩张期，重点核实是补贴还是成本优势
    "NU",    # Nu Holdings。20-F 报送；金融牌照型，监管风险需单独核实
    # "TICKER",  # 在此加新标的
]

WINDOW_YEARS = 5              # 所有趋势统一在这个窗口上计算
ACCEPTED_FORMS = {"10-K", "20-F", "40-F"}
CACHE_DIR = os.environ.get("SES_CACHE_DIR", ".ses_cache")

# 标签优先级：按顺序回退
TAGS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ],
    "gross_profit": ["GrossProfit"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfSales"],
    "sga": ["SellingGeneralAndAdministrativeExpense"],
    "operating_income": ["OperatingIncomeLoss"],
}

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_ticker_to_cik_cache = None


# --------------------------------------------------------------------------- 抓取

def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _load_ticker_map() -> dict:
    global _ticker_to_cik_cache
    if _ticker_to_cik_cache is None:
        raw = _get_json(_TICKER_MAP_URL)
        _ticker_to_cik_cache = {
            v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in raw.values()
        }
    return _ticker_to_cik_cache


def get_cik(ticker: str) -> str:
    cik = _load_ticker_map().get(ticker.upper())
    if not cik:
        raise ValueError(f"{ticker} 未在 SEC ticker 映射表里找到，需要手动查 CIK")
    return cik


def fetch_company_facts(cik: str) -> dict:
    """companyfacts 单个文件可达 10MB+，落盘缓存避免重复下载。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{cik}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    data = _get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return data


# --------------------------------------------------------------------------- 序列提取

def _annual_series(facts: dict, tag: str, taxonomy: str = "us-gaap"):
    """
    提取某科目的年度值序列，返回 [(end_date_str, val), ...] 按期末日排序。

    ⚠ 不使用 fy/fp 字段。fy 描述的是该 fact 出现在哪一份报送里，不是数据本身的会计年度：
      一份 FY2024 的 10-K 同时包含 2024/2023/2022 三年利润表，三条记录的 fy 全是 2024。
      按 fy 去重会让后写的覆盖先写的，静默串年。
    改为：按 start/end 的实际期间长度识别年度区间，按 end 去重，同一 end 取 filed 最新的修订。
    """
    try:
        units = facts["facts"][taxonomy][tag]["units"]
    except KeyError:
        return [], None

    unit = "USD" if "USD" in units else next(iter(units), None)
    if unit is None:
        return [], None

    seen = {}
    for v in units[unit]:
        if v.get("form") not in ACCEPTED_FORMS:
            continue
        start, end, filed = v.get("start"), v.get("end"), v.get("filed", "")
        if not start or not end:
            continue
        try:
            dur = (date.fromisoformat(end) - date.fromisoformat(start)).days
        except ValueError:
            continue
        if not (300 <= dur <= 400):      # 只要年度期间，排除季度与累计期
            continue
        prev = seen.get(end)
        if prev is None or filed > prev[1]:
            seen[end] = (v["val"], filed)

    return sorted((e, v[0]) for e, v in seen.items()), unit


def _first_available(facts: dict, keys: list):
    for tag in keys:
        s, unit = _annual_series(facts, tag)
        if len(s) >= 2:
            return s, tag, unit
    return [], None, None


# --------------------------------------------------------------------------- 信号计算

def compute_signals(cik: str) -> dict:
    facts = fetch_company_facts(cik)
    notes = []

    revenue, rev_tag, unit = _first_available(facts, TAGS["revenue"])
    if len(revenue) < 2:
        return {"error": "收入序列不足", "notes": notes}

    gross, gp_tag, _ = _first_available(facts, TAGS["gross_profit"])
    derived = False
    if len(gross) < 2:
        # 亚马逊等公司不单独 tag GrossProfit，必须走 收入 − 成本 的推导路径，
        # 否则会返回"数据不足"而漏检。
        cor, cor_tag, _ = _first_available(facts, TAGS["cost_of_revenue"])
        if len(cor) >= 2:
            rev_map = dict(revenue)
            gross = [(e, rev_map[e] - c) for e, c in cor if e in rev_map]
            derived = True
            notes.append(f"毛利由 收入 − {cor_tag} 推导")

    sga, _, _ = _first_available(facts, TAGS["sga"])
    opinc, _, _ = _first_available(facts, TAGS["operating_income"])

    # 窗口对齐：四个科目可得年数不同，必须先求交集再算所有趋势。
    # 用 5 年 CAGR 配 10 年毛利率变化，会得到没有意义的比较。
    rev_map, gp_map = dict(revenue), dict(gross)
    sga_map, op_map = dict(sga), dict(opinc)
    common = sorted(set(rev_map) & set(gp_map)) if gp_map else sorted(rev_map)
    if len(common) < 2:
        return {"error": "收入与毛利无重叠年度", "notes": notes}

    window = common[-(WINDOW_YEARS + 1):]
    lo, hi = window[0], window[-1]
    yrs = (date.fromisoformat(hi) - date.fromisoformat(lo)).days / 365.25
    if yrs < 1:
        return {"error": "窗口不足一年", "notes": notes}
    if len(window) < WINDOW_YEARS + 1:
        notes.append(f"窗口仅 {len(window)-1} 年（目标 {WINDOW_YEARS} 年）")

    def ratio(m):
        return [(e, m[e] / rev_map[e]) for e in window if e in m and rev_map.get(e)]

    gm, sga_r, opm = ratio(gp_map), ratio(sga_map), ratio(op_map)

    sig = {
        "window_start": lo, "window_end": hi, "window_years": round(yrs, 2),
        "revenue_tag": rev_tag, "unit": unit, "gross_profit_derived": derived,
        "notes": notes,
    }
    if rev_map[lo] > 0:
        sig["revenue_cagr"] = (rev_map[hi] / rev_map[lo]) ** (1 / yrs) - 1
    if len(gm) >= 2:
        sig["gm_trend"] = gm[-1][1] - gm[0][1]
        sig["gross_margin_series"] = [(e, round(v, 4)) for e, v in gm]
    if len(sga_r) >= 2:
        sig["sga_trend"] = sga_r[-1][1] - sga_r[0][1]
    else:
        notes.append("SG&A 序列不足，红灯判定降级")
    if len(opm) >= 2:
        sig["opm_trend"] = opm[-1][1] - opm[0][1]
        sig["operating_margin_series"] = [(e, round(v, 4)) for e, v in opm]
    else:
        notes.append("营业利润率序列不足 —— 核心判别器缺失，结果仅供参考")
    sig["revenue_series"] = [(e, rev_map[e]) for e in window]
    return sig


# --------------------------------------------------------------------------- 判定

def ses_flag(sig: dict) -> tuple:
    """
    分诊，不是打分公式。返回 (flag, 说明)。

    核心：毛利率下降本身不含信息 —— 主动让利与被动侵蚀都会让它下降。
    只有配上"营业利润率有没有跟着塌"才有分辨力：
      · 毛利让出去但经营利润稳住 → 成本侧的规模收益真实存在且被传导
      · 毛利与经营利润一起塌     → 根本没有规模收益，只是在被迫降价
    """
    if sig.get("error"):
        return "数据不足", sig["error"]
    cagr, gm = sig.get("revenue_cagr"), sig.get("gm_trend")
    opm, sga = sig.get("opm_trend"), sig.get("sga_trend")
    if cagr is None or gm is None:
        return "数据不足", "缺收入增速或毛利率趋势"
    if opm is None:
        return "数据不足", "缺营业利润率趋势 —— 核心判别器不可用，不出灯"

    if gm > 0:
        return "灰", "毛利率在扩张，没有反哺证据（不代表不是好生意，只是不是这个策略的画像）"
    if gm <= -0.03 and opm < -0.03 and (sga is None or sga >= 0):
        return "红", "毛利塌、经营利润塌、费用比率未降 —— 典型定价权丧失，不是反哺"
    if cagr >= 0.08 and opm >= -0.01:
        return "绿", "让利未伤及经营利润 —— 规模反哺嫌疑，进 Phase 2 核实是主动让利还是被动竞价"
    if cagr >= 0.08 and -0.03 <= opm < -0.01:
        return "黄", "经营利润率在滑，可能是投入期也可能是侵蚀早期 —— 必须进 Phase 2"
    return "灰", "特征不明显"


# --------------------------------------------------------------------------- 运行

def run_screen(candidates=None) -> dict:
    results = []
    for ticker in (candidates or CANDIDATES):
        try:
            cik = get_cik(ticker)
            sig = compute_signals(cik)
            flag, why = ses_flag(sig)
            results.append({"ticker": ticker, "cik": cik, "flag": flag,
                            "reason": why, "signals": sig})
        except Exception as e:
            results.append({"ticker": ticker, "flag": "抓取失败",
                            "reason": f"{type(e).__name__}: {e}", "signals": {}})
        time.sleep(0.15)   # SEC 限流礼貌等待

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "window_years": WINDOW_YEARS,
        "results": results,
    }

    def pct(x):
        return f"{x*100:+.1f}%" if isinstance(x, (int, float)) else "  --  "

    print(f"{'标的':<7}{'灯':<7}{'CAGR':>8}{'毛利Δ':>9}{'营利Δ':>9}{'SG&AΔ':>9}  说明")
    print("-" * 108)
    for r in results:
        s = r["signals"]
        print(f"{r['ticker']:<7}{r['flag']:<7}"
              f"{pct(s.get('revenue_cagr')):>8}{pct(s.get('gm_trend')):>9}"
              f"{pct(s.get('opm_trend')):>9}{pct(s.get('sga_trend')):>9}  {r['reason']}")
    print("\n⚠ 灯不是结论，是分诊。绿灯只意味着值得花时间做 Phase 2。")
    print("⚠ 混业公司（高毛利分部占比上升）本筛结果无效，须直接做分部级拆分。")
    return out


if __name__ == "__main__":
    data = run_screen()
    with open("ses_screen.json", "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n已写入 ses_screen.json ({len(data['results'])} 个标的)")
