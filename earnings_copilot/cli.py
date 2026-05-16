"""
Earnings Copilot CLI.

Usage:
  python -m earnings_copilot.cli --ticker AAPL --company "Apple Inc." --quarter "Q1 FY2025" \
    --pdf /path/to/report.pdf --transcript /path/to/call.txt
"""

import argparse
import json
import os
from dataclasses import asdict

from earnings_copilot.pipeline import run


def main():
    parser = argparse.ArgumentParser(description="Earnings Copilot — AI-powered earnings analysis")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--quarter", required=True, help='e.g. "Q1 FY2026"')
    parser.add_argument("--pdf", default=None, help="Path to earnings report PDF")
    parser.add_argument("--transcript", default=None, help="Path to earnings call transcript .txt")
    parser.add_argument("--consensus-key", default=None, help="ConsensusData API key (optional)")
    parser.add_argument("--output", default=None, help="Write JSON report to this file")
    args = parser.parse_args()

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    report = run(
        ticker=args.ticker,
        company_name=args.company,
        quarter=args.quarter,
        pdf_path=args.pdf,
        transcript_path=args.transcript,
        consensus_api_key=args.consensus_key,
        anthropic_api_key=anthropic_key,
    )

    output = {
        "ticker": report.ticker,
        "quarter": report.quarter,
        "processing_seconds": round(report.processing_seconds, 1),
        "tables_extracted": len(report.tables),
        "expectation_data": {
            "eps_estimate": report.expectation_data.eps_estimate,
            "revenue_estimate_millions": report.expectation_data.revenue_estimate,
            "source": report.expectation_data.source,
        },
    }

    if report.analysis:
        a = report.analysis
        output["analysis"] = {
            "headline": a.headline,
            "verdict": a.one_line_verdict,
            "eps_actual": a.eps_actual,
            "revenue_actual_millions": a.revenue_actual,
            "eps_gap_pct": a.eps_gap_pct,
            "revenue_gap_pct": a.revenue_gap_pct,
            "tone": a.management_tone.value,
            "tone_score": a.tone_score,
            "tone_reasoning": a.tone_reasoning,
            "themes": a.key_themes,
            "tension_areas": a.tension_areas,
            "risks": [
                {"category": r.category, "description": r.description, "severity": r.severity.value, "new": r.is_new}
                for r in a.risk_factors
            ],
        }

    json_str = json.dumps(output, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"\nReport written to {args.output}")
    else:
        print("\n" + "=" * 60)
        print(json_str)


if __name__ == "__main__":
    main()
