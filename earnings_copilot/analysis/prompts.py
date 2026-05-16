"""
Earnings call prompt system — five specialized templates.

Design principles:
1. Each template has a single responsibility (not one mega-prompt)
2. All outputs are structured JSON — no prose parsing
3. Chain-of-thought is internal (reasoning field) — not shown to user
4. Context injection is explicit, never implicit
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PromptContext:
    ticker: str
    company_name: str
    quarter: str                      # e.g. "Q1 FY2026"
    eps_estimate: Optional[float]
    revenue_estimate_millions: Optional[float]
    transcript: str
    prior_quarter_tone: Optional[str] = None   # for trend comparison


# ── Template 1: Core Summary ──────────────────────────────────────────────────

SUMMARY_TEMPLATE = """\
You are a senior equity analyst reading an earnings call transcript.

<context>
Company: {company_name} ({ticker})
Quarter: {quarter}
EPS Consensus Estimate: {eps_estimate}
Revenue Consensus Estimate: {revenue_estimate_millions}M USD
</context>

<transcript>
{transcript}
</transcript>

Extract a structured summary. Return ONLY valid JSON matching this schema exactly:

{{
  "headline": "<one sharp sentence capturing the most important takeaway>",
  "eps_actual": <float or null>,
  "revenue_actual_millions": <float or null>,
  "eps_gap_pct": <positive = beat, negative = miss, null if no estimate>,
  "revenue_gap_pct": <positive = beat, negative = miss, null if no estimate>,
  "yoy_revenue_growth_pct": <float or null — revenue YoY growth % as stated or implied>,
  "gross_margin_pct": <float or null — current quarter gross margin %, non-GAAP preferred>,
  "next_quarter_gross_margin_pct": <float or null — guided gross margin for next quarter, if mentioned>,
  "segments": [
    {{
      "name": "<segment name, e.g. 'Data Center', 'Client', 'Gaming'>",
      "revenue_millions": <float>,
      "yoy_pct": <float or null — YoY growth %>
    }}
  ],
  "guidance": {{
    "next_quarter_revenue_millions": <float or null>,
    "next_quarter_eps": <float or null>,
    "full_year_revenue_millions": <float or null>,
    "full_year_eps": <float or null>,
    "vs_consensus": "<above|in-line|below|withdrawn|not_given>",
    "guidance_note": "<one sentence on what changed or was surprising>"
  }},
  "key_points": [
    "<most important point>",
    "<second most important>",
    "<third>"
  ],
  "one_line_verdict": "<institutional-grade one-liner: e.g. 'Beat on EPS, miss on revenue, guidance cut — net negative'>"
}}

Notes:
- segments: include ALL business segments mentioned with revenue figures; use [] if none disclosed
- gross_margin_pct: extract the exact figure stated; do not estimate
- yoy_revenue_growth_pct: use the figure stated by management, not your calculation"""


# ── Template 2: Management Tone Analysis ─────────────────────────────────────

TONE_TEMPLATE = """\
You are a behavioral finance analyst specializing in management communication signals.

<context>
Company: {company_name} ({ticker}) — {quarter}
{prior_quarter_note}
</context>

<transcript>
{transcript}
</transcript>

Analyze management tone and communication signals. Think step by step internally,
then return ONLY valid JSON:

{{
  "tone": "<bullish|neutral|cautious|defensive>",
  "tone_score": <integer 1-10, where 1=very defensive, 10=very confident>,
  "reasoning": "<2-3 sentences explaining the score based on specific language observed>",
  "hedging_signals": [
    "<specific hedging phrase observed, e.g. 'we hope to achieve'>",
    "<another example>"
  ],
  "confidence_signals": [
    "<specific confident phrase, e.g. 'we expect to exceed'>",
    "<another example>"
  ],
  "notable_language_changes": "<compared to last quarter if prior_quarter_tone provided, else null>",
  "ceo_vs_cfo_alignment": "<aligned|misaligned|unclear> — CFO hedging more than CEO is a red flag"
}}"""


# ── Template 3: Key Themes ────────────────────────────────────────────────────

THEMES_TEMPLATE = """\
You are a thematic research analyst. Identify the dominant strategic and operational
themes management emphasized in this earnings call.

<context>
Company: {company_name} ({ticker}) — {quarter}
</context>

<transcript>
{transcript}
</transcript>

Return ONLY valid JSON:

