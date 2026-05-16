"""
Merlin analysis engine — runs all five consulting prompts, assembles MerlinAnalysis.
"""

import json
import re
import time
from typing import Optional

import anthropic

from merlin.models import (
    CoreIssue,
    InterviewQuestion,
    MerlinAnalysis,
    RiskItem,
)
from merlin.prompts import (
    MerlinContext,
    build_brief_prompt,
    build_issues_prompt,
    build_qa_prompt,
    build_risk_prompt,
    build_strategy_prompt,
)

MODEL = "claude-opus-4-7"
MAX_TOKENS = 4096


def _call(client: anthropic.Anthropic, prompt: str, section: str) -> dict:
    print(f"  [{section}] calling Claude...", flush=True)
    t0 = time.time()

    create_kwargs: dict = dict(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    if "opus" in MODEL or "sonnet-4-6" in MODEL:
        create_kwargs["thinking"] = {"type": "adaptive"}

    response = client.messages.create(**create_kwargs)

    raw = next(
        (b.text for b in response.content if hasattr(b, "text")),
        "",
    ).strip()

    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    def extract_json(s: str) -> dict:
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        start = s.find("{")
        if start == -1:
            raise ValueError("No JSON object found")
        depth, in_str, escape = 0, False, False
        for i, ch in enumerate(s[start:], start):
            if escape:
                escape = False
                continue
            if ch == "\\" and in_str:
                escape = True
                continue
            if ch == '"' and not escape:
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(s[start : i + 1])
        raise ValueError("Unbalanced JSON braces")

    try:
        result = extract_json(raw)
    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"[{section}] JSON parse failed: {e}\nRaw:\n{raw[:500]}")

    elapsed = time.time() - t0
    print(f"  [{section}] done in {elapsed:.1f}s", flush=True)
    return result


def _parse_issues(raw: dict) -> list[CoreIssue]:
    issues = []
    for item in raw.get("core_issues", []):
        issues.append(CoreIssue(
            title=item.get("title", ""),
            why_it_matters=item.get("why_it_matters", ""),
            evidence=item.get("evidence", ""),
            impact=int(item.get("impact", 3)),
            certainty=int(item.get("certainty", 3)),
        ))
    return issues


def _parse_risks(raw: dict) -> list[RiskItem]:
    risks = []
    for item in raw.get("risks", []):
        risks.append(RiskItem(
            category=item.get("category", "other"),
            description=item.get("description", ""),
            contradiction=item.get("contradiction", ""),
            verification_question=item.get("verification_question", ""),
            severity=item.get("severity", "medium"),
        ))
    return risks


def _parse_questions(raw: dict) -> list[InterviewQuestion]:
    questions = []
    for item in raw.get("questions", []):
        questions.append(InterviewQuestion(
            question=item.get("question", ""),
            purpose=item.get("purpose", ""),
            follow_ups=item.get("follow_ups", []),
            evasion_signal=item.get("evasion_signal", ""),
            breakthrough=item.get("breakthrough", ""),
            priority=int(item.get("priority", 99)),
        ))
    questions.sort(key=lambda q: q.priority)
    return questions


def analyze(
    ctx: MerlinContext,
    api_key: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> MerlinAnalysis:
    if auth_token:
        client = anthropic.Anthropic(auth_token=auth_token)
    elif api_key:
        client = anthropic.Anthropic(api_key=api_key)
    else:
        client = anthropic.Anthropic()

    brief_raw = _call(client, build_brief_prompt(ctx), "Brief")
    issues_raw = _call(client, build_issues_prompt(ctx), "Issues")
    risk_raw = _call(client, build_risk_prompt(ctx), "Risks")
    qa_raw = _call(client, build_qa_prompt(ctx), "Questions")
    strategy_raw = _call(client, build_strategy_prompt(ctx), "Strategy")

    return MerlinAnalysis(
        company_name=ctx.company_name,
        meeting_purpose=ctx.meeting_purpose,
        company_overview=brief_raw.get("company_overview", ""),
        recent_events=brief_raw.get("recent_events", []),
        key_metrics=brief_raw.get("key_metrics", []),
        strategic_narrative=brief_raw.get("strategic_narrative", ""),
        context_gaps=brief_raw.get("context_gaps", ""),
        core_issues=_parse_issues(issues_raw),
        risks=_parse_risks(risk_raw),
        questions=_parse_questions(qa_raw),
        central_hypothesis=strategy_raw.get("central_hypothesis", ""),
        opening_strategy=strategy_raw.get("opening_strategy", ""),
        key_themes=strategy_raw.get("key_themes", []),
        confidence_score=int(strategy_raw.get("confidence_score", 5)),
        confidence_reasoning=strategy_raw.get("confidence_reasoning", ""),
    )
