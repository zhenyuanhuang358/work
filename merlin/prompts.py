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


# Appended to every prompt — enforces synchronized bilingual output
_BILINGUAL = """

BILINGUAL OUTPUT RULE (mandatory):
For every text field (not integers, not category codes like "high/medium/low"):
Write the content in BOTH English and Chinese, in this exact format:
  "English text ||| 中文翻译"

Example:
  "company_overview": "Luckin Coffee is China's largest coffee chain by store count, operating 31,000+ stores with a digital-first model. ||| 瑞幸咖啡是中国门店数量最多的咖啡连锁，拥有31,000余家门店，以数字化为核心驱动。"

Do NOT skip the ||| separator. Do NOT write English-only or Chinese-only for any text field."""


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
  "company_overview": "<2-3 sentences bilingual: what the company does, business model, scale>",
  "recent_events": [
    "<most recent important event — bilingual>",
    "<second event — bilingual>",
    "<third event — bilingual>"
  ],
  "key_metrics": [
    "<metric 1, e.g. 'Revenue ¥34.5B, +38% YoY ||| 营收344.75亿，同比+38%'>",
    "<metric 2 — bilingual>",
    "<metric 3 — bilingual>",
    "<metric 4 — bilingual>"
  ],
  "strategic_narrative": "<the story management is telling — bilingual>",
  "context_gaps": "<what important information is missing — bilingual>"
}}""" + _BILINGUAL


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
      "title": "<concise issue name, 5-8 words — bilingual>",
      "why_it_matters": "<one sentence: what decision or view changes — bilingual>",
      "evidence": "<specific data points or observations — bilingual>",
      "impact": <integer 1-5, 5 = highest impact on meeting outcome>,
      "certainty": <integer 1-5, 5 = most certain this issue exists>
    }}
  ]
}}""" + _BILINGUAL


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
2. NARRATIVE vs DATA GAPS — management says X but the numbers suggest Y
3. TIMING ANOMALIES — something changed suddenly, or didn't change when it should have
4. OMISSION SIGNALS — important topics conspicuously absent from materials

For each risk, provide:
- The exact data tension (what are the two conflicting signals)
- The one question that separates the innocent from the concerning explanation

Return ONLY valid JSON:

{{
  "risks": [
    {{
      "category": "<financial|strategic|operational|competitive|governance|other>",
      "description": "<what the risk is in one sentence — bilingual>",
      "contradiction": "<the specific data tension: 'X says A, but Y says B' — bilingual>",
      "verification_question": "<the single most targeted question to resolve this — bilingual>",
      "severity": "<high|medium|low>"
    }}
  ]
}}""" + _BILINGUAL


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
      "question": "<the specific, targeted question — bilingual>",
      "purpose": "<what you're actually trying to learn — bilingual>",
      "follow_ups": [
        "<follow-up if answer is vague — bilingual>",
        "<follow-up if they deflect — bilingual>"
      ],
      "evasion_signal": "<how they will likely dodge this — bilingual>",
      "breakthrough": "<how to push through — bilingual>",
      "priority": <integer 1-6>
    }}
  ]
}}""" + _BILINGUAL


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
The opening strategy should be the first 60 seconds: how to frame the conversation
to maximize candor and reduce defensive responses.

Return ONLY valid JSON:

{{
  "central_hypothesis": "<the one bet to test — bilingual>",
  "opening_strategy": "<how to open the conversation — specific, not generic — bilingual>",
  "key_themes": [
    "<theme 1: 4-6 words — bilingual>",
    "<theme 2 — bilingual>",
    "<theme 3 — bilingual>",
    "<theme 4 — bilingual>",
    "<theme 5 — bilingual>"
  ],
  "confidence_score": <integer 1-10, reflecting how much useful material was available for prep>,
  "confidence_reasoning": "<one sentence: why this score — bilingual>"
}}""" + _BILINGUAL


# ── Prompt 6: Critic ─────────────────────────────────────────────────────────
# Independent context — Critic never sees how the Builder reached its conclusions.
# Goal: prove the brief is wrong, generic, or insufficient. Not to help. To fail it.

CRITIC_TEMPLATE = """\
You are an adversarial quality critic reviewing an interview brief produced by an AI system.
Your mission: find every weakness. You WANT to fail this brief.

<context>
Company: {company_name}
Meeting purpose: {meeting_purpose}
</context>

<brief_to_critique>
{analysis_json}
</brief_to_critique>

Look specifically for these five failure modes:

1. GENERIC QUESTIONS — questions that could apply to any company in this sector,
   not specifically to {company_name}. Flag each one.
2. UNTESTABLE HYPOTHESES — a central hypothesis you cannot confirm or deny
   in a single 60-minute conversation.
3. IRRELEVANT ISSUES — core issues not connected to {meeting_purpose}.
4. OVERCONFIDENT ANALYSIS — claims presented as verified fact when they are speculation.
5. MISSED OBVIOUS SIGNALS — risks or issues any informed analyst would flag
   that this brief completely ignored.

Quality score rubric (be strict):
- 9-10: Every question references specific {company_name} data; hypothesis is crisp
        and testable in one meeting; all issues directly serve {meeting_purpose}
- 7-8: Mostly specific; minor generic elements; hypothesis broadly testable
- 5-6: Several generic questions; hypothesis partially testable; some drift from purpose
- 3-4: Majority of questions could apply to any peer company
- 1-2: Generic throughout; could have been written for any company in this industry

adjusted_confidence = your independent read of how trustworthy this brief is
(may be lower than the builder's self-reported score if you found serious issues)

Return ONLY valid JSON:

{{
  "verdict": "<pass|conditional_pass|fail>",
  "quality_score": <integer 1-10>,
  "adjusted_confidence": <integer 1-10>,
  "failures": [
    {{
      "section": "<brief|issues|risks|questions|strategy>",
      "issue": "<specific problem — bilingual>",
      "severity": "<critical|major|minor>"
    }}
  ],
  "strengths": [
    "<genuinely strong element — bilingual>"
  ],
  "critic_note": "<one sentence overall verdict — bilingual>"
}}

pass = ship immediately
conditional_pass = usable with noted caveats
fail = do not use without substantial revision""" + _BILINGUAL


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


def build_critic_prompt(ctx: MerlinContext, analysis_json: str) -> str:
    return CRITIC_TEMPLATE.format(
        company_name=ctx.company_name,
        meeting_purpose=ctx.meeting_purpose,
        analysis_json=analysis_json,
    )
