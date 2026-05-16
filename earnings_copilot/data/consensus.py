"""
Expectation gap data engine — three-tier fallback.

Tier 1 (paid):    ConsensusData / Bloomberg / FactSet API
Tier 2 (free):    yfinance analyst estimates (actual consensus, not price history)
Tier 3 (LLM):     Ask Claude to estimate based on sector comps and growth trends

Note: the original draft's Tier 2 used stock price history to "estimate" revenue —
that's fundamentally wrong. yfinance exposes actual analyst consensus via
ticker.earnings_estimate and ticker.revenue_estimate. Use those.
"""

import asyncio
import time
from typing import Optional

import aiohttp

from earnings_copilot.models import ExpectationData


async def _fetch_consensus_api(session: aiohttp.ClientSession, ticker: str, api_key: str) -> Optional[dict]:
    url = "https://api.consensusdata.com/v1/consensus"
    params = {"ticker": ticker, "metrics": "EPS,Revenue", "period": "next_quarter"}
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                return await r.json()
    except Exception:
        pass
    return None


def _fetch_yfinance_estimates(ticker: str) -> Optional[dict]:
    """yfinance actual analyst consensus — NOT price history."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)

        # These return real analyst consensus tables, not price data
        eps_est = t.earnings_estimate
        rev_est = t.revenue_estimate

        if eps_est is None or rev_est is None:
            return None

        # Take the "0q" row = current quarter estimate
        eps_val = None
        rev_val = None

        if "avg" in eps_est.columns and "0q" in eps_est.index:
            eps_val = float(eps_est.loc["0q", "avg"])

        if "avg" in rev_est.columns and "0q" in rev_est.index:
            rev_val = float(rev_est.loc["0q", "avg"]) / 1e6  # convert to millions

        return {"eps": eps_val, "revenue_millions": rev_val}
    except Exception:
        return None


async def _fetch_llm_estimate(ticker: str) -> Optional[dict]:
    """Last resort: ask Claude to estimate consensus from public information."""
    import anthropic

    client = anthropic.Anthropic()
    prompt = (
        f"What is Wall Street's current consensus EPS estimate and revenue estimate "
        f"for {ticker} for the upcoming quarter? "
        f"State the values concisely in JSON format: "
        f'{{\"eps_estimate\": <float or null>, \"revenue_estimate_millions\": <float or null>, '
        f'\"confidence\": \"low|medium\", \"reasoning\": \"<one sentence>\"}}'
        f"\nReturn only valid JSON."
    )

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    import json, re
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
        return {
            "eps": data.get("eps_estimate"),
            "revenue_millions": data.get("revenue_estimate_millions"),
        }
    except Exception:
        return None


async def get_expectation_data(
    ticker: str,
    consensus_api_key: Optional[str] = None,
) -> ExpectationData:
    """
    Fetch consensus expectations with automatic tier fallback.
    Never raises — returns ExpectationData with error field on total failure.
    """
    t0 = time.time()

    async with aiohttp.ClientSession() as session:
        # Tier 1: paid API
        if consensus_api_key:
            data = await _fetch_consensus_api(session, ticker, consensus_api_key)
            if data:
                return ExpectationData(
                    ticker=ticker,
                    eps_estimate=data.get("eps"),
                    revenue_estimate=data.get("revenue_millions"),
                    source="ConsensusData API",
                    staleness_hours=(time.time() - t0) / 3600,
                )

    # Tier 2: yfinance (sync, run in thread)
    loop = asyncio.get_event_loop()
    yf_data = await loop.run_in_executor(None, _fetch_yfinance_estimates, ticker)
    if yf_data and (yf_data.get("eps") or yf_data.get("revenue_millions")):
        return ExpectationData(
            ticker=ticker,
            eps_estimate=yf_data.get("eps"),
            revenue_estimate=yf_data.get("revenue_millions"),
            source="yfinance analyst estimates",
            staleness_hours=(time.time() - t0) / 3600,
        )

    # Tier 3: LLM estimation
    llm_data = await _fetch_llm_estimate(ticker)
    if llm_data and (llm_data.get("eps") or llm_data.get("revenue_millions")):
        return ExpectationData(
            ticker=ticker,
            eps_estimate=llm_data.get("eps"),
            revenue_estimate=llm_data.get("revenue_millions"),
            source="LLM estimate (low confidence)",
            staleness_hours=(time.time() - t0) / 3600,
        )

    return ExpectationData(
        ticker=ticker,
        eps_estimate=None,
        revenue_estimate=None,
        source="unavailable",
        error="All tiers failed. Provide consensus data manually.",
    )
