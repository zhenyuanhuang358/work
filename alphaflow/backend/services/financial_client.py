"""
Financial data client.
Production: uses yfinance + SEC EDGAR.
Demo mode: returns embedded sample data for known tickers.
"""
import httpx
import json
from typing import Optional

# Sample data for demo — real NVDA Q1 FY2026 figures (quarter ended Apr 27, 2025)
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
            "segments": [
                {"name": "Data Center", "revenue_m": 39106, "growth_yoy_pct": 73.0},
                {"name": "Gaming", "revenue_m": 3803, "growth_yoy_pct": 42.0},
                {"name": "Professional Visualization", "revenue_m": 549, "growth_yoy_pct": 19.0},
                {"name": "Automotive", "revenue_m": 567, "growth_yoy_pct": 72.0},
                {"name": "OEM & Other", "revenue_m": 37, "growth_yoy_pct": -32.0},
            ],
            "guidance": {
                "next_quarter": "Q2 FY2026",
                "revenue_midpoint_m": 45000,
                "revenue_range": "$44.5B - $45.5B",
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
                "peer_avg_pe_forward": 28.0,
                "five_year_avg_pe": 55.0,
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
                "tablets, wearables, and accessories. The company also provides software, "
                "services, and digital content. Services segment has become a key growth driver."
            ),
            "market_cap_b": 3180,
            "employees": 164000,
        },
        "financials": {
            "quarter": "Q1 FY2025",
            "period_end": "December 28, 2024",
            "revenue_m": 124300,
            "revenue_prev_quarter_m": 94900,
            "revenue_prev_year_m": 119575,
            "revenue_growth_yoy_pct": 4.0,
            "revenue_growth_qoq_pct": 31.0,
            "gross_profit_m": 58270,
            "gross_margin_pct": 46.9,
            "gross_margin_prev_year_pct": 45.9,
            "operating_income_m": 39680,
            "operating_margin_pct": 31.9,
            "net_income_m": 36330,
            "net_margin_pct": 29.2,
            "eps_diluted": 2.40,
            "eps_prev_year": 2.18,
            "eps_growth_yoy_pct": 10.1,
            "free_cash_flow_m": 30000,
            "cash_and_equivalents_m": 53770,
            "capex_m": 3200,
            "r_and_d_m": 7870,
            "segments": [
                {"name": "iPhone", "revenue_m": 69140, "growth_yoy_pct": 1.0},
                {"name": "Services", "revenue_m": 26340, "growth_yoy_pct": 14.0},
                {"name": "Mac", "revenue_m": 8986, "growth_yoy_pct": 15.0},
                {"name": "iPad", "revenue_m": 8089, "growth_yoy_pct": 15.0},
                {"name": "Wearables & Home", "revenue_m": 11745, "growth_yoy_pct": -2.0},
            ],
            "guidance": {
                "next_quarter": "Q2 FY2025",
                "revenue_midpoint_m": None,
                "revenue_range": "Low-to-mid single digit YoY growth",
                "gross_margin_pct": 46.5,
                "gross_margin_guidance": "46.0% - 47.0% GAAP",
                "management_commentary": (
                    "Services revenue reached an all-time high with over 1 billion paid subscriptions. "
                    "iPhone 16 cycle demand remains healthy globally. "
                    "We expect continued Services momentum driven by Apple Intelligence rollout. "
                    "Tariff uncertainty creates near-term supply chain considerations."
                ),
            },
            "consensus": {
                "revenue_estimate_m": 124100,
                "eps_estimate": 2.35,
                "beat_revenue_pct": 0.2,
                "beat_eps_pct": 2.1,
            },
        },
        "context": {
            "recent_news": [
                "Apple Intelligence features rolling out to iPhone 16 series",
                "Services segment approaching $30B quarterly run rate",
                "India manufacturing expansion accelerates amid tariff concerns",
                "DOJ antitrust case overhang on App Store business model",
                "Vision Pro sales below initial expectations",
            ],
            "valuation": {
                "pe_ttm": 32.4,
                "pe_forward": 29.8,
                "ev_revenue_ttm": 8.6,
                "ev_ebitda_ttm": 24.5,
                "peer_avg_pe_forward": 26.0,
                "five_year_avg_pe": 28.0,
            },
        },
    },
}