{{
  "themes": [
    {{
      "name": "<theme name, 3-6 words>",
      "importance": "<high|medium|low>",
      "management_emphasis": "<how many times / how strongly it was mentioned>",
      "investor_relevance": "<why this matters to investors in one sentence>",
      "sentiment": "<positive|neutral|negative>"
    }}
  ],
  "primary_narrative": "<the single story management is trying to tell this quarter, in one sentence>",
  "narrative_vs_results": "<consistent|partially_consistent|contradicted — does the narrative match the numbers?>"
}}

Order themes by importance descending. Include 3-7 themes."""


# ── Template 4: Risk Factors ──────────────────────────────────────────────────

RISK_TEMPLATE = """\
You are a risk analyst reviewing forward-looking statements in an earnings call.

<context>
Company: {company_name} ({ticker}) — {quarter}
</context>

<transcript>
{transcript}
</transcript>

Extract all risk factors mentioned or implied. Return ONLY valid JSON:

{{
  "risks": [
    {{
      "category": "<macro|competitive|execution|regulatory|financial|geopolitical|other>",
      "description": "<specific risk in one sentence>",
      "severity": "<high|medium|low>",
      "is_new": <true if not mentioned in prior quarters, false if recurring>,
      "management_acknowledged": <true if explicitly discussed, false if implied>,
      "direct_quote": "<exact quote from transcript if available, else null>"
    }}
  ],
  "biggest_new_risk": "<name the single most important new risk, or null>",
  "risk_trend": "<increasing|stable|decreasing — vs. typical quarter for this company>"
}}

Include risks even if management downplayed them. Flag discrepancy between
management tone and actual risk severity."""


# ── Template 5: Q&A Analysis ──────────────────────────────────────────────────

QA_TEMPLATE = """\
You are an analyst tracking what sell-side analysts push on versus what management
deflects. This is often where the real signal is.

<context>
Company: {company_name} ({ticker}) — {quarter}
</context>

<transcript>
{transcript}
</transcript>

Analyze the Q&A section only. Return ONLY valid JSON:

{{
  "questions": [
    {{
      "analyst_firm": "<firm name or 'Unknown'>",
      "question_summary": "<core question in one sentence>",
      "topic": "<guidance|margin|competition|growth|macro|capital_allocation|other>",
      "directness_score": <1-5, where 5=management fully answered, 1=complete deflection>,
      "evasion_signals": ["<specific evasion tactic, e.g. 'redirected to non-GAAP'>"],
      "answer_summary": "<what management actually said in one sentence>"
    }}
  ],
  "tension_areas": [
    "<topic where multiple analysts pushed on the same thing>",
    "<another tension area>"
  ],
  "most_avoided_topic": "<the question management most clearly didn't want to answer>",
  "analyst_sentiment": "<bullish|neutral|bearish — based on tone and follow-up aggressiveness>"
}}"""


# ── Builder ───────────────────────────────────────────────────────────────────

def build_summary_prompt(ctx: PromptContext) -> str:
    return SUMMARY_TEMPLATE.format(
        company_name=ctx.company_name,
        ticker=ctx.ticker,
        quarter=ctx.quarter,
        eps_estimate=ctx.eps_estimate if ctx.eps_estimate is not None else "N/A",
        revenue_estimate_millions=ctx.revenue_estimate_millions if ctx.revenue_estimate_millions is not None else "N/A",
        transcript=ctx.transcript,
    )


def build_tone_prompt(ctx: PromptContext) -> str:
    prior = (
        f"Prior quarter tone for comparison: {ctx.prior_quarter_tone}"
        if ctx.prior_quarter_tone
        else "No prior quarter tone available for comparison."
    )
    return TONE_TEMPLATE.format(
        company_name=ctx.company_name,
        ticker=ctx.ticker,
        quarter=ctx.quarter,
        prior_quarter_note=prior,
        transcript=ctx.transcript,
    )


def build_themes_prompt(ctx: PromptContext) -> str:
    return THEMES_TEMPLATE.format(
        company_name=ctx.company_name,
        ticker=ctx.ticker,
        quarter=ctx.quarter,
        transcript=ctx.transcript,
    )


def build_risk_prompt(ctx: PromptContext) -> str:
    return RISK_TEMPLATE.format(
        company_name=ctx.company_name,
        ticker=ctx.ticker,
        quarter=ctx.quarter,
        transcript=ctx.transcript,
    )


def build_qa_prompt(ctx: PromptContext) -> str:
    return QA_TEMPLATE.format(
        company_name=ctx.company_name,
        ticker=ctx.ticker,
        quarter=ctx.quarter,
        transcript=ctx.transcript,
    )
