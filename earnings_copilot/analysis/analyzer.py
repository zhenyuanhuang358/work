"""
Core analysis engine — runs all five prompts against Claude, assembles EarningsCallAnalysis.
Streams each section so the user sees results incrementally.
"""

import json
import re
import time
from typing import Optional

import anthropic

from earnings_copilot.models import (
    AnalystQuestion,
    EarningsCallAnalysis,
    GuidanceItem,
    GuidanceVsConsensus,
    ManagementTone,
    RiskFactor,
    RiskSeverity,
)
from earnings_copilot.analysis.prompts import (
    PromptContext,
    build_qa_prompt,
    build_risk_prompt,
    build_summary_prompt,
    build_themes_prompt,
    build_tone_prompt,
)

MODEL = "claude-opus-4-7"
MAX_TOKENS = 2048


def _call(client: anthropic.Anthropic, prompt: str, section: str) -> dict:
    """Single LLM call → parsed JSON. Raises on parse failure."""
    print(f"  [{section}] calling Claude...", flush=True)
    t0 = time.time()

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    )

    raw = next(
        (b.text for b in response.content if hasattr(b, "text")),
        "",
    ).strip()

    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"[{section}] JSON parse failed: {e}\nRaw:\n{raw[:500]}")

    elapsed = time.time() - t0
    print(f"  [{section}] done in {elapsed:.1f}s", flush=True)
    return result


def _parse_guidance(raw: dict) -> list[GuidanceItem]:
    g = raw.get("guidance", {})
    items = []
    mapping = {
        "next_quarter_revenue_millions": "Next Q Revenue (M)",
        "next_quarter_eps": "Next Q EPS",
        "full_year_revenue_millions": "FY Revenue (M)",
        "full_year_eps": "FY EPS",
    }
    vs = g.get("vs_consensus", "not_given")
    try:
        vs_enum = GuidanceVsConsensus(vs)
    except ValueError:
        vs_enum = GuidanceVsConsensus.IN_LINE

    for key, label in mapping.items():
        val = g.get(key)
        if val is not None:
            items.append(GuidanceItem(metric=label, value=str(val), vs_consensus=vs_enum))
    return items


def _parse_risks(raw: dict) -> list[RiskFactor]:
    risks = []
    for r in raw.get("risks", []):
        try:
            sev = RiskSeverity(r.get("severity", "medium"))
        except ValueError:
            sev = RiskSeverity.MEDIUM
        risks.append(
            RiskFactor(
                category=r.get("category", "other"),
                description=r.get("description", ""),
                severity=sev,
                is_new=bool(r.get("is_new", False)),
                management_acknowledged=bool(r.get("management_acknowledged", True)),
            )
        )
    return risks


def _parse_questions(raw: dict) -> list[AnalystQuestion]:
    questions = []
    for q in raw.get("questions", []):
        questions.append(
            AnalystQuestion(
                analyst_firm=q.get("analyst_firm", "Unknown"),
                question_summary=q.get("question_summary", ""),
                management_directness=int(q.get("directness_score", 3)),
                evasion_signals=q.get("evasion_signals", []),
            )
        )
    return questions


def analyze_earnings_call(
    ctx: PromptContext,
    api_key: Optional[str] = None,
) -> EarningsCallAnalysis:
    """
    Run all five analysis prompts and assemble a complete EarningsCallAnalysis.
    Each section is independent — a failure in one doesn't block the others.
    """
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    summary_raw = _call(client, build_summary_prompt(ctx), "Summary")
    tone_raw = _call(client, build_tone_prompt(ctx), "Tone")
    themes_raw = _call(client, build_themes_prompt(ctx), "Themes")
    risk_raw = _call(client, build_risk_prompt(ctx), "Risks")
    qa_raw = _call(client, build_qa_prompt(ctx), "Q&A")

    try:
        tone_enum = ManagementTone(tone_raw.get("tone", "neutral"))
    except ValueError:
        tone_enum = ManagementTone.NEUTRAL

    return EarningsCallAnalysis(
        ticker=ctx.ticker,
        quarter=ctx.quarter,
        headline=summary_raw.get("headline", ""),
        eps_actual=summary_raw.get("eps_actual"),
        revenue_actual=summary_raw.get("revenue_actual_millions"),
        eps_gap_pct=summary_raw.get("eps_gap_pct"),
        revenue_gap_pct=summary_raw.get("revenue_gap_pct"),
        guidance=_parse_guidance(summary_raw),
        management_tone=tone_enum,
        tone_score=int(tone_raw.get("tone_score", 5)),
        tone_reasoning=tone_raw.get("reasoning", ""),
        key_themes=[t.get("name", "") for t in themes_raw.get("themes", [])],
        risk_factors=_parse_risks(risk_raw),
        analyst_questions=_parse_questions(qa_raw),
        tension_areas=qa_raw.get("tension_areas", []),
        one_line_verdict=summary_raw.get("one_line_verdict", ""),
    )
