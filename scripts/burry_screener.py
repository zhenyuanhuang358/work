"""
burry_screener.py — Burry Layer 1 独立选股器 + Tier 1 边界发现

两个独立任务，一次运行都做：
  A. Tier 边界发现：查 EDGAR submissions，找出最新 13F-HR 期间 -> burry_state.json
     ⚠ 边界必须发现，不得写死。13F 义务由持仓规模触发，不由投顾注册状态决定，
       注销 ≠ 义务终止。写成常量会在恢复报送时静默失效。
  B. 全市场扫描（两段式）-> burry_screen.json
     Stage A 纯 EDGAR，零价格请求，把全市场压到数百家
     Stage B 只对幸存者取价格，算 EV/EBITDA、P/B、FCF yield，按分位数排序

⚠ 运行环境：data.sec.gov / www.sec.gov 在会话容器出口策略封禁名单内
  （CONNECT tunnel failed, 403）。本脚本在 GitHub Actions 跑。

阈值一律用分位数，不用固定倍数——2000 年的 6 倍 EV/EBITDA 和 2026 年的不是一回事。
"""

import json
import os
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Personal Research zhenyuanhuang358@gmail.com"}

YEAR = int(os.environ.get("BURRY_YEAR", "2025"))     # 扫描基准年（最近完整财年）
CACHE_DIR = os.environ.get("BURRY_FRAME_CACHE", ".burry_frames")
MAX_STAGE_B = int(os.environ.get("BURRY_MAX_STAGE_B", "800"))
FINNHUB_TOKEN = os.environ.get("FINNHUB_TOKEN", "")

STATE_FILE = "burry_state.json"
SCREEN_FILE = "burry_screen.json"

# Stage A 分位门槛（越小越严）
Q_NETDEBT_MAX = 0.60      # 净负债/EBITDA 低于 60% 分位
Q_SBC_MAX = 0.50          # SBC/营收 低于中位数

# Stage B 分位门槛
Q_EV_EBITDA = 0.10        # EV/EBITDA 最低 10% 分位
Q_PB = 0.15               # P/B 最低 15% 分位
Q_FCF_YIELD = 0.85        # FCF yield 最高 15% 分位（即 85% 分位以上）

# 每个概念给一组候选标签，逐个取 frame 后按 CIK 合并（先到先得）
CONCEPTS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues", "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "operating_income": ["OperatingIncomeLoss"],
    "dep_amort": ["DepreciationDepletionAndAmortization",
                  "DepreciationAmortizationAndAccretionNet", "DepreciationAndAmortization"],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
}
# 时点科目（frames 需 I 后缀）
CONCEPTS_INSTANT = {
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments"],
    "debt_lt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "debt_st": ["LongTermDebtCurrent", "ShortTermBorrowings"],
    "equity": ["StockholdersEquity",
               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "shares": ["EntityCommonStockSharesOutstanding"],   # dei 分类，见 fetch_frame
}

# ⚠ 已知缺口：frames API 不返回 SIC，本脚本无法按行业剔除金融机构。
# 银行/保险/券商没有 EV/EBITDA 与净负债的常规口径，其数值会失真。
# 不静默剔除（会让范围被动收窄），改为在输出 warnings 里提示人工复核。


def _get(url, timeout=120):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ────────────────────────── A. Tier 边界发现 ──────────────────────────

def discover_cik(name_query="scion asset management"):
    """按实体名查 CIK。不硬编码——写错的 CIK 不会自己暴露，后续全部归因都会建立在错主体上。"""
    url = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
           f"&company={urllib.parse.quote(name_query)}&type=13F&dateb=&owner=include"
           "&count=40&output=atom")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"  CIK 查询失败: {type(e).__name__} {e}")
        return None, []
    import re
    hits = []
    for m in re.finditer(r"<CIK>(\d+)</CIK>", text):
        hits.append(m.group(1).zfill(10))
    for m in re.finditer(r"CIK=(\d{10})", text):
        hits.append(m.group(1))
    uniq = sorted(set(hits))
    return (uniq[0] if uniq else None), uniq


