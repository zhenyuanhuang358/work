"""
Price fetcher — runs inside GitHub Actions (unrestricted egress).
Fetches equity prices via Finnhub API + VIX/Treasury via yfinance.
Saves to stock_prices.json.

Tickers tracked:
  Equities (Finnhub):  20 tickers - indices/megacaps/mid-price CSP-friendly names
  Indices (yfinance):  ^VIX (CBOE VIX)  ^TNX (10-year Treasury yield)
"""

import os
import json
import time
from datetime import datetime, timezone

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

EQUITY_TICKERS = [
    # 指数/大盘
    "SPY", "QQQ", "IWM", "GLD", "SLV", "TLT", "XLE",
    # 大盘股（价差策略用）
    "NVDA", "PLTR", "TSLA", "AAPL", "AMD", "MU",
    # 中低价高流动性（小账户CSP友好带：股价20-80美元）
    "SOFI", "HOOD", "INTC", "F", "UBER", "T", "KO",
]

INDEX_TICKERS = {
    "^VIX": "vix",
    "^TNX": "treasury_10y",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_equity_finnhub(ticker: str, token: str) -> dict | None:
    if not HAS_REQUESTS or not token:
        return None
    url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={token}"
    try:
        r = requests.get(url, timeout=8)
        d = r.json()
        if d.get("c") and d["c"] > 0:
            return {
                "price": round(d["c"], 2),
                "change": round(d.get("d") or 0, 2),
                "changePct": round(d.get("dp") or 0, 2),
                "high": round(d.get("h") or 0, 2),
                "low": round(d.get("l") or 0, 2),
                "prevClose": round(d.get("pc") or 0, 2),
            }
    except Exception as e:
        print(f"  Finnhub error for {ticker}: {e}")
    return None


def fetch_equity_yfinance(ticker: str) -> dict | None:
    if not HAS_YFINANCE:
        return None
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
        high = info.get("dayHigh") or info.get("regularMarketDayHigh")
        low = info.get("dayLow") or info.get("regularMarketDayLow")
        if price:
            change = round(float(price) - float(prev), 2) if prev else 0
            change_pct = round((price - prev) / prev * 100, 2) if prev else 0
            return {
                "price": round(float(price), 2),
                "change": change,
                "changePct": change_pct,
                "high": round(float(high), 2) if high else None,
                "low": round(float(low), 2) if low else None,
                "prevClose": round(float(prev), 2) if prev else None,
            }
    except Exception as e:
        print(f"  yfinance error for {ticker}: {e}")
    return None


def fetch_index_yfinance(yf_symbol: str) -> float | None:
    """Fetch a single index value (VIX, TNX) via yfinance."""
    if not HAS_YFINANCE:
        return None
    try:
        t = yf.Ticker(yf_symbol)
        info = t.info or {}
        val = info.get("regularMarketPrice") or info.get("currentPrice")
        if val:
            return round(float(val), 2)
        # Fallback: last close from fast_info
        fi = t.fast_info
        if hasattr(fi, "last_price") and fi.last_price:
            return round(float(fi.last_price), 2)
    except Exception as e:
        print(f"  yfinance index error for {yf_symbol}: {e}")
    return None


def main():
    token = os.environ.get("FINNHUB_TOKEN", "")
    prices = {}

    print("Fetching equities...")
    for ticker in EQUITY_TICKERS:
        print(f"  {ticker}...", end=" ")
        data = fetch_equity_finnhub(ticker, token)
        if not data:
            print("Finnhub failed, trying yfinance...", end=" ")
            data = fetch_equity_yfinance(ticker)
        if data:
            prices[ticker] = data
            print(f"${data['price']} ({data['changePct']:+.2f}%)")
        else:
            print("FAILED")
        time.sleep(0.2)

    print("\nFetching indices (VIX + 10yr Treasury)...")
    index_data = {}
    for yf_symbol, key in INDEX_TICKERS.items():
        print(f"  {yf_symbol}...", end=" ")
        val = fetch_index_yfinance(yf_symbol)
        if val is not None:
            index_data[key] = val
            print(val)
        else:
            print("FAILED")
        time.sleep(0.3)

    output = {
        "updated_at": _now(),
        "vix": index_data.get("vix"),
        "treasury_10y": index_data.get("treasury_10y"),
        "prices": prices,
    }

    with open("stock_prices.json", "w") as f:
        json.dump(output, f, indent=2)

    n_ok = len(prices)
    print(f"\nDone. {n_ok}/{len(EQUITY_TICKERS)} equities, "
          f"VIX={'✓' if index_data.get('vix') else '✗'}, "
          f"10yr={'✓' if index_data.get('treasury_10y') else '✗'}")


if __name__ == "__main__":
    main()
