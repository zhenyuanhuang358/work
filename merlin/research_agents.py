"""
Merlin Research Mode — four-agent execution engine.

Orchestrator → Scout (web_search) → Analyst + Forensic (parallel) → Strategist
"""

import json
import re
import time
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
MODEL_LIGHT = "claude-sonnet-4-6"  # Analyst + Forensic: lighter model, less rate pressure
MAX_TOKENS = 4096
MAX_TOKENS_SCOUT = 8192       # Scout: web search results + JSON output
MAX_TOKENS_STRATEGIST = 8192  # Strategist: 11 answers + executive summary
FINDINGS_CAP = 6000           # Max chars of raw findings passed to Analyst/Forensic
FINDINGS_TRUNCATE = 10000     # Max chars passed to Strategist


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
    """Plain LLM call with adaptive thinking, no tools. Retries on rate limit."""
    print(f"  [{label}] calling...", flush=True)
    t0 = time.time()
    kwargs = dict(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    if "opus" in MODEL or "sonnet-4-6" in MODEL:
        kwargs["thinking"] = {"type": "adaptive"}

    wait = 15
    for attempt in range(5):
        try:
            response = client.messages.create(**kwargs)
            break
        except anthropic.RateLimitError:
            if attempt == 4:
                raise
            print(f"  [{label}] rate limited, retrying in {wait}s...", flush=True)
            time.sleep(wait)
            wait *= 2

    raw = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "").strip()
    result = _extract_json(_clean(raw))
    print(f"  [{label}] done in {time.time()-t0:.1f}s", flush=True)
    return result


def _call_light(client: anthropic.Anthropic, prompt: str, label: str) -> dict:
    """Uses MODEL_LIGHT (Sonnet) for Analyst/Forensic — no thinking, larger output budget."""
    print(f"  [{label}] calling...", flush=True)
    t0 = time.time()
    # No thinking here: these are structured extraction tasks, not reasoning-heavy.
    # Thinking eats into max_tokens budget; we need the full budget for JSON output.
    kwargs = dict(
        model=MODEL_LIGHT,
        max_tokens=7000,
        messages=[{"role": "user", "content": prompt}],
    )

    wait = 10
    for attempt in range(5):
        try:
            response = client.messages.create(**kwargs)
            break
        except anthropic.RateLimitError:
            if attempt == 4:
                raise
            print(f"  [{label}] rate limited, retrying in {wait}s...", flush=True)
            time.sleep(wait)
            wait *= 2

    raw = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "").strip()
    result = _extract_json(_clean(raw))
    print(f"  [{label}] done in {time.time()-t0:.1f}s", flush=True)
    return result


def _call_plain_large(client: anthropic.Anthropic, prompt: str, label: str) -> dict:
    """Like _call_plain but with larger token budget for long outputs."""
    print(f"  [{label}] calling...", flush=True)
    t0 = time.time()
    kwargs = dict(
        model=MODEL,
        max_tokens=MAX_TOKENS_STRATEGIST,
        messages=[{"role": "user", "content": prompt}],
    )
    if "opus" in MODEL or "sonnet-4-6" in MODEL:
        kwargs["thinking"] = {"type": "adaptive"}

    wait = 15
    for attempt in range(5):
        try:
            response = client.messages.create(**kwargs)
            break
        except anthropic.RateLimitError:
            if attempt == 4:
                raise
            print(f"  [{label}] rate limited, retrying in {wait}s...", flush=True)
            time.sleep(wait)
            wait *= 2

    raw = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "").strip()
    result = _extract_json(_clean(raw))
    print(f"  [{label}] done in {time.time()-t0:.1f}s", flush=True)
    return result


def _call_scout(client: anthropic.Anthropic, prompt: str) -> dict:
    """Scout call with web_search server-side tool.

    web_search_20250305 is a server-side tool: Anthropic executes searches
    automatically and returns the complete response (including tool results and
    final text) in a single API call — no client-side agentic loop needed.
    Falls back to plain reasoning if the tool is unavailable.
    """
    print("  [Scout] searching...", flush=True)
    t0 = time.time()

    def _extract_text(content) -> str:
        # Only extract TextBlock (not ServerToolUseBlock or WebSearchToolResultBlock)
        parts = []
        for b in content:
            btype = getattr(b, "type", "")
            if btype == "text" and getattr(b, "text", ""):
                parts.append(b.text)
        return "".join(parts).strip()

    # Try with web_search tool first
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS_SCOUT,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=[{"role": "user", "content": prompt}],
        )
        final_text = _extract_text(response.content)

        # If stop_reason is tool_use (model wants more turns), continue loop
        messages = [{"role": "user", "content": prompt}]
        messages.append({"role": "assistant", "content": response.content})
        # server_tool_use stop_reason means Anthropic is still processing — re-poll
        while response.stop_reason in ("tool_use", "server_tool_use"):
            tool_results = [
                {"type": "tool_result", "tool_use_id": b.id, "content": ""}
                for b in response.content
                if getattr(b, "type", "") in ("tool_use", "server_tool_use")
            ]
            if not tool_results:
                break
            messages.append({"role": "user", "content": tool_results})
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS_SCOUT,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})
            final_text = _extract_text(response.content)

    except Exception as e:
        print(f"  [Scout] web_search unavailable ({e}), falling back to reasoning...", flush=True)
        # Fallback: plain reasoning without live search
        fallback_prompt = (
            "You cannot search the web. Answer using your training knowledge. "
            "Be explicit about confidence and data currency.\n\n" + prompt
        )
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": fallback_prompt}],
        )
        final_text = _extract_text(response.content)

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
    findings_json_full = json.dumps(findings, ensure_ascii=False, indent=2)

    # Truncate findings for downstream agents to keep prompts manageable
    def _cap(s: str, limit: int) -> str:
        return s[:limit] + "\n...[truncated]" if len(s) > limit else s

    findings_json = _cap(findings_json_full, FINDINGS_CAP)

    # Phase 3: Analyst then Forensic — use lighter model to avoid rate limit after Scout
    print("\n[Phase 3] Analyst running...", flush=True)
    analyst_result = _call_light(client, build_analyst_prompt(ctx, findings_json), "Analyst")

    print("\n[Phase 3] Forensic running...", flush=True)
    forensic_result = _call_light(
        client,
        build_forensic_prompt(ctx, findings_json, "[]"),
        "Forensic",
    )

    analysis = analyst_result.get("analysis", [])
    red_flags = forensic_result.get("red_flags", [])
    overall_integrity = forensic_result.get("overall_integrity", "medium")
    analysis_json = json.dumps(analysis, ensure_ascii=False, indent=2)
    forensic_json = json.dumps({"red_flags": red_flags}, ensure_ascii=False, indent=2)

    # Phase 4: Strategist — synthesize and write final answers
    findings_for_strategist = _cap(findings_json_full, FINDINGS_TRUNCATE)
    print("\n[Phase 4] Strategist synthesizing...", flush=True)
    strategy_raw = _call_plain_large(
        client,
        build_strategist_prompt(ctx, findings_for_strategist, analysis_json, forensic_json),
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
