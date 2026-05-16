from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CoreIssue:
    title: str
    why_it_matters: str
    evidence: str
    impact: int       # 1-5, 5 = highest impact on meeting outcome
    certainty: int    # 1-5, 5 = most certain the issue exists


@dataclass
class RiskItem:
    category: str
    description: str
    contradiction: str        # the data tension that surfaces this risk
    verification_question: str  # single best question to test it
    severity: str             # "high" | "medium" | "low"


@dataclass
class InterviewQuestion:
    question: str
    purpose: str              # what you're actually trying to learn
    follow_ups: list[str]
    evasion_signal: str       # how they'll try to dodge it
    breakthrough: str         # how to push through evasion
    priority: int             # 1 = ask first


@dataclass
class MerlinAnalysis:
    company_name: str
    meeting_purpose: str

    # Company context
    company_overview: str
    recent_events: list[str]
    key_metrics: list[str]    # ["Revenue $Xbn", "GM XX%", ...] — strings for flexibility
    strategic_narrative: str  # the story management tells
    context_gaps: str         # what's missing that would change the analysis

    # Core consulting work
    core_issues: list[CoreIssue]
    risks: list[RiskItem]
    questions: list[InterviewQuestion]

    # Interview strategy
    central_hypothesis: str   # the one bet to test in this meeting
    opening_strategy: str     # how to open the conversation
    key_themes: list[str]
    confidence_score: int     # 1-10, analyst confidence in prep quality
    confidence_reasoning: str  # why this score
