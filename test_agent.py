"""
Earnings Copilot — end-to-end test with mock LLM.

Validates the full agent loop without needing a real ANTHROPIC_API_KEY:
  1. Agent sends tools list + user message to "Claude"
  2. Mock Claude returns a tool_use block (fetch_consensus_data)
  3. Agent executes tool, sends result back
  4. Mock Claude returns another tool_use (analyze_earnings_transcript)
  5. Agent executes that tool
  6. Mock Claude returns another tool_use (calculate_expectation_gap)
  7. Agent executes that tool
  8. Mock Claude returns end_turn with final text
  9. Test asserts the output is correct

Swap MockAnthropicClient with real anthropic.Anthropic() to run for real.
"""

import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

# ── Sample transcript (abbreviated AAPL-style Q1 FY2026) ─────────────────────

SAMPLE_TRANSCRIPT = """
Apple Q1 FY2026 Earnings Call — February 2026

TIM COOK (CEO):
Good afternoon. We're very pleased to report record revenue for the December quarter,
with revenue of $124.3 billion, up 4% year over year. iPhone revenue was $69.1 billion.
Services hit a new all-time record of $26.3 billion, up 14% year over year.
We believe this is the beginning of a significant product cycle driven by Apple Intelligence,
and we expect that momentum to continue into the March quarter.

LUCA MAESTRI (CFO):
Our gross margin was 46.9%, up 70 basis points year over year. EPS was $2.41.
For Q2, we expect revenue between $88 and $90 billion.
We expect gross margin between 46% and 47%.

ANALYST (Morgan Stanley):
Can you give us more color on the China revenue trajectory?

TIM COOK:
China is a market we continue to invest in. Revenue in greater China was $18.5 billion
in the quarter. We remain committed to that market for the long term.

ANALYST (Goldman Sachs):
On the AI monetization timeline — when do you expect Apple Intelligence to drive
meaningful incremental ARPU in services?

LUCA MAESTRI:
We're not going to provide specific guidance on that. What I can tell you is that
customer engagement with Apple Intelligence features is very encouraging.

ANALYST (JPMorgan):
The Q2 guidance implies some deceleration from Q1. Can you help us understand the
macro assumptions embedded in that range?

TIM COOK:
We always try to give guidance that we feel we can achieve or beat. We're not going
to comment on specific macro assumptions.
"""

# ── Mock Anthropic client ─────────────────────────────────────────────────────

@dataclass
class FakeContent:
    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class FakeResponse:
    stop_reason: str
    content: list


def _tool_use(tool_id, name, inputs):
    return FakeContent(type="tool_use", id=tool_id, name=name, input=inputs)

def _text(t):
    return FakeContent(type="text", text=t)


class MockAnthropicMessages:
    """
    Simulates the Claude API's tool_use loop.
    Cycles through pre-scripted responses based on call count.
    """
    def __init__(self):
        self._call_count = 0

    def create(self, **kwargs):
        self._call_count += 1
        call = self._call_count

        if call == 1:
            # Claude's first move: fetch consensus data
            return FakeResponse(
                stop_reason="tool_use",
                content=[
                    _text("Let me start by fetching the consensus estimates for AAPL."),
                    _tool_use("tu_001", "fetch_consensus_data", {"ticker": "AAPL"}),
                ],
            )

        elif call == 2:
            # Claude has consensus data; now analyze the transcript
            return FakeResponse(
                stop_reason="tool_use",
                content=[
                    _text("Got consensus data. Now analyzing the transcript."),
                    _tool_use(
                        "tu_002",
                        "analyze_earnings_transcript",
                        {
                            "ticker": "AAPL",
                            "company_name": "Apple Inc.",
                            "quarter": "Q1 FY2026",
                            "transcript": SAMPLE_TRANSCRIPT,
                            "eps_estimate": 2.35,
                            "revenue_estimate_millions": 124_000,
                        },
                    ),
                ],
            )

        elif call == 3:
            # Claude has transcript analysis; compute gap
            return FakeResponse(
                stop_reason="tool_use",
                content=[
                    _tool_use(
                        "tu_003",
                        "calculate_expectation_gap",
                        {
                            "eps_actual": 2.41,
                            "eps_estimate": 2.35,
                            "revenue_actual_millions": 124_300,
                            "revenue_estimate_millions": 124_000,
                        },
                    )
                ],
            )

        elif call == 4:
            # Claude synthesizes final answer
            return FakeResponse(
                stop_reason="end_turn",
                content=[
                    _text(
                        "## AAPL Q1 FY2026 — Earnings Copilot Verdict\n\n"
                        "**EPS:** $2.41 actual vs $2.35 estimate → Beat by 2.6%\n"
                        "**Revenue:** $124.3B actual vs $124.0B estimate → Beat by 0.2% (in-line)\n\n"
                        "**Management Tone:** Neutral-to-cautious (score: 6/10). "
                        "Tim Cook deflected on China and AI monetization timelines. "
                        "Luca Maestri provided tight Q2 guidance of $88-90B, below some estimates.\n\n"
                        "**Top Risks:**\n"
                        "- Greater China revenue deceleration ($18.5B, no growth signal)\n"
                        "- Apple Intelligence ARPU monetization timeline unquantified\n"
                        "- Q2 guidance midpoint ($89B) implies YoY deceleration\n\n"
                        "**One-Line Verdict:** Modest EPS beat, in-line revenue, conservative Q2 guide — "
                        "neutral print, AI optionality intact but unpriced."
                    )
                ],
            )

        raise RuntimeError(f"MockAnthropicMessages: unexpected call #{call}")


