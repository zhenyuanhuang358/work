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
- Quantify ALL claims: margins, growth rates, multiples, dollar figures
- If historical_quarters data is provided, MUST analyze multi-quarter trends explicitly
- Comment on whether current margins/growth represent acceleration or deceleration vs. trend
- Highlight any inflection points in the historical data

Structure your memo with these exact sections:

## Executive Summary
One paragraph. The single most important takeaway for an investor. Lead with the number that matters most.

## Key Financial Metrics
Markdown table: Metric | This Quarter | Prior Quarter | Year Ago | YoY Change

## Revenue & Margin Trend
If historical data provided: 2 paragraphs analyzing the trajectory over 6-8 quarters.
Call out: Is growth accelerating or decelerating? Are margins expanding or compressing?
What does the trend imply about the business model at scale?

## Earnings Highlights
2-3 paragraphs. What drove results. Segment breakdown with specific revenue and growth figures.
Which segments surprised? Which disappointed?

## Guidance Analysis
1-2 paragraphs. Management's forward outlook. Is guidance conservative (vs. history of beats)?
What is the implied sequential growth? What assumptions underpin it?

## Balance Sheet & Cash Flow
1 paragraph. FCF conversion, cash position, debt load, capital return activity.

## Risks
Paragraph form. Top 3 risks: macro, competitive, execution. Be specific and quantify where possible.

## Valuation Commentary
1 paragraph. Current P/E, EV/Revenue, EV/EBITDA vs. peers and vs. own history.
Is the stock cheap or expensive relative to its growth rate (PEG ratio implied)?

## Investment Thesis

**Bull Case:** [specific catalyst + % upside with rationale]

**Base Case:** [central scenario + expected 12-month return]

**Bear Case:** [downside scenario + % drawdown risk]

**Recommendation:** [Clear BUY / HOLD / SELL with one-sentence rationale and key metric to watch]

---

Financial Data:
{metrics}

Management Tone Analysis:
{tone}

Company Context (including historical quarters if available):
{context}"""
