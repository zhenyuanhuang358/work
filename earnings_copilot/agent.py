"""
Earnings Copilot — Tool-Use Agent

Unlike the deterministic pipeline (pipeline.py), this agent lets Claude decide:
- which tools to call and in what order
- whether to skip steps when data is unavailable
- how to handle partial data gracefully

Tool loop: Claude → tool call → execute → Claude → ... → final text answer
"""

import asyncio
import json
from typing import Optional

import anthropic

from earnings_copilot.data.consensus import get_expectation_data
from earnings_copilot.analysis.prompts import PromptContext
from earnings_copilot.analysis.analyzer import analyze_earnings_call

# ── Tool definitions (JSON Schema) ────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "fetch_consensus_data",
        "description": (
            "Fetch Wall Street analyst consensus EPS and revenue estimates for a stock ticker. "
            "Uses three-tier fallback: paid API → yfinance → LLM estimate. "
            "Always call this first before analyzing results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "analyze_earnings_transcript",
        "description": (
            "Run five-dimensional LLM analysis on an earnings call transcript: "
            "summary, management tone (1-10 score), key themes, risk factors, and Q&A tension analysis. "
            "Requires the raw transcript text. Pass eps_estimate and revenue_estimate if available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker":                   {"type": "string"},
                "company_name":             {"type": "string"},
                "quarter":                  {"type": "string", "description": "e.g. Q1 FY2026"},
                "transcript":               {"type": "string", "description": "Full earnings call transcript text"},
                "eps_estimate":             {"type": "number", "description": "Analyst consensus EPS estimate"},
                "revenue_estimate_millions":{"type": "number", "description": "Analyst consensus revenue estimate in millions USD"},
            },
            "required": ["ticker", "company_name", "quarter", "transcript"],
        },
    },
    {
        "name": "calculate_expectation_gap",
        "description": (
            "Calculate the beat/miss percentage for EPS and revenue given actual and estimated values. "
            "Returns gap percentages and a plain-English verdict."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "eps_actual":               {"type": "number"},
                "eps_estimate":             {"type": "number"},
                "revenue_actual_millions":  {"type": "number"},
                "revenue_estimate_millions":{"type": "number"},
            },
            "required": ["eps_actual", "revenue_actual_millions"],
        },
    },
]


# ── Tool executor ─────────────────────────────────────────────────────────────

async def _execute_tool(name: str, inputs: dict, anthropic_client: anthropic.Anthropic) -> str:
    """Route tool call to implementation, return JSON string result."""

    if name == "fetch_consensus_data":
        ticker = inputs["ticker"]
        exp = await get_expectation_data(ticker)
        return json.dumps({
            "ticker":                   exp.ticker,
            "eps_estimate":             exp.eps_estimate,
            "revenue_estimate_millions":exp.revenue_estimate,
            "source":                   exp.source,
            "error":                    exp.error,
        })

    elif name == "analyze_earnings_transcript":
        ctx = PromptContext(
            ticker=inputs["ticker"],
            company_name=inputs["company_name"],
            quarter=inputs["quarter"],
            eps_estimate=inputs.get("eps_estimate"),
            revenue_estimate_millions=inputs.get("revenue_estimate_millions"),
            transcript=inputs["transcript"],
        )
        # analyze_earnings_call is sync; run in thread to not block event loop
        loop = asyncio.get_event_loop()
        analysis = await loop.run_in_executor(
            None,
            lambda: analyze_earnings_call(ctx, api_key=anthropic_client.api_key),
        )
        return json.dumps({
            "headline":         analysis.headline,
            "eps_actual":       analysis.eps_actual,
            "revenue_actual":   analysis.revenue_actual,
            "eps_gap_pct":      analysis.eps_gap_pct,
            "revenue_gap_pct":  analysis.revenue_gap_pct,
            "tone":             analysis.management_tone.value,
            "tone_score":       analysis.tone_score,
            "tone_reasoning":   analysis.tone_reasoning,
            "key_themes":       analysis.key_themes,
            "tension_areas":    analysis.tension_areas,
            "top_risks": [
                {"category": r.category, "severity": r.severity.value, "description": r.description}
                for r in analysis.risk_factors[:5]
            ],
            "one_line_verdict": analysis.one_line_verdict,
        })

    elif name == "calculate_expectation_gap":
        eps_act  = inputs.get("eps_actual")
        eps_est  = inputs.get("eps_estimate")
        rev_act  = inputs.get("revenue_actual_millions")
        rev_est  = inputs.get("revenue_estimate_millions")

        eps_gap = round((eps_act - eps_est) / abs(eps_est) * 100, 2) if eps_est else None
        rev_gap = round((rev_act - rev_est) / abs(rev_est) * 100, 2) if rev_est else None

        def verdict(gap):
            if gap is None: return "N/A"
            if gap > 3:  return f"Beat by {gap:.1f}%"
            if gap < -3: return f"Missed by {abs(gap):.1f}%"
            return f"In-line ({gap:+.1f}%)"

        return json.dumps({
            "eps_gap_pct":     eps_gap,
            "revenue_gap_pct": rev_gap,
            "eps_verdict":     verdict(eps_gap),
            "revenue_verdict": verdict(rev_gap),
        })

    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


# ── Agent loop ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are Earnings Copilot, an institutional-grade earnings analysis agent.

Your job: given a user's request about a company's earnings, orchestrate the
available tools to produce a complete, structured analysis.

Workflow:
1. fetch_consensus_data — always start here to get analyst estimates
2. analyze_earnings_transcript — if a transcript is available
3. calculate_expectation_gap — compute beat/miss with actual numbers
4. Synthesize a final written verdict: headline + EPS/revenue gap + tone assessment + top risks

Rules:
- Be precise with numbers. Never hallucinate financial figures.
- If a tool returns an error, note it and continue with available data.
- Final answer must be structured: use clear sections.
- Keep the final answer under 400 words.
"""


async def run_agent(
    user_message: str,
    api_key: Optional[str] = None,
    verbose: bool = True,
) -> str:
    """
    Run the Earnings Copilot agent on a user query.
    Returns the agent's final text response.
    """
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if verbose:
            print(f"  [agent] stop_reason={response.stop_reason}", flush=True)

        # Append assistant response to conversation
        messages.append({"role": "assistant", "content": response.content})

        # Done — return final text
        if response.stop_reason == "end_turn":
            return next(
                (b.text for b in response.content if hasattr(b, "text")),
                "",
            )

        # Execute all tool calls in this response
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                if verbose:
                    print(f"  [tool] {block.name}({json.dumps(block.input)[:120]})", flush=True)
                result = await _execute_tool(block.name, block.input, client)
                if verbose:
                    print(f"  [tool] → {result[:200]}", flush=True)
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     result,
                })
            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason
        break

    return "[agent] unexpected stop — no final answer"
