"""
Fetch NVIDIA latest earnings call transcript from public sources.

Outputs:
  nvda_transcript_new.txt  — full transcript text (only if newer than last run)
  nvda_quarter.txt         — quarter string, e.g. "Q1 FY2027"
  nvda_transcript.hash     — SHA256 of last processed transcript (cache)

Exit code 0 always. nvda_transcript_new.txt is absent if no new content found.
"""

import hashlib
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

TRANSCRIPT_FILE = Path("nvda_transcript_new.txt")
QUARTER_FILE    = Path("nvda_quarter.txt")
HASH_FILE       = Path("nvda_transcript.hash")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

STOCK_PRICES_FILE = Path("stock_prices.json")


# ── Source 1: The Motley Fool ───────────────────────────────────────────────────

def _fool_latest_url() -> tuple[str, str]:
    """Return (url, title) of the most recent NVDA transcript on Motley Fool."""
    index = "https://www.fool.com/earnings-call-transcripts/?symbol=nvda"
    r = requests.get(index, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/earnings/call-transcripts/\d{4}/\d{2}/\d{2}/", href):
            title = a.get_text(strip=True)
            if not href.startswith("http"):
                href = "https://www.fool.com" + href
            return href, title
    return "", ""


def _fool_transcript(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    # Motley Fool wraps article body in various class names over time
    for selector in [
        "div.article-body",
        "div[class*='article-content']",
        "div[class*='tailwind-article']",
        "article",
    ]:
        node = soup.select_one(selector)
        if node:
            return node.get_text(separator="\n", strip=True)
    return soup.get_text(separator="\n", strip=True)


# ── Source 2: Stock Analysis ────────────────────────────────────────────────

def _stockanalysis_transcript() -> tuple[str, str]:
    """Fallback: Stock Analysis earnings transcript page for NVDA."""
    url = "https://stockanalysis.com/stocks/nvda/financials/earnings/"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    # Find transcript link
    for a in soup.find_all("a", href=True):
        if "transcript" in a["href"].lower() or "transcript" in a.get_text().lower():
            href = a["href"]
            if not href.startswith("http"):
                href = "https://stockanalysis.com" + href
            r2 = requests.get(href, headers=HEADERS, timeout=20)
            r2.raise_for_status()
            soup2 = BeautifulSoup(r2.text, "lxml")
            main = soup2.find("main") or soup2.find("article")
            if main:
                return main.get_text(separator="\n", strip=True), a.get_text(strip=True)
    return "", ""


# ── Quarter extraction ────────────────────────────────────────────────────────

def extract_quarter(title: str) -> str:
    m = re.search(r"(Q[1-4]\s*(?:FY|fiscal year)?\s*20\d{2})", title, re.IGNORECASE)
    if m:
        q = re.sub(r"\s+", " ", m.group(1)).upper()
        q = re.sub(r"FISCAL YEAR", "FY", q)
        return q
    # Try "first quarter 2027" style
    words = {"first": "Q1", "second": "Q2", "third": "Q3", "fourth": "Q4"}
    for word, code in words.items():
        m2 = re.search(rf"{word}\s+quarter.*?(20\d{{2}})", title, re.IGNORECASE)
        if m2:
            return f"{code} FY{m2.group(1)}"
    return "Latest Quarter"


# ── NVDA price from local cache ─────────────────────────────────────────────────

def get_nvda_price() -> str:
    if STOCK_PRICES_FILE.exists():
        try:
            data = json.loads(STOCK_PRICES_FILE.read_text(encoding="utf-8"))
            price = data.get("prices", {}).get("NVDA", {}).get("price")
            if price:
                return str(price)
        except Exception:
            pass
    return ""


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    # Clean up any leftover transcript file from previous run
    TRANSCRIPT_FILE.unlink(missing_ok=True)

    text, title = "", ""

    print("Trying The Motley Fool...", flush=True)
    try:
        url, title = _fool_latest_url()
        if url:
            print(f"  Found: {title}")
            print(f"  URL:   {url}")
            text = _fool_transcript(url)
            print(f"  Length: {len(text)} chars")
    except Exception as e:
        print(f"  Motley Fool failed: {e}", flush=True)

    if len(text) < 1000:
        print("Trying Stock Analysis fallback...", flush=True)
        try:
            text, title = _stockanalysis_transcript()
            print(f"  Length: {len(text)} chars")
        except Exception as e:
            print(f"  Stock Analysis failed: {e}", flush=True)

    if len(text) < 1000:
        print("No usable transcript found. Exiting without output file.")
        sys.exit(0)

    # Filter to NVDA-relevant content (transcripts sometimes embed other tickers)
    if "nvidia" not in text.lower() and "nvda" not in text.lower():
        print("Transcript does not appear to be NVIDIA-related. Skipping.")
        sys.exit(0)

    # Hash check — skip if already processed
    content_hash = hashlib.sha256(text.encode()).hexdigest()[:20]
    if HASH_FILE.exists() and HASH_FILE.read_text().strip() == content_hash:
        print(f"Transcript unchanged (hash {content_hash}). Nothing to do.")
        sys.exit(0)

    quarter = extract_quarter(title)
    print(f"Quarter: {quarter}")
    print(f"Hash:    {content_hash} (new)")

    TRANSCRIPT_FILE.write_text(text, encoding="utf-8")
    QUARTER_FILE.write_text(quarter, encoding="utf-8")
    HASH_FILE.write_text(content_hash, encoding="utf-8")

    price = get_nvda_price()
    if price:
        print(f"NVDA price from cache: ${price}")
        Path("nvda_price.txt").write_text(price, encoding="utf-8")
    else:
        Path("nvda_price.txt").write_text("", encoding="utf-8")

    print("Done — nvda_transcript_new.txt ready for Earner.")


if __name__ == "__main__":
    main()
