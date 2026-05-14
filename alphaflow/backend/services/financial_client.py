"""
Financial data client.
Primary:  Financial Modeling Prep (FMP) API — real multi-quarter data.
Fallback: Embedded sample data for offline / sandbox environments.
"""
import os
import httpx
from typing import Optional

FMP_BASE = "https://financialmodelingprep.com/api/v3"


def _fmp_key() -> Optional[str]:
    return os.environ.get("FMP_API_KEY")


async def _fmp_get(path: str, params: dict = {}) -> dict | list:
    key = _fmp_key()
    if not key:
        raise RuntimeError("FMP_API_KEY not set")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{FMP_BASE}{path}", params={"apikey": key, **params})
        r.raise_for_status()
        return r.json()


async def get_company_data(ticker: str) -> dict:
    ticker = ticker.upper()

    if _fmp_key():
        try:
            return await _fetch_fmp(ticker)
        except Exception as e:
            # network blocked or key issue — fall through to sample data
            if ticker in SAMPLE_DATA:
                return SAMPLE_DATA[ticker]
            raise ValueError(f"FMP fetch failed for {ticker}: {e}")

    if ticker in SAMPLE_DATA:
        return SAMPLE_DATA[ticker]

    raise ValueError(
        f"'{ticker}' not in demo data and FMP_API_KEY not set. "
        f"Set FMP_API_KEY or use: {list(SAMPLE_DATA.keys())}"
    )


