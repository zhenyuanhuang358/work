from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ManagementTone(str, Enum):
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    CAUTIOUS = "cautious"
    DEFENSIVE = "defensive"


class GuidanceVsConsensus(str, Enum):
    ABOVE = "above"
    IN_LINE = "in-line"
    BELOW = "below"
    WITHDRAWN = "withdrawn"


class RiskSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class FinancialTable:
    page: int
    headers: list[str]
    rows: list[dict]
    confidence: float
    raw_text: str
    source: str = "pdf"


@dataclass
class ExpectationData:
    ticker: str
    eps_estimate: Optional[float]
    revenue_estimate: Optional[float]  # in millions
    source: str
    staleness_hours: float = 0.0
    error: Optional[str] = None


@dataclass
class GuidanceItem:
    metric: str
    value: Optional[str]
    vs_consensus: GuidanceVsConsensus
    note: str = ""


@dataclass
class RiskFactor:
    category: str
    description: str
    severity: RiskSeverity
    is_new: bool
    management_acknowledged: bool


@dataclass
class AnalystQuestion:
    analyst_firm: str
    question_summary: str
    management_directness: int  # 1-5, 5 = fully answered
    evasion_signals: list[str] = field(default_factory=list)


@dataclass
class EarningsCallAnalysis:
    ticker: str
    quarter: str
    headline: str
    eps_actual: Optional[float]
    revenue_actual: Optional[float]
    eps_gap_pct: Optional[float]
    revenue_gap_pct: Optional[float]
    guidance: list[GuidanceItem]
    management_tone: ManagementTone
    tone_score: int  # 1-10
    tone_reasoning: str
    key_themes: list[str]
    risk_factors: list[RiskFactor]
    analyst_questions: list[AnalystQuestion]
    tension_areas: list[str]
    one_line_verdict: str
    # Financial detail fields (extracted by summary prompt)
    yoy_revenue_growth_pct: Optional[float] = None
    gross_margin_pct: Optional[float] = None
    next_quarter_gross_margin_pct: Optional[float] = None
    segments: list = field(default_factory=list)  # [{name, revenue_millions, yoy_pct}]


@dataclass
class CopilotReport:
    ticker: str
    quarter: str
    tables: list[FinancialTable]
    expectation_data: ExpectationData
    analysis: EarningsCallAnalysis
    processing_seconds: float