class MockAnthropic:
    def __init__(self, api_key=None):
        self.api_key = api_key or "mock-key"
        self.messages = MockAnthropicMessages()


# ── Patch + run ───────────────────────────────────────────────────────────────

async def run_mock_test():
    import earnings_copilot.agent as agent_module

    # Patch the anthropic.Anthropic constructor inside the agent module
    original_anthropic = agent_module.anthropic.Anthropic
    agent_module.anthropic.Anthropic = MockAnthropic  # type: ignore

    # Patch get_expectation_data in the agent module's namespace (direct import binding)
    from earnings_copilot.models import ExpectationData

    async def mock_get_expectation_data(ticker, consensus_api_key=None):
        print(f"  [mock] get_expectation_data({ticker}) → returning hardcoded", flush=True)
        return ExpectationData(
            ticker=ticker,
            eps_estimate=2.35,
            revenue_estimate=124_000.0,
            source="mock (test)",
        )

    original_consensus = agent_module.get_expectation_data
    agent_module.get_expectation_data = mock_get_expectation_data  # patch agent's local binding

    # Patch analyze_earnings_call in the agent module's namespace
    from earnings_copilot.models import (
        EarningsCallAnalysis, ManagementTone, GuidanceItem, GuidanceVsConsensus,
        RiskFactor, RiskSeverity, AnalystQuestion,
    )

    def mock_analyze_earnings_call(ctx, api_key=None):
        print(f"  [mock] analyze_earnings_call({ctx.ticker}) → returning hardcoded", flush=True)
        return EarningsCallAnalysis(
            ticker=ctx.ticker,
            quarter=ctx.quarter,
            headline="Apple beats EPS by 2.6%, revenue in-line; Q2 guide soft",
            eps_actual=2.41,
            revenue_actual=124_300.0,
            eps_gap_pct=2.55,
            revenue_gap_pct=0.24,
            guidance=[
                GuidanceItem("Q2 Revenue", "$88-90B", GuidanceVsConsensus.BELOW, "Below $90.5B consensus"),
            ],
            management_tone=ManagementTone.CAUTIOUS,
            tone_score=6,
            tone_reasoning="Cook deflected on China and AI monetization; Maestri gave tight guide.",
            key_themes=["Apple Intelligence ramp", "Services record", "China uncertainty", "Q2 conservatism"],
            risk_factors=[
                RiskFactor("macro", "China revenue flat YoY", RiskSeverity.MEDIUM, False, True),
                RiskFactor("execution", "AI monetization timeline vague", RiskSeverity.MEDIUM, True, False),
            ],
            analyst_questions=[
                AnalystQuestion("Goldman Sachs", "AI ARPU timeline?", 2, ["redirected to engagement metrics"]),
                AnalystQuestion("JPMorgan", "Q2 macro assumptions?", 1, ["declined to comment"]),
            ],
            tension_areas=["China trajectory", "AI monetization", "Q2 guidance conservatism"],
            one_line_verdict="Modest EPS beat, in-line revenue, conservative Q2 guide — net neutral.",
        )

    original_analyze = agent_module.analyze_earnings_call
    agent_module.analyze_earnings_call = mock_analyze_earnings_call  # patch agent's local binding

    try:
        print("\n" + "="*60)
        print("EARNINGS COPILOT — AGENT TEST")
        print("="*60)
        print("Query: Analyze Apple Q1 FY2026 earnings\n")

        t0 = time.time()

        result = await agent_module.run_agent(
            user_message=(
                "Analyze Apple Inc. (AAPL) Q1 FY2026 earnings. "
                "Here is the transcript:\n\n" + SAMPLE_TRANSCRIPT
            ),
            verbose=True,
        )

        elapsed = time.time() - t0

        print("\n" + "="*60)
        print("AGENT FINAL OUTPUT")
        print("="*60)
        print(result)
        print(f"\n✓ Completed in {elapsed:.2f}s")

        # Assertions
        assert "AAPL" in result or "Apple" in result, "Output should mention AAPL"
        assert "EPS" in result or "eps" in result.lower(), "Output should mention EPS"
        assert len(result) > 100, "Output too short"

        print("\n✓ All assertions passed")
        return True

    finally:
        # Restore originals
        agent_module.anthropic.Anthropic = original_anthropic
        agent_module.get_expectation_data = original_consensus
        agent_module.analyze_earnings_call = original_analyze


def main():
    ok = asyncio.run(run_mock_test())
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
