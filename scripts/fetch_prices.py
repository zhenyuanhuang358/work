"""
Price fetcher — runs inside GitHub Actions (unrestricted egress).
Fetches equity prices via Finnhub API + VIX/Treasury via yfinance.
Saves to stock_prices.json.

Tickers tracked:
  Equities (Finnhub):  23 tickers + yfinance 盘前/盘后扩展时段 - indices/megacaps/mid-price CSP-friendly names
  Indices (yfinance):  ^VIX ^VIX9D ^VIX3M ^SKEW ^VVIX ^TNX — 含尾部风险定价指标
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
    "NVDA", "PLTR", "TSLA", "AAPL", "AMD", "MU", "GOOGL", "VRT", "SNDK", "AVGO",
    # 中低价高流动性（小账户CSP友好带：股价20-80美元）
    "SOFI", "HOOD", "INTC", "F", "UBER", "T", "KO",
    # 持仓标的：SGI = Somnigroup International（原 Tempur Sealy，2025-02 改名）
    "SGI",
]

INDEX_TICKERS = {
    "^VIX": "vix",
    "^TNX": "treasury_10y",
    # 尾部风险定价指标（tail-risk-monitor skill 使用）
    "^VIX9D": "vix9d",      # 9日VIX，短端恐慌
    "^VIX3M": "vix3m",      # 3月VIX，用于期限结构
    "^SKEW": "skew",        # CBOE SKEW，价外put相对定价 = 尾部保护的价格
    "^VVIX": "vvix",        # 波动率的波动率 = VIX期权的贵贱
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


# 扩展时段（盘前/盘后）跟踪名单：财报股需要盘后价才能核实市场反应
EXTENDED_HOURS_TICKERS = ["SNDK", "MU", "NVDA", "AMD", "GOOGL", "AAPL", "PLTR", "VRT", "HOOD", "INTC", "UBER", "AVGO"]


def fetch_extended_hours(ticker: str) -> dict | None:
    """盘前/盘后价。Finnhub 免费档只返回常规时段，故只能走 yfinance。
    财报多在盘后发布，没有这个字段就无法核实市场对财报的第一反应。"""
    if not HAS_YFINANCE:
        return None
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        out = {}
        for src, dst in (("preMarketPrice", "pre"), ("postMarketPrice", "post")):
            v = info.get(src)
            if v:
                out[dst] = round(float(v), 2)
        for src, dst in (("preMarketChangePercent", "prePct"),
                         ("postMarketChangePercent", "postPct")):
            v = info.get(src)
            if v is not None:
                out[dst] = round(float(v), 2)
        # 回退：用含盘前盘后的分钟线取最后一笔，并与常规收盘对比
        if not out:
            h = t.history(period="2d", interval="5m", prepost=True)
            if not h.empty:
                out["lastExtended"] = round(float(h["Close"].iloc[-1]), 2)
                out["source"] = "history(prepost=True)"
        return out or None
    except Exception as e:
        print(f"  extended-hours error for {ticker}: {e}")
    return None


def fetch_index_yfinance(yf_symbol: str) -> float | None:
    """Fetch a single index value (VIX, TNX, SKEW, VVIX...) via yfinance."""
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

    print("\nFetching extended hours (pre/post market)...")
    for ticker in EXTENDED_HOURS_TICKERS:
        if ticker not in prices:
            continue
        ext = fetch_extended_hours(ticker)
        if ext:
            prices[ticker]["extended"] = ext
            print(f"  {ticker}: {ext}")
        time.sleep(0.2)

    print("\nFetching indices (VIX term structure + SKEW + VVIX + 10yr)...")
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

    # 尾部风险衍生指标（由原始指标计算，供 tail-risk-monitor 直接读取）
    vix, vix9d, vix3m = (index_data.get(k) for k in ("vix", "vix9d", "vix3m"))
    term_structure = None
    if vix and vix3m:
        # >1 = backwardation（近月高于远月）= 市场在为眼前的风险付钱 = 压力信号
        term_structure = round(vix / vix3m, 3)
    short_end = None
    if vix9d and vix:
        short_end = round(vix9d / vix, 3)

    output = {
        "updated_at": _now(),
        "vix": vix,
        "treasury_10y": index_data.get("treasury_10y"),
        "tail_risk": {
            "vix9d": vix9d,
            "vix3m": vix3m,
            "skew": index_data.get("skew"),
            "vvix": index_data.get("vvix"),
            "term_structure": term_structure,   # VIX / VIX3M
            "short_end_ratio": short_end,       # VIX9D / VIX
        },
        "prices": prices,
    }

    with open("stock_prices.json", "w") as f:
        json.dump(output, f, indent=2)

    n_ok = len(prices)
    n_idx = len(index_data)
    print(f"\nDone. {n_ok}/{len(EQUITY_TICKERS)} equities, "
          f"{n_idx}/{len(INDEX_TICKERS)} indices, "
          f"term_structure={term_structure}, skew={index_data.get('skew')}")


if __name__ == "__main__":
    main()