def discover_tier1_boundary(cik):
    """查 submissions，返回最新 13F-HR 的 reportDate/filingDate/accession。"""
    if not cik:
        return None
    try:
        d = _get(f"https://data.sec.gov/submissions/CIK{cik}.json", timeout=60)
    except Exception as e:
        print(f"  submissions 拉取失败: {type(e).__name__} {e}")
        return None
    recent = d.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    rows = []
    for i, f in enumerate(forms):
        if f in ("13F-HR", "13F-HR/A"):
            rows.append({
                "form": f,
                "report_date": recent.get("reportDate", [None] * len(forms))[i],
                "filing_date": recent.get("filingDate", [None] * len(forms))[i],
                "accession": recent.get("accessionNumber", [None] * len(forms))[i],
            })
    if not rows:
        return {"entity_name": d.get("name"), "filings_found": 0, "latest": None, "all": []}
    rows.sort(key=lambda r: (r["report_date"] or ""), reverse=True)
    return {"entity_name": d.get("name"), "filings_found": len(rows),
            "latest": rows[0], "all": rows[:12]}


# ────────────────────────── B. 全市场扫描 ──────────────────────────

def fetch_frame(tag, year, taxonomy="us-gaap", unit="USD", instant=False):
    os.makedirs(CACHE_DIR, exist_ok=True)
    period = f"CY{year}Q4I" if instant else f"CY{year}"
    path = os.path.join(CACHE_DIR, f"{taxonomy}_{tag}_{period}.json")
    if os.path.exists(path):
        with open(path) as f:
            raw = json.load(f)
    else:
        url = f"https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json"
        try:
            raw = _get(url)
        except Exception as e:
            print(f"    {tag} {period}: {type(e).__name__} {e}")
            raw = {"data": []}
        with open(path, "w") as f:
            json.dump(raw, f)
        time.sleep(0.15)
    return {str(d["cik"]).zfill(10): (d["val"], d.get("entityName", ""))
            for d in raw.get("data", [])}


