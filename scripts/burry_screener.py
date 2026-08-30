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
    "operating_income": ["OperatingIncomeLoss",
                         "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],
    "dep_amort": ["DepreciationDepletionAndAmortization",
                  "DepreciationAmortizationAndAccretionNet", "DepreciationAndAmortization",
                  "DepreciationDepletionAndAmortizationExcludingAmortizationOfDeferredCharges"],
    # 上面整合标签取不到时，用这两项相加兜底（Abbott / AMD 等分开报）
    "depreciation_only": ["Depreciation", "DepreciationNonproduction"],
    "amortization_only": ["AmortizationOfIntangibleAssets", "AmortizationOfDeferredCharges"],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
}
# 时点科目按此顺序回退，每个 CIK 取第一个命中的。
# 只查 CY2025Q4I 会漏掉全部非 12 月结账公司（实测 shares 缺失率 62%）。
# 对 shares/equity 这类存量科目，取"最近可得"本就比"强行对齐某一期"更合理。
INSTANT_PERIODS = ["CY2026Q2I", "CY2026Q1I", "CY2025Q4I", "CY2025Q3I", "CY2025Q2I"]

# 时点科目（frames 需 I 后缀）
CONCEPTS_INSTANT = {
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments"],
    "debt_lt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "debt_st": ["LongTermDebtCurrent", "ShortTermBorrowings"],
    "equity": ["StockholdersEquity",
               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    # shares 是首要缺失瓶颈（首跑缺 62%，5 期回退后仍占缺失样本 67%）。
    # dei 覆盖不足时用 us-gaap 的股数科目补——两个分类都试，先到先得。
    "shares": ["EntityCommonStockSharesOutstanding"],          # dei
    "shares_gaap": ["CommonStockSharesOutstanding", "CommonStockSharesIssued"],  # us-gaap
}

# frames 不返回 SIC，逐家查 submissions 要 7000+ 请求。
# 改用「标签指纹」：只有金融机构才会报这些科目，命中即判为金融。
# 银行/保险/券商没有 EV/EBITDA 与净负债的常规口径，其数值必然失真，必须排除。
FINANCIAL_FINGERPRINT = [
    "PolicyholderBenefitsAndClaimsIncurredNet",   # 保险：赔付
    "LiabilityForClaimsAndClaimsAdjustmentExpense",
    "InterestAndDividendIncomeOperating",          # 银行：利息收入
    "Deposits",                                    # 银行：存款
    "ProvisionForLoanAndLeaseLosses",
]

MIN_MKTCAP = float(os.environ.get("BURRY_MIN_MKTCAP", "50e6"))   # 市值下限，滤壳

# ⭐ 回撤维度（2026-08-30 加）。Burry 校验实测：筛选器 ∩ 他实际持仓 = 6/172。
# 根因是「便宜」有两种——筛选器找「一直便宜」（DXC/Kohl's/Macy's 常年低估值），
# 他买「刚变便宜」（MOLINA/UNH/雅诗兰黛/LULU 从高位崩下来）。
# 静态估值分位数区分不了价值陷阱与叙事破裂，缺的就是这一刀。
#
# ⚠ 阈值按经济逻辑预登记，不按重合度拟合（F10）：
#   20% 回撤是常规波动；40% 意味着估值倍数被结构性砍掉一半左右 = 叙事破裂。
#   **加完只跑一次校验，不反复调。反复调就是后见之明拟合。**
DRAWDOWN_MIN = float(os.environ.get("BURRY_DRAWDOWN_MIN", "0.40"))   # 距 3 年高点


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
    # 保留全部备案：13F 抓取需要完整历史，截断会让归因只能看最近三年
    return {"entity_name": d.get("name"), "filings_found": len(rows),
            "latest": rows[0], "all": rows}


# ────────────────────────── B. 全市场扫描 ──────────────────────────

def fetch_frame(tag, year, taxonomy="us-gaap", unit="USD", instant=False, period=None):
    os.makedirs(CACHE_DIR, exist_ok=True)
    if period is None:
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


def fetch_financial_ciks():
    """标签指纹法：命中任一金融专属科目即判为金融机构。"""
    fin = set()
    for tag in FINANCIAL_FINGERPRINT:
        got = fetch_frame(tag, YEAR)
        if not got:
            for period in INSTANT_PERIODS[:3]:
                got = fetch_frame(tag, YEAR, period=period)
                if got:
                    break
        fin |= set(got.keys())
        print(f"  金融指纹 {tag:<45} 累计 {len(fin)}")
    return fin


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
        tax, unit = ("dei", "shares") if concept == "shares" else ("us-gaap", "USD")
        # 期间从新到旧回退，先到先得：拿到的是每家"最近可得"的时点值
        for period in INSTANT_PERIODS:
            for tag in tags:
                for cik, (val, name) in fetch_frame(tag, YEAR, taxonomy=tax, unit=unit,
                                                    period=period).items():
                    merged.setdefault(cik, (val, name))
        print(f"  {concept:<18} {len(INSTANT_PERIODS)}期回退: {len(merged):>6} 家")
        for cik, (val, name) in merged.items():
            e = uni.setdefault(cik, {"name": name})
            e[concept] = val
            if name and not e.get("name"):
                e["name"] = name
    return uni


# dep_amort 不列入 REQUIRED：允许由 depreciation_only + amortization_only 兜底推导
REQUIRED = ["revenue", "operating_income", "equity", "shares"]


def stage_a(uni, tickers, fin_ciks):
    """纯 EDGAR，零价格请求。返回 (完整, 数据缺失, 不适用)。
    ⚠ 「数据缺失」与「不适用」必须分开：前者说明抓数管道有洞、影响分位数代表性；
    后者（EBITDA≤0、金融股）是指标本身无定义，被正确排除，不构成覆盖率问题。"""
    full, missing_data, not_applicable = [], [], []
    for cik, e in uni.items():
        if e.get("shares") is None and e.get("shares_gaap") is not None:
            e["shares"] = e["shares_gaap"]
            e["shares_from_gaap"] = True
        missing = [k for k in REQUIRED if e.get(k) is None]
        rec = {"cik": cik, "name": e.get("name", ""),
               "ticker": tickers.get(cik), "missing": missing,
               "shares_from_gaap": bool(e.get("shares_from_gaap"))}
        if cik in fin_ciks:
            rec["reason"] = "金融机构（标签指纹命中）"
            not_applicable.append(rec)
            continue
        if missing:
            missing_data.append(rec)
            continue
        rev = e["revenue"]
        da = e.get("dep_amort")
        if da is None:
            dep, amo = e.get("depreciation_only"), e.get("amortization_only")
            if dep is not None or amo is not None:
                da = (dep or 0) + (amo or 0)
                rec["da_derived"] = True
        if da is None:
            rec["missing"] = ["dep_amort（含分项兜底后仍缺）"]
            missing_data.append(rec)
            continue
        rec["dep_amort"] = da
        ebitda = e["operating_income"] + da
        if rev <= 0 or ebitda <= 0 or e["equity"] <= 0 or e["shares"] <= 0:
            rec["reason"] = "指标无定义：EBITDA/净资产/收入非正"
            not_applicable.append(rec)
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
    return full, missing_data, not_applicable


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


def fetch_history_batch(syms):
    """批量取 3 年日线，算 52 周与 3 年高点。yfinance 批量下载，
    比逐支 REST 请求快一个数量级，且不受 Finnhub 每分钟 60 次限制。"""
    try:
        import yfinance as yf
    except ImportError:
        print("  yfinance 不可用，回撤维度跳过")
        return {}
    out = {}
    B = 150
    for i in range(0, len(syms), B):
        chunk = syms[i:i + B]
        try:
            df = yf.download(" ".join(chunk), period="3y", interval="1d",
                             group_by="ticker", auto_adjust=True,
                             progress=False, threads=True)
        except Exception as e:
            print(f"  批次 {i//B+1} 下载失败: {type(e).__name__}")
            continue
        for sym in chunk:
            try:
                c = (df[sym]["Close"] if len(chunk) > 1 else df["Close"]).dropna()
                if len(c) < 60:          # 上市不足 3 个月，回撤无意义
                    continue
                px = float(c.iloc[-1])
                hi3 = float(c.max())
                hi52 = float(c.iloc[-252:].max()) if len(c) >= 60 else hi3
                out[sym] = {"px_hist": px, "high_3y": hi3, "high_52w": hi52,
                            "dd_3y": 1 - px / hi3 if hi3 > 0 else None,
                            "dd_52w": 1 - px / hi52 if hi52 > 0 else None,
                            "bars": len(c)}
            except Exception:
                continue
        print(f"  历史行情 {min(i+B,len(syms))}/{len(syms)}  已取到 {len(out)}")
        time.sleep(1)
    return out


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
    fin_ciks = fetch_financial_ciks()
    full, missing_data, not_applicable = stage_a(uni, tickers, fin_ciks)
    # 分位数代表性只受「数据缺失」影响；「不适用」是被正确排除的
    denom = len(full) + len(missing_data)
    miss_ratio = len(missing_data) / max(denom, 1)
    print(f"  完整 {len(full)} / 数据缺失 {len(missing_data)} / 不适用 {len(not_applicable)}")
    print(f"  真实缺失率 = 缺失/(完整+缺失) = {miss_ratio*100:.1f}%")
    warn = []
    if miss_ratio > 0.30:
        warn.append(f"数据缺失率 {miss_ratio*100:.1f}% > 30%，分位数阈值代表性存疑")

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
        no_ticker = sum(1 for r in survivors if not r.get("ticker"))  # noqa
        if no_ticker:
            warn.append(f"Stage A 幸存者中 {no_ticker} 家无 ticker 映射，无法取价，"
                        f"已并入不完整组而非静默丢弃。")
        for i, r in enumerate(survivors):
            sym = r.get("ticker")
            p = fetch_price(sym) if sym else None
            if not p:
                missing_data.append({"cik": r["cik"], "name": r["name"],
                                     "ticker": sym, "missing": ["price"]})
            if p:
                r["price"] = p
                r["mktcap"] = p * r["shares"]
                r["ev"] = r["mktcap"] + r["net_debt"]
                if r["mktcap"] < MIN_MKTCAP:
                    r["reason"] = f"市值 {r['mktcap']/1e6:.1f}M < 下限 {MIN_MKTCAP/1e6:.0f}M"
                    not_applicable.append(r); continue
                # ⚠ EV≤0（净现金超过市值）时 EV/EBITDA 与 FCF yield 无经济含义，
                #   升序排序会把它们顶到最前面，制造「最便宜」的假象。必须排除。
                if r["ev"] <= 0:
                    r["reason"] = f"EV = {r['ev']/1e6:.1f}M ≤ 0，EV 类指标无定义"
                    not_applicable.append(r); continue
                r["ev_ebitda"] = r["ev"] / r["ebitda"]
                r["pb"] = r["mktcap"] / r["equity"]
                r["fcf_yield"] = r["fcf"] / r["ev"]
                priced.append(r)
            if i % 55 == 54:
                time.sleep(60)     # Finnhub 免费档 60 req/min
    else:
        warn.append("未配置 FINNHUB_TOKEN：Stage B 未运行，仅产出 Stage A 结果。"
                    "EV/EBITDA、P/B、FCF yield 全部缺失。")

    # ⭐ 回撤维度：只对已定价的幸存者取历史，成本可控
    if priced:
        print(f"  取 3 年历史行情（{len(priced)} 支）…")
        hist = fetch_history_batch([r["ticker"] for r in priced if r.get("ticker")])
        n_dd = 0
        for r in priced:
            hh = hist.get(r.get("ticker"))
            if hh:
                r.update({k: hh[k] for k in ("high_3y", "high_52w", "dd_3y", "dd_52w")})
                n_dd += 1
        print(f"  回撤可算 {n_dd}/{len(priced)}")
        if n_dd == 0:
            warn.append("回撤维度未取到任何历史行情，本次榜单缺「刚变便宜 vs 一直便宜」的区分。")

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
            # 回撤单列，不混进估值项——它回答的是「什么时候变便宜的」，不是「有多便宜」
            if r.get("dd_3y") is not None and r["dd_3y"] >= DRAWDOWN_MIN:
                r["drawdown_pass"] = True
            if r["sbc_ratio"] is not None and sbc_cut is not None and r["sbc_ratio"] <= sbc_cut:
                passed.append("SBC 稀释")
            r["passed"] = passed
            r["pct"] = {"ev_ebitda": rank_pct(ev_vals, r["ev_ebitda"]),
                        "pb": rank_pct(pb_vals, r["pb"]),
                        "fcf_yield": rank_pct(fy_vals, r["fcf_yield"])}
            results.append(r)
        # 先硬过滤，不加权打分——没验证过筛选力度就引入权重 = 把主观判断伪装成算法
        # 回撤作为**第二排序键**而非过滤器：不剔除无回撤的标的（它们仍是合格的便宜货），
        # 只是把「刚变便宜」的排在「一直便宜」前面，让两类在榜单上可分辨。
        results.sort(key=lambda r: (-len(r["passed"]), not r.get("drawdown_pass", False),
                                    r["ev_ebitda"] or 9e9))

    out = {
        "updated_at": now,
        "year": YEAR,
        "source_boundary": new_rd,
        "coverage_note": ("EDGAR 仅覆盖向 SEC 报送的主体，扫描范围为美股。"
                          "伯里本人选股不限国别（历史上做过波兰、英国、墨西哥小盘股）。"
                          "本扫描器范围小于其真实选股范围——这是数据源的收窄，不是选股标准的收窄。"),
        "sample": {"universe": len(uni), "complete": len(full),
                   "missing_data": len(missing_data), "not_applicable": len(not_applicable),
                   "missing_ratio": round(miss_ratio, 4),
                   "financials_excluded": len(fin_ciks),
                   "stage_a_survivors": len(survivors), "stage_b_priced": len(priced)},
        "drawdown": {"threshold_3y": DRAWDOWN_MIN,
                     "n_pass": sum(1 for r in results if r.get("drawdown_pass")),
                     "note": "阈值按经济逻辑预登记（40% = 倍数被结构性砍半），"
                             "非按与实际持仓的重合度拟合。回撤为排序键，不作过滤器。"},
        "thresholds": {"net_debt_ebitda_cut": nd_cut, "sbc_ratio_cut": sbc_cut,
                       "quantiles": {"net_debt": Q_NETDEBT_MAX, "sbc": Q_SBC_MAX,
                                     "ev_ebitda": Q_EV_EBITDA, "pb": Q_PB,
                                     "fcf_yield": Q_FCF_YIELD}},
        "warnings": warn,
        "results": results[:200],
        # 两类单列保留：数据缺失（管道有洞）与不适用（指标无定义），都不静默丢弃
        "missing_data_sample": missing_data[:150],
        "not_applicable_sample": not_applicable[:150],
    }
    with open(SCREEN_FILE, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n  写出 {SCREEN_FILE}：结果 {len(results)} 家 / "
          f"数据缺失 {len(missing_data)} / 不适用 {len(not_applicable)}")
    for w in warn:
        print(f"  ⚠ {w}")


if __name__ == "__main__":
    main()
