"""
Merlin Research Mode — four-agent execution engine.

Orchestrator → Scout (web_search) → Analyst + Forensic (parallel) → Strategist
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional

import anthropic

from merlin.research_prompts import (
    ResearchContext,
    build_analyst_prompt,
    build_forensic_prompt,
    build_orchestrator_prompt,
    build_scout_prompt,
    build_strategist_prompt,
)

MODEL = "claude-opus-4-7"
MAX_TOKENS = 4096


@dataclass
class ResearchResult:
    company_name: str
    outline_text: str
    sections: list          # orchestrator output
    findings: list          # scout output
    analysis: list          # analyst output
    red_flags: list         # forensic output
    overall_integrity: str
    answers: list           # strategist output
    executive_summary: str
    data_verdict: str


def _extract_json(s: str) -> dict:
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


def _clean(raw: str) -> str:
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    return re.sub(r"\s*```$", "", raw)


def _call_plain(client: anthropic.Anthropic, prompt: str, label: str) -> dict:
    """Plain LLM call with adaptive thinking, no tools."""
    print(f"  [{label}] calling...", flush=True)
    t0 = time.time()
    kwargs = dict(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    if "opus" in MODEL or "sonnet-4-6" in MODEL:
        kwargs["thinking"] = {"type": "adaptive"}
    response = client.messages.create(**kwargs)
    raw = next((b.text for b in response.content if hasattr(b, "text")), "").strip()
    result = _extract_json(_clean(raw))
    print(f"  [{label}] done in {time.time()-t0:.1f}s", flush=True)
    return result


def _call_scout(client: anthropic.Anthropic, prompt: str) -> dict:
    """Scout call with web_search tool enabled."""
    print("  [Scout] searching...", flush=True)
    t0 = time.time()

    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}]
    messages = [{"role": "user", "content": prompt}]

    # Agentic loop: keep going until stop_reason is end_turn or no more tool calls
    while True:
        kwargs = dict(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            tools=tools,
            messages=messages,
        )
        # thinking not compatible with tool use loop in same turn; skip here
        response = client.messages.create(**kwargs)

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        # Handle tool use blocks
        tool_results = []
        has_tool_use = False
        for block in response.content:
            if block.type == "tool_use":
                has_tool_use = True
                # web_search results are provided automatically by Anthropic's server-side tool
                # They come back as tool_result blocks in the next turn
                # We just need to acknowledge them
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Search executed by server.",
                })

        if not has_tool_use:
            break

        messages.append({"role": "user", "content": tool_results})

    # Extract final text from last assistant message
    final_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_text += block.text

    result = _extract_json(_clean(final_text))
    print(f"  [Scout] done in {time.time()-t0:.1f}s", flush=True)
    return result


def run_research(
    ctx: ResearchContext,
    api_key: Optional[str] = None,
    auth_token: Optional[str] = None,
) -> ResearchResult:
    if auth_token:
        client = anthropic.Anthropic(auth_token=auth_token)
    elif api_key:
        client = anthropic.Anthropic(api_key=api_key)
    else:
        client = anthropic.Anthropic()

    # Phase 1: Orchestrator — parse and classify the outline
    print("\n[Phase 1] Orchestrator parsing outline...", flush=True)
    orch_raw = _call_plain(client, build_orchestrator_prompt(ctx), "Orchestrator")
    sections = orch_raw.get("sections", [])
    sections_json = json.dumps(sections, ensure_ascii=False, indent=2)

    # Phase 2: Scout — web search per section
    print("\n[Phase 2] Scout gathering intelligence...", flush=True)
    scout_raw = _call_scout(client, build_scout_prompt(ctx, sections_json))
    findings = scout_raw.get("findings", [])
    findings_json = json.dumps(findings, ensure_ascii=False, indent=2)

    # Phase 3: Analyst + Forensic in parallel
    print("\n[Phase 3] Analyst + Forensic running in parallel...", flush=True)
    analyst_result, forensic_result = {}, {}

    def run_analyst():
        return _call_plain(client, build_analyst_prompt(ctx, findings_json), "Analyst")

    def run_forensic():
        # Forensic needs findings but not analysis yet — run with empty analysis
        return _call_plain(
            client,
            build_forensic_prompt(ctx, findings_json, "[]"),
            "Forensic",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(run_analyst): "analyst",
            pool.submit(run_forensic): "forensic",
        }
        for future in as_completed(futures):
            label = futures[future]
            result = future.result()
            if label == "analyst":
                analyst_result = result
            else:
                forensic_result = result

    analysis = analyst_result.get("analysis", [])
    red_flags = forensic_result.get("red_flags", [])
    overall_integrity = forensic_result.get("overall_integrity", "medium")
    analysis_json = json.dumps(analysis, ensure_ascii=False, indent=2)
    forensic_json = json.dumps({"red_flags": red_flags}, ensure_ascii=False, indent=2)

    # Phase 4: Strategist — synthesize and write final answers
    print("\n[Phase 4] Strategist synthesizing...", flush=True)
    strategy_raw = _call_plain(
        client,
        build_strategist_prompt(ctx, findings_json, analysis_json, forensic_json),
        "Strategist",
    )

    return ResearchResult(
        company_name=ctx.company_name,
        outline_text=ctx.outline_text,
        sections=sections,
        findings=findings,
        analysis=analysis,
        red_flags=red_flags,
        overall_integrity=overall_integrity,
        answers=strategy_raw.get("answers", []),
        executive_summary=strategy_raw.get("executive_summary", ""),
        data_verdict=strategy_raw.get("data_verdict", ""),
    )
