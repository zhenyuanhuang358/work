"""
Research data fetcher — runs inside GitHub Actions (unrestricted egress).
Fetches financial data for listed companies and saves to research_cache/.

Sources:
  - yfinance (Yahoo Finance): HK + US stocks, clean structured JSON
  - Sina Finance API: A-share fallback (semi-official, no auth required)
  - Eastmoney quote API: A-share supplementary metrics

Usage:
  python3 scripts/fetch_research_data.py "02255.HK,600519.SS,9988.HK"
"""

import sys
import json
import os
import re
import time
from datetime import datetime, timezone

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ── helpers ──────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe(val):
    """Convert pandas/numpy types to plain Python for JSON serialisation."""
    if val is None or val != val:  # NaN check
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        try:
            return float(val)
        except (TypeError, ValueError):
            return str(val)


# ── yfinance fetcher (HK / US / some HK-listed China co's) ───────────────────

def fetch_via_yfinance(ticker: str) -> dict:
    if not HAS_YFINANCE:
        return {"error": "yfinance not installed"}

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        result = {
            "ticker": ticker,
            "name": info.get("longName") or info.get("shortName", ""),
            "currency": info.get("currency", ""),
            "exchange": info.get("exchange", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "updated_at": _now(),
            "source": "yfinance",
            "summary": info.get("longBusinessSummary", "")[:600],
            "market_data": {
                "market_cap": _safe(info.get("marketCap")),
                "price": _safe(info.get("currentPrice") or info.get("regularMarketPrice")),
                "52w_high": _safe(info.get("fiftyTwoWeekHigh")),
                "52w_low": _safe(info.get("fiftyTwoWeekLow")),
            },
            "financials": {
                "revenue_ttm": _safe(info.get("totalRevenue")),
                "gross_profit_ttm": _safe(info.get("grossProfits")),
                "ebitda": _safe(info.get("ebitda")),
                "net_income_ttm": _safe(info.get("netIncomeToCommon")),
                "gross_margin": _safe(info.get("grossMargins")),
                "operating_margin": _safe(info.get("operatingMargins")),
                "net_margin": _safe(info.get("profitMargins")),
                "return_on_equity": _safe(info.get("returnOnEquity")),
                "debt_to_equity": _safe(info.get("debtToEquity")),
                "free_cash_flow": _safe(info.get("freeCashflow")),
                "employees": _safe(info.get("fullTimeEmployees")),
            },
            "annual_income": {},
            "annual_balance": {},
        }

        # Annual income statement — last 4 fiscal years
        try:
            fin = t.financials
            if fin is not None and not fin.empty:
                for col in fin.columns[:4]:
                    yr = str(col)[:10]
                    result["annual_income"][yr] = {
                        k: _safe(v) for k, v in fin[col].items()
                    }
        except Exception:
            pass

        # Balance sheet snapshot
        try:
            bs = t.balance_sheet
            if bs is not None and not bs.empty:
                col = bs.columns[0]
                yr = str(col)[:10]
                result["annual_balance"][yr] = {
                    k: _safe(v) for k, v in bs[col].items()
                }
        except Exception:
            pass

        return result

    except Exception as e:
        return {"ticker": ticker, "error": str(e), "source": "yfinance", "updated_at": _now()}


# ── Sina Finance API fetcher (A-shares: SH60xxxx / SZ00xxxx / SZ30xxxx) ─────

def fetch_via_sina(code: str) -> dict:
    """
    Sina Finance has a semi-official, no-auth financial summary API.
    code: e.g. '600519' (without exchange suffix)
    exchange prefix: 'sh' for Shanghai, 'sz' for Shenzhen
    """
    if not HAS_REQUESTS:
        return {"error": "requests not installed"}

    prefix = "sh" if code.startswith("6") else "sz"
    url = f"http://hq.sinajs.cn/list={prefix}{code}"
    hdrs = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=hdrs, timeout=10)
        r.encoding = "gbk"
        raw = r.text

        # Parse: var hq_str_sh600519="贵州茅台,1800.00,..."
        m = re.search(r'"([^"]+)"', raw)
        if not m:
            return {"error": "parse failed", "raw": raw[:200]}

        fields = m.group(1).split(",")
        # Sina real-time quote: name,open,close,current,high,low,bid,ask,...,date,time
        if len(fields) < 10:
            return {"error": "unexpected field count", "fields": fields}

        return {
            "ticker": f"{prefix}{code}",
            "name": fields[0],
            "currency": "CNY",
            "exchange": "SSE" if prefix == "sh" else "SZSE",
            "updated_at": _now(),
            "source": "sina_hq",
            "market_data": {
                "price": _safe(fields[3]),
                "open": _safe(fields[1]),
                "prev_close": _safe(fields[2]),
                "high": _safe(fields[4]),
                "low": _safe(fields[5]),
                "volume": _safe(fields[8]),
                "amount": _safe(fields[9]),
            },
            "financials": {},  # real-time quote only; no financial statements via this endpoint
            "annual_income": {},
            "note": "Sina HQ provides real-time quote only. For financials, fetch eastmoney or read annual report.",
        }
    except Exception as e:
        return {"ticker": code, "error": str(e), "source": "sina_hq", "updated_at": _now()}


