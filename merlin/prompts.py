"""
Merlin — Five consulting reasoning prompts.

Design principle: each prompt embeds a specific consulting methodology,
not just "be a consultant." The reasoning logic must be explicit in the prompt.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MerlinContext:
    company_name: str
    meeting_purpose: str          # e.g. "投资尽调", "销售拜访", "管理层访谈"
    background_text: str          # everything the user provided: docs, paste, web snippets
    industry: Optional[str] = None
    interviewee_role: Optional[str] = None


# ── Prompt 1: Company Brief ───────────────────────────────────────────────────

BRIEF_TEMPLATE = """\
You are a senior research analyst preparing a briefing for a partner before an important meeting.

<context>
Company: {company_name}
Meeting purpose: {meeting_purpose}
Industry: {industry}
Interviewee role: {interviewee_role}
</context>

<materials>
{background_text}
</materials>

Your job: extract a structured, factual briefing from the materials above.
Do NOT make up facts not present in the materials. Use null if data is unavailable.

Return ONLY valid JSON:

{{
  "company_overview": "<2-3 sentences: what the company does, business model, scale>",
  "recent_events": [
    "<most recent important event — earnings, news, leadership change, product launch>",
    "<second event>",
    "<third event>"
  ],
  "key_metrics": [
    "<metric 1, e.g. 'Revenue $10B, +36% YoY'>",
    "<metric 2, e.g. 'Gross margin 52.8%'>",
    "<metric 3>",
    "<metric 4>"
  ],
  "strategic_narrative": "<the story management is telling: what is the company positioning itself as, and why now?>",
  "context_gaps": "<what important information is missing that would change the analysis if known>"
}}"""


# ── Prompt 2: Core Issues ─────────────────────────────────────────────────────

ISSUES_TEMPLATE = """\
You are a McKinsey senior partner. Your job is NOT to summarize what you know.
Your job is to identify what you DON'T know that matters most for {meeting_purpose}.

<company>
{company_name}
</company>

<materials>
{background_text}
</materials>

Consulting method: for each core issue, complete this logic chain:
1. What specific claim or assumption is being made?
2. What data or evidence would CONFIRM it?
3. What data or evidence would CONTRADICT it?
4. If this assumption is wrong, what is the consequence for {meeting_purpose}?

Focus on issues where the ANSWER CHANGES YOUR DECISION. Ignore interesting-but-irrelevant details.

Return ONLY valid JSON with 3-5 issues, ordered by importance:

{{
  "core_issues": [
    {{
      "title": "<concise issue name, 5-8 words>",
      "why_it_matters": "<one sentence: what decision or view changes if this is resolved>",
      "evidence": "<specific data points or observations that make this a real issue>",
      "impact": <integer 1-5, 5 = highest impact on meeting outcome>,
      "certainty": <integer 1-5, 5 = most certain this issue exists>
    }}
  ]
}}"""


# ── Prompt 3: Risk & Contradiction Detection ──────────────────────────────────

RISK_TEMPLATE = """\
You are a forensic analyst. Your job: find what doesn't add up.

<company>
{company_name}
</company>

<materials>
{background_text}
</materials>

Look specifically for these four types of problems:

1. METRIC CONTRADICTIONS — two numbers that tell conflicting stories
   Example: revenue up 30% but gross margin down 5pp → pricing pressure or cost issue

2. NARRATIVE vs DATA GAPS — management says X but the numbers suggest Y
   Example: "AI-driven growth" but AI revenue is 3% of total

3. TIMING ANOMALIES — something changed suddenly, or didn't change when it should have
   Example: capex jumped 3× the quarter before revenue acceleration

4. OMISSION SIGNALS — important topics conspicuously absent from materials
   Example: company talks about "market expansion" but never mentions market share

For each risk, provide:
- The exact data tension (what are the two conflicting signals)
- The innocent explanation
- The concerning explanation
- The one question that separates the two explanations

Return ONLY valid JSON:

{{
  "risks": [
    {{
      "category": "<financial|strategic|operational|competitive|governance|other>",
      "description": "<what the risk is in one sentence>",
      "contradiction": "<the specific data tension: 'X says A, but Y says B'>",
      "verification_question": "<the single most targeted question to resolve this in the interview>",
      "severity": "<high|medium|low>"
    }}
  ]
}}"""


# ── Prompt 4: Question Tree ───────────────────────────────────────────────────

QA_TEMPLATE = """\
You are preparing interview questions for {meeting_purpose} with {company_name}.

<materials>
{background_text}
</materials>

CRITICAL RULE: Do NOT generate generic questions.
Every question must be specific to THIS company and THIS situation.

BAD: "What are your growth plans?"
GOOD: "Your Q3 data shows new customer acquisition accelerating while retention dropped 8pp —
       are you optimizing for growth or unit economics right now, and how does that change in 12 months?"

For each question:
- Make it hard to deflect without revealing something
- Anticipate the likely evasion tactic
- Provide the follow-up that cuts through the evasion

Return ONLY valid JSON with 4-6 questions, ordered by priority (1 = ask first):

{{
  "questions": [
    {{
      "question": "<the specific, targeted question>",
      "purpose": "<what you're actually trying to learn — the real question behind the question>",
      "follow_ups": [
        "<follow-up if answer is vague>",
        "<follow-up if they deflect to another topic>"
      ],
      "evasion_signal": "<how they will likely dodge this: e.g. 'will cite industry headwinds', 'will give forward guidance instead'>",
      "breakthrough": "<how to push through: e.g. 'ask for the specific Q number', 'ask what the internal target was'>",
      "priority": <integer 1-6>
    }}
  ]
}}"""


# ── Prompt 5: Interview Strategy ──────────────────────────────────────────────

STRATEGY_TEMPLATE = """\
You are a senior partner briefing a junior analyst 30 minutes before an important meeting.

<company>
{company_name}
</company>

<meeting purpose>
{meeting_purpose}
</meeting purpose>

<what we know>
{background_text}
</what we know>

Your job: give the analyst the strategic frame for this meeting.

The central hypothesis is the ONE THING that, if true, changes everything.
Example: "The real question is whether their unit economics actually improve with scale,
         or whether management is papering over a structurally broken model with growth."

The opening strategy should be the first 60 seconds: how to frame the conversation
to maximize candor and reduce defensive responses.

Return ONLY valid JSON:

{{
  "central_hypothesis": "<the one bet to test: what would change your view completely if confirmed?>",
  "opening_strategy": "<how to open the conversation to build trust and reduce defensiveness — specific, not generic>",
  "key_themes": [
    "<theme 1: 4-6 words>",
    "<theme 2>",
    "<theme 3>",
    "<theme 4>",
    "<theme 5>"
  ],
  "confidence_score": <integer 1-10, reflecting how much useful material was available for prep>,
  "confidence_reasoning": "<one sentence: why this score — e.g. 'Limited financials available, strong qualitative context'>"
}}"""


# ── Builders ──────────────────────────────────────────────────────────────────

def build_brief_prompt(ctx: MerlinContext) -> str:
    return BRIEF_TEMPLATE.format(
        company_name=ctx.company_name,
        meeting_purpose=ctx.meeting_purpose,
        industry=ctx.industry or "不详",
        interviewee_role=ctx.interviewee_role or "不详",
        background_text=ctx.background_text,
    )


def build_issues_prompt(ctx: MerlinContext) -> str:
    return ISSUES_TEMPLATE.format(
        company_name=ctx.company_name,
        meeting_purpose=ctx.meeting_purpose,
        background_text=ctx.background_text,
    )


def build_risk_prompt(ctx: MerlinContext) -> str:
    return RISK_TEMPLATE.format(
        company_name=ctx.company_name,
        background_text=ctx.background_text,
    )


def build_qa_prompt(ctx: MerlinContext) -> str:
    return QA_TEMPLATE.format(
        company_name=ctx.company_name,
        meeting_purpose=ctx.meeting_purpose,
        background_text=ctx.background_text,
    )


def build_strategy_prompt(ctx: MerlinContext) -> str:
    return STRATEGY_TEMPLATE.format(
        company_name=ctx.company_name,
        meeting_purpose=ctx.meeting_purpose,
        background_text=ctx.background_text,
    )