async def _fetch_fmp(ticker: str) -> dict:
    """Fetch comprehensive data from FMP for any ticker."""
    # Parallel fetch all endpoints
    import asyncio
    profile_task     = _fmp_get(f"/profile/{ticker}")
    income_task      = _fmp_get(f"/income-statement/{ticker}", {"period": "quarter", "limit": 8})
    balance_task     = _fmp_get(f"/balance-sheet-statement/{ticker}", {"period": "quarter", "limit": 4})
    cashflow_task    = _fmp_get(f"/cash-flow-statement/{ticker}", {"period": "quarter", "limit": 4})
    metrics_task     = _fmp_get(f"/key-metrics/{ticker}", {"period": "quarter", "limit": 4})
    ratios_task      = _fmp_get(f"/ratios/{ticker}", {"period": "quarter", "limit": 1})
    surprises_task   = _fmp_get(f"/earnings-surprises/{ticker}")
    estimates_task   = _fmp_get(f"/analyst-estimates/{ticker}", {"period": "quarter", "limit": 2})

    (profile, income, balance, cashflow,
     metrics, ratios, surprises, estimates) = await asyncio.gather(
        profile_task, income_task, balance_task, cashflow_task,
        metrics_task, ratios_task, surprises_task, estimates_task,
        return_exceptions=True
    )

    def safe_list(v): return v if isinstance(v, list) else []
    profile    = profile[0]   if isinstance(profile, list) and profile else {}
    income     = safe_list(income)
    balance    = safe_list(balance)
    cashflow   = safe_list(cashflow)
    metrics    = safe_list(metrics)
    ratios     = safe_list(ratios)
    surprises  = safe_list(surprises)
    estimates  = safe_list(estimates)

    if not income:
        raise ValueError(f"No income data for {ticker}")

    q0  = income[0]   # most recent quarter
    q1  = income[1]   if len(income) > 1 else {}
    q4  = income[4]   if len(income) > 4 else {}   # year-ago quarter
    b0  = balance[0]  if balance else {}
    cf0 = cashflow[0] if cashflow else {}
    m0  = metrics[0]  if metrics else {}
    r0  = ratios[0]   if ratios else {}

    def v(d, k, div=1): return round((d.get(k) or 0) / div, 2) if div != 1 else (d.get(k) or 0)

    rev     = v(q0, "revenue", 1e6)
    rev_q1  = v(q1, "revenue", 1e6)
    rev_yoy = v(q4, "revenue", 1e6)
    gp      = v(q0, "grossProfit", 1e6)
    oi      = v(q0, "operatingIncome", 1e6)
    ni      = v(q0, "netIncome", 1e6)
    fcf     = v(cf0, "freeCashFlow", 1e6)
    capex   = abs(v(cf0, "capitalExpenditure", 1e6))
    rnd     = v(q0, "researchAndDevelopmentExpenses", 1e6)
    cash    = v(b0, "cashAndCashEquivalents", 1e6)
    eps     = q0.get("eps") or 0
    eps_yoy = q4.get("eps") or 0

    gm_pct    = round(gp / rev * 100, 1) if rev else 0
    gm_yoy    = round(v(q4, "grossProfit", 1e6) / max(v(q4, "revenue", 1e6), 1) * 100, 1)
    om_pct    = round(oi / rev * 100, 1) if rev else 0
    nm_pct    = round(ni / rev * 100, 1) if rev else 0
    rev_g_yoy = round((rev - rev_yoy) / rev_yoy * 100, 1) if rev_yoy else 0
    rev_g_qoq = round((rev - rev_q1) / rev_q1 * 100, 1) if rev_q1 else 0
    eps_g_yoy = round((eps - eps_yoy) / abs(eps_yoy) * 100, 1) if eps_yoy else 0

    # Historical quarters for trend analysis
    history = []
    for q in income[:8]:
        qrev = (q.get("revenue") or 0) / 1e6
        qgp  = (q.get("grossProfit") or 0) / 1e6
        history.append({
            "period": q.get("period", "") + " " + str(q.get("calendarYear", "")),
            "date": q.get("date", ""),
            "revenue_m": round(qrev, 0),
            "gross_margin_pct": round(qgp / qrev * 100, 1) if qrev else 0,
            "eps": q.get("eps") or 0,
            "operating_margin_pct": round((q.get("operatingIncome") or 0) / max(q.get("revenue") or 1, 1) * 100, 1),
        })

    # Surprise data — most recent
    latest_surprise = surprises[0] if surprises else {}
    beat_rev  = round((latest_surprise.get("actualEarningResult", 0) - latest_surprise.get("estimatedEarning", 0)) / max(abs(latest_surprise.get("estimatedEarning") or 1), 1) * 100, 1) if latest_surprise else None
    # Note: surprises endpoint returns EPS beats not revenue; use analyst estimates for revenue
    next_est = estimates[0] if estimates else {}

    return {
        "company": {
            "name": profile.get("companyName", ticker),
            "ticker": ticker,
            "sector": profile.get("sector", ""),
            "industry": profile.get("industry", ""),
            "description": profile.get("description", ""),
            "market_cap_b": round((profile.get("mktCap") or 0) / 1e9, 1),
            "employees": profile.get("fullTimeEmployees", 0),
            "exchange": profile.get("exchangeShortName", ""),
            "ceo": profile.get("ceo", ""),
            "website": profile.get("website", ""),
        },
        "financials": {
            "quarter": f"{q0.get('period','')} {q0.get('calendarYear','')}",
            "period_end": q0.get("date", ""),
            "revenue_m": rev,
            "revenue_prev_quarter_m": rev_q1,
            "revenue_prev_year_m": rev_yoy,
            "revenue_growth_yoy_pct": rev_g_yoy,
            "revenue_growth_qoq_pct": rev_g_qoq,
            "gross_profit_m": gp,
            "gross_margin_pct": gm_pct,
            "gross_margin_prev_year_pct": gm_yoy,
            "operating_income_m": oi,
            "operating_margin_pct": om_pct,
            "net_income_m": ni,
            "net_margin_pct": nm_pct,
            "eps_diluted": eps,
            "eps_prev_year": eps_yoy,
            "eps_growth_yoy_pct": eps_g_yoy,
            "free_cash_flow_m": fcf,
            "cash_and_equivalents_m": cash,
            "capex_m": capex,
            "r_and_d_m": rnd,
            "debt_total_m": v(b0, "totalDebt", 1e6),
            "segments": [],  # FMP segments require premium endpoint
            "guidance": {
                "next_quarter": f"Next Quarter",
                "revenue_midpoint_m": round((next_est.get("revenueAvg") or 0) / 1e6, 0) or None,
                "revenue_range": f"Analyst est: ${round((next_est.get('revenueLow') or 0)/1e9,1)}B – ${round((next_est.get('revenueHigh') or 0)/1e9,1)}B" if next_est else "See latest earnings call",
                "gross_margin_pct": None,
                "gross_margin_guidance": "See latest earnings call transcript",
                "management_commentary": "See latest earnings call transcript for management commentary.",
            },
            "consensus": {
                "revenue_estimate_m": round((next_est.get("revenueAvg") or 0) / 1e6, 0) or None,
                "eps_estimate": next_est.get("epsAvg"),
                "beat_revenue_pct": None,
                "beat_eps_pct": beat_rev,
            },
            "historical_quarters": history,
        },
        "context": {
            "recent_news": [],
            "valuation": {
                "pe_ttm": round(m0.get("peRatio") or 0, 1),
                "pe_forward": round(r0.get("priceEarningsRatio") or 0, 1),
                "ev_revenue_ttm": round(m0.get("evToSales") or 0, 1),
                "ev_ebitda_ttm": round(m0.get("enterpriseValueOverEBITDA") or 0, 1),
                "price_to_book": round(m0.get("pbRatio") or 0, 1),
                "debt_to_equity": round(m0.get("debtToEquity") or 0, 2),
                "current_ratio": round(m0.get("currentRatio") or 0, 2),
                "roe": round((m0.get("roe") or 0) * 100, 1),
                "peer_avg_pe_forward": 0,
                "five_year_avg_pe": 0,
            },
        },
    }