def fetch_ticker_map():
    """SEC 官方 CIK->ticker 映射。frames 只给 CIK，没有 ticker，
    不补这一步 Stage B 取价会全部落空。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, "company_tickers.json")
    if os.path.exists(path):
        with open(path) as f:
            raw = json.load(f)
    else:
        try:
            raw = _get("https://www.sec.gov/files/company_tickers.json", timeout=60)
        except Exception as e:
            print(f"  ticker 映射拉取失败: {type(e).__name__} {e}")
            return {}
        with open(path, "w") as f:
            json.dump(raw, f)
    m = {}
    for v in raw.values():
        m.setdefault(str(v["cik_str"]).zfill(10), v["ticker"])
    return m


def build_universe():
    uni = {}
    for concept, tags in CONCEPTS.items():
        merged = {}
        for tag in tags:
            for cik, (val, name) in fetch_frame(tag, YEAR).items():
                merged.setdefault(cik, (val, name))
        print(f"  {concept:<18} CY{YEAR}:  {len(merged):>6} 家")
        for cik, (val, name) in merged.items():
            e = uni.setdefault(cik, {"name": name})
            e[concept] = val
            if name and not e.get("name"):
                e["name"] = name
    for concept, tags in CONCEPTS_INSTANT.items():
        merged = {}
        for tag in tags:
            tax, unit = ("dei", "shares") if concept == "shares" else ("us-gaap", "USD")
            for cik, (val, name) in fetch_frame(tag, YEAR, taxonomy=tax, unit=unit,
                                                instant=True).items():
                merged.setdefault(cik, (val, name))
        print(f"  {concept:<18} CY{YEAR}Q4I: {len(merged):>6} 家")
        for cik, (val, name) in merged.items():
            e = uni.setdefault(cik, {"name": name})
            e[concept] = val
            if name and not e.get("name"):
                e["name"] = name
    return uni


REQUIRED = ["revenue", "operating_income", "dep_amort", "equity", "shares"]


def stage_a(uni, tickers):
    """纯 EDGAR，零价格请求。返回 (完整样本, 不完整样本)。"""
    full, incomplete = [], []
    for cik, e in uni.items():
        missing = [k for k in REQUIRED if e.get(k) is None]
        rec = {"cik": cik, "name": e.get("name", ""),
               "ticker": tickers.get(cik), "missing": missing}
        if missing:
            incomplete.append(rec)
            continue
        rev = e["revenue"]
        ebitda = e["operating_income"] + e["dep_amort"]
        if rev <= 0 or ebitda <= 0 or e["equity"] <= 0 or e["shares"] <= 0:
            rec["missing"] = ["非正数值：rev/ebitda/equity/shares"]
            incomplete.append(rec)
            continue
        net_debt = (e.get("debt_lt") or 0) + (e.get("debt_st") or 0) - (e.get("cash") or 0)
        fcf = (e.get("cfo") or 0) - (e.get("capex") or 0)
        rec.update({
            "revenue": rev, "ebitda": ebitda, "equity": e["equity"], "shares": e["shares"],
            "net_debt": net_debt, "fcf": fcf,
            "net_debt_ebitda": net_debt / ebitda,
            "sbc_ratio": (e["sbc"] / rev) if e.get("sbc") else None,
        })
        full.append(rec)
    return full, incomplete


def pct_threshold(values, q):
    """分位阈值。⚠ 只在完整样本内计算——缺数据者系统性偏小盘偏便宜，
    把它们排除会抬高「便宜」的门槛。故不完整组单列，不参与计算也不剔除。"""
    vs = sorted(v for v in values if v is not None)
    if not vs:
        return None
    i = min(int(q * (len(vs) - 1)), len(vs) - 1)
    return vs[i]


def rank_pct(values, v):
    vs = sorted(x for x in values if x is not None)
    if not vs or v is None:
        return None
    return sum(1 for x in vs if x <= v) / len(vs)


def fetch_price(sym):
    if not FINNHUB_TOKEN:
        return None
    try:
        d = _get(f"https://finnhub.io/api/v1/quote?symbol={sym}&token={FINNHUB_TOKEN}", timeout=15)
        c = d.get("c")
        return c if c and c > 0 else None
    except Exception:
        return None


def main():
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # ── A. Tier 边界发现 ──
    print("== A. Tier 1 边界发现 ==")
    cik, all_hits = discover_cik()
    print(f"  CIK 候选: {all_hits or '（无）'}")
    boundary = discover_tier1_boundary(cik) if cik else None
    prev = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                prev = json.load(f)
        except Exception:
            prev = {}
    prev_rd = ((prev.get("tier1") or {}).get("latest") or {}).get("report_date")
    new_rd = ((boundary or {}).get("latest") or {}).get("report_date")
    moved = bool(new_rd and prev_rd and new_rd > prev_rd)
    if boundary and boundary.get("latest"):
        print(f"  最新 13F-HR 期间: {new_rd}（备案 {boundary['latest']['filing_date']}）"
              f"{'  ⚠ 边界前移，需回溯修订已出报告' if moved else ''}")
    else:
        print("  未取得 13F-HR 记录 — Tier 1 边界置为 unknown，不得推断为「已终结」")
    state = {
        "updated_at": now, "cik": cik, "cik_candidates": all_hits,
        "tier1": boundary, "boundary_moved_since_last_run": moved,
        "note": "Tier 1 边界由 EDGAR 发现，不写死。13F 义务由持仓规模触发，非投顾注册状态。",
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    # ── B. 全市场扫描 ──
    print(f"\n== B. 全市场扫描 CY{YEAR} ==")
    uni = build_universe()
    print(f"  合并后报送人: {len(uni)}")
    tickers = fetch_ticker_map()
    print(f"  CIK->ticker 映射: {len(tickers)} 条")
    full, incomplete = stage_a(uni, tickers)
    inc_ratio = len(incomplete) / max(len(uni), 1)
    print(f"  完整样本 {len(full)} / 不完整 {len(incomplete)}（{inc_ratio*100:.1f}%）")
    warn = []
    warn.append("frames 不返回 SIC，本次未按行业剔除金融机构；"
                "银行/保险/券商的 EV/EBITDA 与净负债/EBITDA 会失真，须人工复核。")
    if inc_ratio > 0.30:
        warn.append(f"不完整样本占比 {inc_ratio*100:.1f}% > 30%，分位数阈值代表性存疑")

    nd_vals = [r["net_debt_ebitda"] for r in full]
    sbc_vals = [r["sbc_ratio"] for r in full if r["sbc_ratio"] is not None]
    nd_cut = pct_threshold(nd_vals, Q_NETDEBT_MAX)
    sbc_cut = pct_threshold(sbc_vals, Q_SBC_MAX)
    survivors = [r for r in full
                 if r["net_debt_ebitda"] <= nd_cut
                 and (r["sbc_ratio"] is None or r["sbc_ratio"] <= sbc_cut)]
    print(f"  Stage A 幸存: {len(survivors)}（净负债/EBITDA ≤ {nd_cut:.2f}, SBC/营收 ≤ "
          f"{sbc_cut:.4f}）" if sbc_cut is not None else f"  Stage A 幸存: {len(survivors)}")
    if len(survivors) > MAX_STAGE_B:
        warn.append(f"Stage A 幸存 {len(survivors)} > {MAX_STAGE_B}：应收紧 Stage A 门槛，"
                    f"而不是加大取价量。本次按净负债/EBITDA 升序截断。")
        survivors.sort(key=lambda r: r["net_debt_ebitda"])
        survivors = survivors[:MAX_STAGE_B]

    # Stage B：只对幸存者取价格
    priced = []
    if FINNHUB_TOKEN:
        print(f"  Stage B 取价 {len(survivors)} 家 …")
        no_ticker = sum(1 for r in survivors if not r.get("ticker"))
        if no_ticker:
            warn.append(f"Stage A 幸存者中 {no_ticker} 家无 ticker 映射，无法取价，"
                        f"已并入不完整组而非静默丢弃。")
        for i, r in enumerate(survivors):
            sym = r.get("ticker")
            p = fetch_price(sym) if sym else None
            if not p:
                incomplete.append({"cik": r["cik"], "name": r["name"],
                                   "ticker": sym, "missing": ["price"]})
            if p:
                r["price"] = p
                r["mktcap"] = p * r["shares"]
                r["ev"] = r["mktcap"] + r["net_debt"]
                r["ev_ebitda"] = r["ev"] / r["ebitda"] if r["ebitda"] else None
                r["pb"] = r["mktcap"] / r["equity"] if r["equity"] else None
                r["fcf_yield"] = r["fcf"] / r["ev"] if r["ev"] else None
                priced.append(r)
            if i % 55 == 54:
                time.sleep(60)     # Finnhub 免费档 60 req/min
    else:
        warn.append("未配置 FINNHUB_TOKEN：Stage B 未运行，仅产出 Stage A 结果。"
                    "EV/EBITDA、P/B、FCF yield 全部缺失。")

    results = []
    if priced:
        ev_vals = [r["ev_ebitda"] for r in priced]
        pb_vals = [r["pb"] for r in priced]
        fy_vals = [r["fcf_yield"] for r in priced]
        cuts = {"ev_ebitda": pct_threshold(ev_vals, Q_EV_EBITDA),
                "pb": pct_threshold(pb_vals, Q_PB),
                "fcf_yield": pct_threshold(fy_vals, Q_FCF_YIELD)}
        for r in priced:
            passed = []
            if r["ev_ebitda"] is not None and r["ev_ebitda"] <= cuts["ev_ebitda"]:
                passed.append("EV/EBITDA")
            if r["pb"] is not None and r["pb"] <= cuts["pb"]:
                passed.append("P/B")
            if r["fcf_yield"] is not None and r["fcf_yield"] >= cuts["fcf_yield"]:
                passed.append("FCF yield")
            passed.append("净负债/EBITDA")
            if r["sbc_ratio"] is not None and sbc_cut is not None and r["sbc_ratio"] <= sbc_cut:
                passed.append("SBC 稀释")
            r["passed"] = passed
            r["pct"] = {"ev_ebitda": rank_pct(ev_vals, r["ev_ebitda"]),
                        "pb": rank_pct(pb_vals, r["pb"]),
                        "fcf_yield": rank_pct(fy_vals, r["fcf_yield"])}
            results.append(r)
        # 先硬过滤，不加权打分——没验证过筛选力度就引入权重 = 把主观判断伪装成算法
        results.sort(key=lambda r: (-len(r["passed"]), r["ev_ebitda"] or 9e9))

    out = {
        "updated_at": now,
        "year": YEAR,
        "source_boundary": new_rd,
        "coverage_note": ("EDGAR 仅覆盖向 SEC 报送的主体，扫描范围为美股。"
                          "伯里本人选股不限国别（历史上做过波兰、英国、墨西哥小盘股）。"
                          "本扫描器范围小于其真实选股范围——这是数据源的收窄，不是选股标准的收窄。"),
        "sample": {"universe": len(uni), "complete": len(full),
                   "incomplete": len(incomplete), "incomplete_ratio": round(inc_ratio, 4),
                   "stage_a_survivors": len(survivors), "stage_b_priced": len(priced)},
        "thresholds": {"net_debt_ebitda_cut": nd_cut, "sbc_ratio_cut": sbc_cut,
                       "quantiles": {"net_debt": Q_NETDEBT_MAX, "sbc": Q_SBC_MAX,
                                     "ev_ebitda": Q_EV_EBITDA, "pb": Q_PB,
                                     "fcf_yield": Q_FCF_YIELD}},
        "warnings": warn,
        "results": results[:200],
        # 不完整样本单列保留：既不参与分位数计算，也不剔除
        "incomplete_sample": incomplete[:200],
    }
    with open(SCREEN_FILE, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n  写出 {SCREEN_FILE}：结果 {len(results)} 家，不完整 {len(incomplete)} 家")
    for w in warn:
        print(f"  ⚠ {w}")


if __name__ == "__main__":
    main()
