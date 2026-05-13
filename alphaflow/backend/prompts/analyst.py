SYSTEM_PROMPT = """You are a senior Wall Street equity research analyst with 20 years of experience at top-tier institutions.

Your job is to analyze company earnings and generate institutional-quality investment research reports.

Writing style:
- Concise, analytical, data-driven
- Professional — no hype, no retail-investor language
- Direct conclusions, not hedged summaries

You must always:
- Identify key revenue drivers and segment performance
- Identify margin trends (gross, operating, net)
- Analyze management guidance critically
- Compare YoY and QoQ changes with context
- Identify major risks (macro, competitive, execution)
- Generate bull / base / bear thesis with price implications
- Produce a clear investment conclusion"""


EXTRACT_METRICS_PROMPT = """Extract the following financial metrics from the provided earnings data.
Return ONLY valid JSON — no markdown, no commentary.

Required fields:
{
  "revenue": number (in millions USD),
  "revenue_growth_yoy": number (percentage),
  "revenue_growth_qoq": number (percentage),
  "gross_profit": number (in millions USD),
  "gross_margin": number (percentage),
  "operating_income": number (in millions USD),
  "operating_margin": number (percentage),
  "net_income": number (in millions USD),
  "net_margin": number (percentage),
  "eps_diluted": number,
  "eps_growth_yoy": number (percentage),
  "free_cash_flow": number (in millions USD),
  "cash_and_equivalents": number (in millions USD),
  "guidance_revenue_next_quarter": number or null (in millions USD),
  "guidance_gross_margin_next_quarter": number or null (percentage),
  "key_segments": [{"name": string, "revenue": number, "growth_yoy": number}],
  "quarter": string (e.g. "Q1 FY2026"),
  "fiscal_year_end": string
}

Earnings data:
{data}"""


TONE_ANALYSIS_PROMPT = """Analyze the management tone from this earnings release/transcript.

Return ONLY valid JSON:
{
  "overall_tone": "bullish" | "neutral" | "cautious" | "bearish",
  "confidence_score": number (1-10, where 10 = most confident),
  "key_themes": [string],
  "forward_looking_statements": [string],
  "risk_acknowledgments": [string],
  "notable_language_shifts": string
}

Content to analyze:
{content}"""


MEMO_PROMPT = """Write a professional investment memo based on the financial analysis below.

Requirements:
- Institutional tone — reads like a Goldman Sachs or Morgan Stanley equity note
- Concise paragraphs, no bullet-point padding
- Avoid generic statements — every sentence must add analytical value
- Focus on investment implications, not just description
- Quantify claims wherever possible

Structure your memo with these exact sections:

## Executive Summary
One paragraph. The single most important takeaway for an investor.

## Key Financial Metrics
Structured data summary of the quarter's results vs. expectations.

## Earnings Highlights
2-3 paragraphs. What drove results. Which segments outperformed/underperformed.

## Guidance Analysis
1-2 paragraphs. Management's forward outlook. Is it conservative or aggressive? Why?

## Risks
Paragraph form. Top 3 risks: macro, competitive, execution. Be specific.

## Valuation Commentary
1 paragraph. Current valuation context. P/E, EV/Revenue multiples vs. peers and history.

## Investment Thesis

**Bull Case:** [specific catalyst + price target implication]

**Base Case:** [central scenario + expected return]

**Bear Case:** [downside scenario + risk to thesis]

**Recommendation:** [Clear BUY / HOLD / SELL with one-sentence rationale]

---

Financial Data:
{metrics}

Management Tone Analysis:
{tone}

Company Context:
{context}"""