# ── Embedded sample data (offline / sandbox fallback) ────────────────────────

SAMPLE_DATA = {
    "NVDA": {
        "company": {
            "name": "NVIDIA Corporation",
            "ticker": "NVDA",
            "sector": "Technology",
            "industry": "Semiconductors",
            "description": (
                "NVIDIA designs and manufactures graphics processing units (GPUs) and "
                "system-on-chip units. The company operates through two segments: "
                "Compute & Networking and Graphics. NVIDIA is the dominant provider of "
                "AI accelerator chips, commanding ~80% market share in data center GPUs."
            ),
            "market_cap_b": 3290,
            "employees": 36000,
        },
        "financials": {
            "quarter": "Q1 FY2026",
            "period_end": "April 27, 2025",
            "revenue_m": 44062,
            "revenue_prev_quarter_m": 39331,
            "revenue_prev_year_m": 26044,
            "revenue_growth_yoy_pct": 69.2,
            "revenue_growth_qoq_pct": 12.0,
            "gross_profit_m": 32965,
            "gross_margin_pct": 74.8,
            "gross_margin_prev_year_pct": 64.6,
            "operating_income_m": 27558,
            "operating_margin_pct": 62.5,
            "net_income_m": 18775,
            "net_margin_pct": 42.6,
            "eps_diluted": 0.76,
            "eps_prev_year": 0.44,
            "eps_growth_yoy_pct": 72.7,
            "free_cash_flow_m": 14428,
            "cash_and_equivalents_m": 37793,
            "capex_m": 697,
            "r_and_d_m": 3497,
            "debt_total_m": 8462,
            "segments": [
                {"name": "Data Center", "revenue_m": 39106, "growth_yoy_pct": 73.0},
                {"name": "Gaming", "revenue_m": 3803, "growth_yoy_pct": 42.0},
                {"name": "Professional Visualization", "revenue_m": 549, "growth_yoy_pct": 19.0},
                {"name": "Automotive", "revenue_m": 567, "growth_yoy_pct": 72.0},
                {"name": "OEM & Other", "revenue_m": 37, "growth_yoy_pct": -32.0},
            ],
            "historical_quarters": [
                {"period": "Q1 FY2026", "revenue_m": 44062, "gross_margin_pct": 74.8, "eps": 0.76, "operating_margin_pct": 62.5},
                {"period": "Q4 FY2025", "revenue_m": 39331, "gross_margin_pct": 73.5, "eps": 0.89, "operating_margin_pct": 61.1},
                {"period": "Q3 FY2025", "revenue_m": 35082, "gross_margin_pct": 74.6, "eps": 0.78, "operating_margin_pct": 61.8},
                {"period": "Q2 FY2025", "revenue_m": 30040, "gross_margin_pct": 75.1, "eps": 0.67, "operating_margin_pct": 62.0},
                {"period": "Q1 FY2025", "revenue_m": 26044, "gross_margin_pct": 64.6, "eps": 0.44, "operating_margin_pct": 54.1},
                {"period": "Q4 FY2024", "revenue_m": 22103, "gross_margin_pct": 76.0, "eps": 0.52, "operating_margin_pct": 61.6},
                {"period": "Q3 FY2024", "revenue_m": 18120, "gross_margin_pct": 74.0, "eps": 0.40, "operating_margin_pct": 57.5},
                {"period": "Q2 FY2024", "revenue_m": 13507, "gross_margin_pct": 70.1, "eps": 0.25, "operating_margin_pct": 50.3},
            ],
            "guidance": {
                "next_quarter": "Q2 FY2026",
                "revenue_midpoint_m": 45000,
                "revenue_range": "$44.5B – $45.5B",
                "gross_margin_pct": 74.6,
                "gross_margin_guidance": "~74.6% GAAP, ~76.0% non-GAAP",
                "management_commentary": (
                    "Demand for Blackwell architecture GPUs continues to exceed supply. "
                    "We are ramping Blackwell production aggressively to meet hyperscaler demand. "
                    "Supply constraints are expected to ease through the second half of FY2026. "
                    "China export restrictions continue to impact revenue, with alternative "
                    "compliant products being developed."
                ),
            },
            "consensus": {
                "revenue_estimate_m": 43200,
                "eps_estimate": 0.73,
                "beat_revenue_pct": 2.0,
                "beat_eps_pct": 4.1,
            },
        },
        "context": {
            "recent_news": [
                "NVDA announces Blackwell Ultra architecture at GTC 2025",
                "Microsoft, Google, Meta commit to $200B+ AI capex in 2025",
                "US expands chip export restrictions to additional countries",
                "AMD MI350 launch seen as limited competitive threat",
                "Sovereign AI demand accelerating from Middle East, Japan",
            ],
            "valuation": {
                "pe_ttm": 40.2,
                "pe_forward": 33.5,
                "ev_revenue_ttm": 29.8,
                "ev_ebitda_ttm": 47.1,
                "price_to_book": 28.4,
                "debt_to_equity": 0.41,
                "current_ratio": 4.2,
                "roe": 119.4,
                "peer_avg_pe_forward": 28.0,
                "five_year_avg_pe": 55.0,
            },
        },
    },
    "PLTR": {
        "company": {
            "name": "Palantir Technologies Inc.",
            "ticker": "PLTR",
            "sector": "Technology",
            "industry": "Software — Infrastructure",
            "description": (
                "Palantir builds data analytics and AI platforms for government and commercial clients. "
                "Its two core products — Gotham (government) and Foundry (commercial) — are complemented "
                "by AIP (AI Platform), which drives AI adoption in enterprise workflows. "
                "Palantir has been GAAP profitable since Q3 2023 and joined the S&P 500 in September 2024."
            ),
            "market_cap_b": 370,
            "employees": 4200,
            "ceo": "Alexander Karp",
        },
        "financials": {
            "quarter": "Q1 2026",
            "period_end": "March 31, 2026",
            "revenue_m": 1632.6,
            "revenue_prev_quarter_m": 1406.8,
            "revenue_prev_year_m": 884.0,
            "revenue_growth_yoy_pct": 84.7,
            "revenue_growth_qoq_pct": 16.1,
            "gross_profit_m": 1416.8,
            "gross_margin_pct": 86.8,
            "gross_margin_prev_year_pct": 81.0,
            "operating_income_m": 754.0,
            "operating_margin_pct": 46.2,
            "net_income_m": 870.5,
            "net_margin_pct": 53.3,
            "eps_diluted": 0.34,
            "eps_prev_year": 0.08,
            "eps_growth_yoy_pct": 325.0,
            "free_cash_flow_m": 520,
            "cash_and_equivalents_m": 6800,
            "capex_m": 12,
            "r_and_d_m": 161.0,
            "debt_total_m": 0,
            "segments": [],
            "historical_quarters": [
                {"period": "Q1 2026", "revenue_m": 1632.6, "gross_margin_pct": 86.8, "eps": 0.34, "operating_margin_pct": 46.2},
                {"period": "Q4 2025", "revenue_m": 1406.8, "gross_margin_pct": 84.7, "eps": 0.24, "operating_margin_pct": 40.9},
                {"period": "Q3 2025", "revenue_m": 1181.1, "gross_margin_pct": 82.4, "eps": 0.19, "operating_margin_pct": 33.3},
                {"period": "Q2 2025", "revenue_m": 1003.7, "gross_margin_pct": 80.8, "eps": 0.13, "operating_margin_pct": 26.8},
                {"period": "Q1 2025", "revenue_m": 884.0,  "gross_margin_pct": 81.0, "eps": 0.08, "operating_margin_pct": 19.9},
                {"period": "Q4 2024", "revenue_m": 828.0,  "gross_margin_pct": 80.3, "eps": 0.14, "operating_margin_pct": 16.8},
                {"period": "Q3 2024", "revenue_m": 726.0,  "gross_margin_pct": 81.7, "eps": 0.10, "operating_margin_pct": 16.0},
                {"period": "Q2 2024", "revenue_m": 678.0,  "gross_margin_pct": 81.3, "eps": 0.09, "operating_margin_pct": 14.5},
            ],
            "guidance": {
                "next_quarter": "Q2 2026",
                "revenue_midpoint_m": 1718,
                "revenue_range": "$1.71B – $1.73B (est.)",
                "gross_margin_pct": None,
                "gross_margin_guidance": "Adj. Operating Margin ~47%+",
                "management_commentary": (
                    "Palantir is the default AI operating system for the US government and enterprise. "
                    "AIP adoption has crossed the chasm — every major US institution is now a customer or prospect. "
                    "Revenue doubled year-over-year as operating margins approached 50%, a combination "
                    "unprecedented at this scale in enterprise software. "
                    "The defense and intelligence community is accelerating AI deployment at a pace we have "
                    "never seen. Rule of 40 score now exceeds 130. "
                    "We are raising full-year 2026 guidance significantly above prior expectations."
                ),
            },
            "consensus": {
                "revenue_estimate_m": 1570,
                "eps_estimate": 0.29,
                "beat_revenue_pct": 4.0,
                "beat_eps_pct": 17.2,
            },
        },
        "context": {
            "recent_news": [
                "PLTR Q1 2026: revenue $1.63B (+85% YoY), operating margin 46.2% — massive beat",
                "AIP now deployed across majority of Fortune 500 — enterprise penetration accelerating",
                "US defense AI budget expansion post-2025 geopolitical escalation driving gov. contracts",
                "Palantir named preferred AI platform for NATO allied command infrastructure",
                "Short sellers capitulate as PLTR sustains 80%+ growth at billion-dollar revenue scale",
            ],
            "valuation": {
                "pe_ttm": 185.0,
                "pe_forward": 110.0,
                "ev_revenue_ttm": 55.0,
                "ev_ebitda_ttm": 130.0,
                "price_to_book": 35.0,
                "debt_to_equity": 0.0,
                "current_ratio": 7.1,
                "roe": 38.0,
                "peer_avg_pe_forward": 45.0,
                "five_year_avg_pe": 0,
            },
        },
    },
    "AAPL": {
        "company": {
            "name": "Apple Inc.",
            "ticker": "AAPL",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "description": (
                "Apple designs, manufactures, and markets smartphones, personal computers, "
                "tablets, wearables, and accessories worldwide. Services segment (App Store, "
                "Apple Music, iCloud, Apple TV+) has become the primary margin driver."
            ),
            "market_cap_b": 3150,
            "employees": 164000,
            "ceo": "Tim Cook",
        },
        "financials": {
            "quarter": "Q2 FY2026",
            "period_end": "March 28, 2026",
            "revenue_m": 111184,
            "revenue_prev_quarter_m": 143756,
            "revenue_prev_year_m": 95360,
            "revenue_growth_yoy_pct": 16.6,
            "revenue_growth_qoq_pct": -22.6,
            "gross_profit_m": 54781,
            "gross_margin_pct": 49.3,
            "gross_margin_prev_year_pct": 47.1,
            "operating_income_m": 35885,
            "operating_margin_pct": 32.3,
            "net_income_m": 29578,
            "net_margin_pct": 26.6,
            "eps_diluted": 2.01,
            "eps_prev_year": 1.65,
            "eps_growth_yoy_pct": 21.8,
            "free_cash_flow_m": 27000,
            "cash_and_equivalents_m": 48000,
            "capex_m": 3200,
            "r_and_d_m": 11419,
            "debt_total_m": 97000,
            "segments": [],
            "historical_quarters": [
                {"period": "Q2 FY2026", "revenue_m": 111184, "gross_margin_pct": 49.3, "eps": 2.01, "operating_margin_pct": 32.3},
                {"period": "Q1 FY2026", "revenue_m": 143756, "gross_margin_pct": 48.1, "eps": 2.84, "operating_margin_pct": 35.4},
                {"period": "Q4 FY2025", "revenue_m": 102466, "gross_margin_pct": 47.2, "eps": 1.85, "operating_margin_pct": 31.6},
                {"period": "Q3 FY2025", "revenue_m": 94036,  "gross_margin_pct": 46.5, "eps": 1.57, "operating_margin_pct": 30.0},
                {"period": "Q2 FY2025", "revenue_m": 95360,  "gross_margin_pct": 47.1, "eps": 1.65, "operating_margin_pct": 30.8},
                {"period": "Q1 FY2025", "revenue_m": 124300, "gross_margin_pct": 46.9, "eps": 2.40, "operating_margin_pct": 31.9},
                {"period": "Q4 FY2024", "revenue_m": 94900,  "gross_margin_pct": 46.2, "eps": 1.64, "operating_margin_pct": 29.6},
                {"period": "Q3 FY2024", "revenue_m": 85777,  "gross_margin_pct": 46.3, "eps": 1.40, "operating_margin_pct": 29.6},
            ],
            "guidance": {
                "next_quarter": "Q3 FY2026",
                "revenue_midpoint_m": None,
                "revenue_range": "Low-to-mid single digit YoY growth (company guidance)",
                "gross_margin_pct": 49.5,
                "gross_margin_guidance": "49.0% – 50.0%",
                "management_commentary": (
                    "Services revenue continues to grow at double-digit rates, driving margin expansion. "
                    "Apple Intelligence is rolling out to more languages and devices, accelerating iPhone upgrade cycles. "
                    "India manufacturing now accounts for over 25% of iPhone production, reducing tariff exposure. "
                    "We are seeing record Services revenue with over 1.1 billion paid subscriptions globally. "
                    "The Mac and iPad segments showed strong momentum driven by M-series chip adoption. "
                    "Gross margins expanded to 49.3%, the highest in company history, driven by Services mix shift."
                ),
            },
            "consensus": {
                "revenue_estimate_m": 107500,
                "eps_estimate": 1.95,
                "beat_revenue_pct": 3.4,
                "beat_eps_pct": 3.1,
            },
        },
        "context": {
            "recent_news": [
                "Apple Intelligence expanding to Chinese, Japanese, Korean — potential China revival",
                "Services revenue approaching $30B/quarter — highest margin segment now 30%+ of gross profit",
                "India manufacturing at 25% of iPhone output, significantly reducing tariff risk",
                "Apple Vision Pro 2 rumored for Q4 2026 — spatial computing next growth vector",
                "Gross margin at 49.3% — all-time high driven by Services mix and supply chain efficiency",
            ],
            "valuation": {
                "pe_ttm": 30.2,
                "pe_forward": 27.5,
                "ev_revenue_ttm": 7.8,
                "ev_ebitda_ttm": 21.4,
                "price_to_book": 45.0,
                "debt_to_equity": 1.52,
                "current_ratio": 0.92,
                "roe": 148.0,
                "peer_avg_pe_forward": 26.0,
                "five_year_avg_pe": 28.0,
            },
        },
    },
}