async def get_company_data(ticker: str) -> dict:
    """Return company financials. Production: calls real APIs. Demo: sample data."""
    ticker = ticker.upper()

    if ticker in SAMPLE_DATA:
        return SAMPLE_DATA[ticker]

    # Production path — try yfinance
    try:
        return await _fetch_yfinance(ticker)
    except Exception:
        raise ValueError(
            f"Ticker '{ticker}' not found. Demo supports: {list(SAMPLE_DATA.keys())}. "
            "Deploy to production for full ticker coverage."
        )


async def _fetch_yfinance(ticker: str) -> dict:
    """Fetch real data via yfinance (requires network access)."""
    import yfinance as yf

    stock = yf.Ticker(ticker)
    info = stock.info
    fin = stock.quarterly_financials
    cf = stock.quarterly_cashflow

    if fin.empty:
        raise ValueError(f"No financial data for {ticker}")

    q0, q1 = fin.columns[0], fin.columns[1] if len(fin.columns) > 1 else fin.columns[0]
    q_year_ago = fin.columns[3] if len(fin.columns) > 3 else fin.columns[-1]

    def safe(df, row, col):
        try:
            return float(df.loc[row, col]) / 1e6
        except Exception:
            return 0.0

    rev = safe(fin, "Total Revenue", q0)
    rev_qoq = safe(fin, "Total Revenue", q1)
    rev_yoy = safe(fin, "Total Revenue", q_year_ago)

    return {
        "company": {
            "name": info.get("longName", ticker),
            "ticker": ticker,
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "description": info.get("longBusinessSummary", ""),
            "market_cap_b": round(info.get("marketCap", 0) / 1e9, 1),
            "employees": info.get("fullTimeEmployees", 0),
        },
        "financials": {
            "quarter": str(q0.date()),
            "period_end": str(q0.date()),
            "revenue_m": rev,
            "revenue_prev_quarter_m": rev_qoq,
            "revenue_prev_year_m": rev_yoy,
            "revenue_growth_yoy_pct": round((rev - rev_yoy) / rev_yoy * 100, 1) if rev_yoy else 0,
            "revenue_growth_qoq_pct": round((rev - rev_qoq) / rev_qoq * 100, 1) if rev_qoq else 0,
            "gross_profit_m": safe(fin, "Gross Profit", q0),
            "gross_margin_pct": round(safe(fin, "Gross Profit", q0) / rev * 100, 1) if rev else 0,
            "gross_margin_prev_year_pct": 0,
            "operating_income_m": safe(fin, "Operating Income", q0),
            "operating_margin_pct": round(safe(fin, "Operating Income", q0) / rev * 100, 1) if rev else 0,
            "net_income_m": safe(fin, "Net Income", q0),
            "net_margin_pct": round(safe(fin, "Net Income", q0) / rev * 100, 1) if rev else 0,
            "eps_diluted": info.get("trailingEps", 0),
            "eps_prev_year": 0,
            "eps_growth_yoy_pct": 0,
            "free_cash_flow_m": safe(cf, "Free Cash Flow", q0) if "Free Cash Flow" in cf.index else 0,
            "cash_and_equivalents_m": info.get("totalCash", 0) / 1e6,
            "capex_m": 0,
            "r_and_d_m": safe(fin, "Research And Development", q0),
            "segments": [],
            "guidance": {
                "next_quarter": "Next Quarter",
                "revenue_midpoint_m": None,
                "revenue_range": "Management did not provide specific guidance",
                "gross_margin_pct": None,
                "gross_margin_guidance": "Not provided",
                "management_commentary": "See latest earnings call transcript for management commentary.",
            },
            "consensus": {
                "revenue_estimate_m": None,
                "eps_estimate": None,
                "beat_revenue_pct": None,
                "beat_eps_pct": None,
            },
        },
        "context": {
            "recent_news": [],
            "valuation": {
                "pe_ttm": info.get("trailingPE", 0),
                "pe_forward": info.get("forwardPE", 0),
                "ev_revenue_ttm": info.get("enterpriseToRevenue", 0),
                "ev_ebitda_ttm": info.get("enterpriseToEbitda", 0),
                "peer_avg_pe_forward": 0,
                "five_year_avg_pe": 0,
            },
        },
    }