# ── Eastmoney API — A-share key financial metrics (no auth) ──────────────────

def fetch_via_eastmoney_ashare(code: str) -> dict:
    """
    Eastmoney provides a structured JSON endpoint for A-share fundamentals.
    code: '600519' style (6-digit, no exchange prefix)
    """
    if not HAS_REQUESTS:
        return {"error": "requests not installed"}

    # Determine market: 1=SH, 0=SZ
    mkt = "1" if code.startswith("6") else "0"
    secid = f"{mkt}.{code}"

    url = (
        "https://push2.eastmoney.com/api/qt/stock/get"
        f"?secid={secid}"
        "&fields=f57,f58,f107,f116,f117,f162,f163,f164,f167,f173,f174,f177"
        "&ut=fa5fd1943c7b386f172d6893dbfba10b"
    )
    hdrs = {
        "Referer": "https://quote.eastmoney.com/",
        "User-Agent": "Mozilla/5.0",
    }

    try:
        r = requests.get(url, headers=hdrs, timeout=10)
        d = r.json().get("data", {})
        if not d:
            return {"error": "empty response", "source": "eastmoney"}

        return {
            "ticker": f"{'sh' if mkt == '1' else 'sz'}{code}",
            "name": d.get("f58", ""),
            "currency": "CNY",
            "updated_at": _now(),
            "source": "eastmoney_quote",
            "market_data": {
                "market_cap_cny_100m": _safe(d.get("f116")),  # 总市值（元）
                "float_cap_cny_100m": _safe(d.get("f117")),   # 流通市值
                "pe_ttm": _safe(d.get("f162")),
                "pe_lyr": _safe(d.get("f163")),
                "pb": _safe(d.get("f167")),
                "dividend_yield": _safe(d.get("f173")),
                "eps_ttm": _safe(d.get("f174")),
            },
            "financials": {},
            "annual_income": {},
            "note": "Eastmoney quote API: market metrics only. Full financials require report parsing.",
        }
    except Exception as e:
        return {"ticker": code, "error": str(e), "source": "eastmoney", "updated_at": _now()}


# ── Router: pick the right fetcher per ticker format ────────────────────────

def fetch(ticker: str) -> dict:
    ticker = ticker.strip()

    # HK-listed (e.g. 02255.HK, 9988.HK)
    if ticker.upper().endswith(".HK"):
        print(f"  → yfinance (HK): {ticker}")
        return fetch_via_yfinance(ticker)

    # US-listed
    if re.match(r"^[A-Z]{1,5}$", ticker):
        print(f"  → yfinance (US): {ticker}")
        return fetch_via_yfinance(ticker)

    # A-share: 600519.SS / 000858.SZ (Yahoo-style) or bare 6-digit code
    a_match = re.match(r"^(\d{6})\.(SS|SZ|sh|sz)?$", ticker, re.IGNORECASE)
    bare_match = re.match(r"^(\d{6})$", ticker)
    code = None
    if a_match:
        code = a_match.group(1)
    elif bare_match:
        code = bare_match.group(1)

    if code:
        # Try yfinance with Yahoo-style suffix first (better financials)
        suffix = "SS" if code.startswith("6") else "SZ"
        yf_ticker = f"{code}.{suffix}"
        print(f"  → yfinance (A-share): {yf_ticker}")
        result = fetch_via_yfinance(yf_ticker)

        # If yfinance gives no revenue data, supplement with Eastmoney quote
        if not result.get("financials", {}).get("revenue_ttm"):
            print(f"  → eastmoney fallback for {code}")
            em = fetch_via_eastmoney_ashare(code)
            result["market_data_eastmoney"] = em.get("market_data", {})
            result["source"] += "+eastmoney"

        return result

    # Unknown format — try yfinance anyway
    print(f"  → yfinance (unknown format): {ticker}")
    return fetch_via_yfinance(ticker)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Usage: python3 fetch_research_data.py TICKER1,TICKER2,...")
        sys.exit(0)

    tickers = [t.strip() for t in sys.argv[1].split(",") if t.strip()]
    os.makedirs("research_cache", exist_ok=True)

    results = []
    for ticker in tickers:
        print(f"\nFetching {ticker}...")
        data = fetch(ticker)
        slug = re.sub(r"[^A-Za-z0-9]", "_", ticker).lower()
        path = f"research_cache/{slug}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        status = "✓" if "error" not in data else f"✗ {data['error']}"
        print(f"  {status} → {path}")
        results.append({"ticker": ticker, "path": path, "ok": "error" not in data})
        time.sleep(0.5)  # polite rate-limiting

    # Write manifest so the agent can check what's cached
    manifest = {
        "updated_at": _now(),
        "entries": results,
    }
    with open("research_cache/_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nDone. {sum(r['ok'] for r in results)}/{len(results)} succeeded.")


if __name__ == "__main__":
    main()
