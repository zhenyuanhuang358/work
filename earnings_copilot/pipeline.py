"""
Earnings Copilot — main pipeline.
Orchestrates PDF extraction → consensus fetch → LLM analysis → report assembly.
"""

import asyncio
import time
from pathlib import Path
from typing import Optional

from earnings_copilot.analysis.analyzer import analyze_earnings_call
from earnings_copilot.analysis.prompts import PromptContext
from earnings_copilot.data.consensus import get_expectation_data
from earnings_copilot.extractors.pdf import extract_tables_from_pdf
from earnings_copilot.models import CopilotReport


def _load_transcript(transcript_path: Optional[str]) -> str:
    if not transcript_path:
        return ""
    p = Path(transcript_path)
    if not p.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")
    return p.read_text(encoding="utf-8")


async def run_pipeline(
    ticker: str,
    company_name: str,
    quarter: str,
    pdf_path: Optional[str] = None,
    transcript_path: Optional[str] = None,
    consensus_api_key: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
    prior_quarter_tone: Optional[str] = None,
) -> CopilotReport:
    """
    Full pipeline:
      1. Extract financial tables from PDF (if provided)
      2. Fetch consensus expectations (three-tier fallback)
      3. Analyze earnings call transcript (five LLM prompts)
      4. Assemble CopilotReport
    """
    t0 = time.time()

    # Step 1: PDF table extraction (optional)
    tables = []
    if pdf_path:
        print(f"[1/3] Extracting tables from {pdf_path}...")
        tables = extract_tables_from_pdf(pdf_path)
        print(f"      → {len(tables)} financial tables found")
    else:
        print("[1/3] No PDF provided — skipping table extraction")

    # Step 2: Consensus data (async)
    print(f"[2/3] Fetching consensus for {ticker}...")
    expectation = await get_expectation_data(ticker, consensus_api_key)
    print(f"      → Source: {expectation.source}")
    if expectation.eps_estimate:
        print(f"      → EPS estimate: {expectation.eps_estimate:.2f}")
    if expectation.revenue_estimate:
        print(f"      → Revenue estimate: {expectation.revenue_estimate:.0f}M")

    # Step 3: Transcript analysis
    transcript = _load_transcript(transcript_path)
    if not transcript:
        print("[3/3] No transcript provided — skipping LLM analysis")
        return CopilotReport(
            ticker=ticker,
            quarter=quarter,
            tables=tables,
            expectation_data=expectation,
            analysis=None,
            processing_seconds=time.time() - t0,
        )

    print(f"[3/3] Analyzing transcript ({len(transcript):,} chars)...")
    ctx = PromptContext(
        ticker=ticker,
        company_name=company_name,
        quarter=quarter,
        eps_estimate=expectation.eps_estimate,
        revenue_estimate_millions=expectation.revenue_estimate,
        transcript=transcript,
        prior_quarter_tone=prior_quarter_tone,
    )
    analysis = analyze_earnings_call(ctx, api_key=anthropic_api_key)

    elapsed = time.time() - t0
    print(f"\n✓ Done in {elapsed:.1f}s")
    print(f"  Verdict: {analysis.one_line_verdict}")

    return CopilotReport(
        ticker=ticker,
        quarter=quarter,
        tables=tables,
        expectation_data=expectation,
        analysis=analysis,
        processing_seconds=elapsed,
    )


def run(
    ticker: str,
    company_name: str,
    quarter: str,
    pdf_path: Optional[str] = None,
    transcript_path: Optional[str] = None,
    consensus_api_key: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
) -> CopilotReport:
    """Sync wrapper for use outside async contexts."""
    return asyncio.run(
        run_pipeline(
            ticker=ticker,
            company_name=company_name,
            quarter=quarter,
            pdf_path=pdf_path,
            transcript_path=transcript_path,
            consensus_api_key=consensus_api_key,
            anthropic_api_key=anthropic_api_key,
        )
    )
