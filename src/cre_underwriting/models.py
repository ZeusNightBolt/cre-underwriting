"""
cre_underwriting.models — Shared dataclasses for the CRE underwriting pipeline.

Single source of truth for all domain objects. No module should define its own
version of Scenario, DealInput, EnvironmentalRisk, etc. — import from here.

Previously these were duplicated across cre_convexity.py, cre_enhanced.py,
and cre_environmental.py with different field names and completeness.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


# ════════════════════════════════════════════════════════════════
# Schema normalization
# ════════════════════════════════════════════════════════════════

def extract_pricing(data: dict) -> dict:
    """Normalize ask price and hard-floor values across deal JSON schemas.

    Two schemas exist in the wild:
      - classic:  property.price + hard_asset_floor/hard_floor.{low,mid,high}
      - pricing:  pricing.ask + pricing.hard_floor_{low,mid,high}  (e.g. Boonton)

    Returns a dict with keys: ask_price, hard_floor_low, hard_floor_mid,
    hard_floor_high. Missing values default to 0. This is the single shared
    fallback chain — use it instead of reading the raw dict directly.
    """
    pricing = data.get("pricing") or {}
    prop = data.get("property") or {}
    hf = data.get("hard_asset_floor", data.get("hard_floor")) or {}

    ask_price = prop.get("price", 0) or pricing.get("ask", 0) or data.get("ask_price", 0) or 0
    return {
        "ask_price": ask_price,
        "hard_floor_low": pricing.get("hard_floor_low") or hf.get("low", 0) or 0,
        "hard_floor_mid": pricing.get("hard_floor_mid") or hf.get("mid", 0) or 0,
        "hard_floor_high": pricing.get("hard_floor_high") or hf.get("high", 0) or 0,
    }


# ════════════════════════════════════════════════════════════════
# Core Deal Objects (from cre_convexity.py)
# ════════════════════════════════════════════════════════════════

@dataclass
class Scenario:
    """A single scenario in the 5-scenario architecture."""
    name: str                           # "Worst", "Baseline", "Phase 1 Optimize", etc.
    probability: float                  # 0.0 – 1.0
    revenue: float = 0.0
    cogs: float = 0.0
    labor: float = 0.0
    other_opex: float = 0.0
    noi: Optional[float] = None         # computed: revenue - cogs - labor - other_opex
    sde: Optional[float] = None         # computed: noi + adjustments
    exit_value: float = 0.0
    moic: Optional[float] = None        # computed: exit_value / purchase_price

    def __post_init__(self):
        if self.noi is None:
            self.noi = self.revenue - self.cogs - self.labor - self.other_opex


@dataclass
class DealInput:
    """Complete deal input for convexity analysis.

    NOTE: Creating a DealInput does NOT mutate the caller's Scenario objects.
    MOIC is computed from a copy of the scenario list.
    """
    ask_price: float
    purchase_price: float
    hard_floor_low: float
    hard_floor_mid: float
    hard_floor_high: float
    real_estate_value: float = 0.0
    license_value: float = 0.0
    equipment_value: float = 0.0
    scenarios: List[Scenario] = field(default_factory=list)
    exit_year: int = 5
    capital_invested: Optional[float] = None

    def __post_init__(self):
        if self.capital_invested is None:
            self.capital_invested = self.purchase_price
        # Defensive copy: compute MOIC on copies so caller's Scenario
        # objects are never mutated. The original bug (Fords 34554176)
        # caused wrong MOIC when scenarios were reused across deals.
        self.scenarios = [Scenario(
            name=s.name, probability=s.probability,
            revenue=s.revenue, cogs=s.cogs, labor=s.labor,
            other_opex=s.other_opex, noi=s.noi, sde=s.sde,
            exit_value=s.exit_value, moic=s.moic,
        ) for s in self.scenarios]
        if self.purchase_price > 0:
            for s in self.scenarios:
                if s.moic is None:
                    s.moic = s.exit_value / self.purchase_price


# ════════════════════════════════════════════════════════════════
# Divergence & Convexity Outputs (from cre_convexity.py)
# ════════════════════════════════════════════════════════════════

@dataclass
class DivergenceOutput:
    """Divergence metrics for a deal."""
    absolute_spread: float
    capital_normalized_spread: float
    convexity_ratio: float
    convexity_verdict: str             # "HIGH", "POSITIVE", "MARGINAL", "NEGATIVE"
    worst_scenario_value: float
    hard_floor_mid: float
    effective_worst: float             # max(worst_scenario, hard_floor_mid)
    base_scenario_value: float
    best_scenario_value: float
    worst_case_pct_capital: float
    best_case_moic: float
    risk_reward_ratio: float


@dataclass
class PWEVOutput:
    """Probability-weighted expected value."""
    pwev: float
    pwev_vs_ask_pct: float
    is_underpriced: bool
    worst_contribution: float
    base_contribution: float
    best_contribution: float


@dataclass
class FrontierPoint:
    """A point on the effective frontier chart."""
    x: float     # worst-case LOSS as % of capital (100 - worst_case_pct_capital)
    y: float     # best case 5-year MOIC
    zone: str    # "Pursue aggressively", "Acceptable selectively", etc.


@dataclass
class VerdictOutput:
    """Final deal verdict with reasoning."""
    verdict: str                       # "PURSUE AT $X", "CONDITIONAL", "PASS"
    target_offer: Optional[float]
    walk_away: Optional[float]
    convexity_ratio: float
    zone: str
    reasoning: List[str] = field(default_factory=list)
    risk_reward_summary: str = ""


@dataclass
class ConvexityResult:
    """Complete convexity analysis output."""
    deal: DealInput
    divergence: DivergenceOutput
    pwev: PWEVOutput
    frontier: FrontierPoint
    verdict: VerdictOutput

    def to_dict(self) -> dict:
        return {
            "divergence": {
                "absolute_spread": self.divergence.absolute_spread,
                "capital_normalized_spread": round(self.divergence.capital_normalized_spread, 2),
                "convexity_ratio": round(self.divergence.convexity_ratio, 2),
                "convexity_verdict": self.divergence.convexity_verdict,
                "worst_scenario_value": self.divergence.worst_scenario_value,
                "hard_floor_mid": self.divergence.hard_floor_mid,
                "effective_worst": self.divergence.effective_worst,
                "base_scenario_value": self.divergence.base_scenario_value,
                "best_scenario_value": self.divergence.best_scenario_value,
                "worst_case_pct_capital": round(self.divergence.worst_case_pct_capital, 1),
                "best_case_moic": round(self.divergence.best_case_moic, 2),
                "best_case_moic_5yr": round(self.divergence.best_case_moic, 2),
                "risk_reward_ratio": round(self.divergence.risk_reward_ratio, 1),
            },
            "pwev": {
                "pwev": round(self.pwev.pwev, 0),
                "pwev_vs_ask_pct": round(self.pwev.pwev_vs_ask_pct, 1),
                "is_underpriced": self.pwev.is_underpriced,
            },
            "frontier": {
                "x": round(self.frontier.x, 1),
                "y": round(self.frontier.y, 2),
                "zone": self.frontier.zone,
            },
            "verdict": {
                "verdict": self.verdict.verdict,
                "target_offer": self.verdict.target_offer,
                "walk_away": self.verdict.walk_away,
                "convexity_ratio": round(self.verdict.convexity_ratio, 2),
                "reasoning": self.verdict.reasoning,
                "risk_reward_summary": self.verdict.risk_reward_summary,
            },
        }


# ════════════════════════════════════════════════════════════════
# Enhanced Analysis Outputs (from cre_enhanced.py)
# ════════════════════════════════════════════════════════════════

@dataclass
class MoatDimension:
    """A single dimension of the 8-moat scoring system."""
    name: str
    score: int
    max_score: int = 3
    rationale: str = ""

    @property
    def percentage(self) -> float:
        return (self.score / self.max_score * 100) if self.max_score > 0 else 0


@dataclass
class MoatScorecard:
    """Complete 8-moat scorecard."""
    dimensions: List[MoatDimension] = field(default_factory=list)
    total_score: int = 0
    max_score: int = 24
    classification: str = ""
    strongest: List[str] = field(default_factory=list)
    weakest: List[str] = field(default_factory=list)
    verdict_text: str = ""

    @property
    def percentage(self) -> float:
        return (self.total_score / self.max_score * 100) if self.max_score > 0 else 0

    def to_dict(self) -> dict:
        return {
            "dimensions": [
                {"name": d.name, "score": d.score, "max": d.max_score,
                 "percentage": round(d.percentage, 1), "rationale": d.rationale}
                for d in self.dimensions
            ],
            "total_score": self.total_score,
            "max_score": self.max_score,
            "percentage": round(self.percentage, 1),
            "classification": self.classification,
            "strongest": self.strongest,
            "weakest": self.weakest,
            "verdict_text": self.verdict_text,
        }


@dataclass
class OfferPoint:
    """A single price point in the offer ladder.

    Note: cash_on_cash_pct was removed — it was computed identically to
    cap_rate_pct (NOI/price), i.e. a mislabeled duplicate. True cash-on-cash
    requires financing parameters (LTV, rate, amortization) that the deal
    schema does not carry.
    """
    price: float
    price_per_sf: float
    cap_rate_pct: float
    gross_rent_multiplier: float
    label: str = ""


@dataclass
class OfferLadder:
    """Multi-price offer analysis ladder."""
    points: List[OfferPoint] = field(default_factory=list)
    target_low: float = 0
    target_high: float = 0
    walk_away: float = 0
    ask_price: float = 0
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "points": [
                {"price": p.price, "price_per_sf": round(p.price_per_sf, 0),
                 "cap_rate_pct": round(p.cap_rate_pct, 2),
                 "gross_rent_multiplier": round(p.gross_rent_multiplier, 1),
                 "label": p.label}
                for p in self.points
            ],
            "target_low": self.target_low, "target_high": self.target_high,
            "walk_away": self.walk_away, "ask_price": self.ask_price,
            "rationale": self.rationale,
        }


# ════════════════════════════════════════════════════════════════
# Environmental & Economic (unified from cre_environmental.py)
# ════════════════════════════════════════════════════════════════

@dataclass
class EnvironmentalRisk:
    """Environmental risk assessment for a property."""
    flood_zone: str = ""
    in_floodplain: bool = False
    flood_risk_level: str = "unknown"
    ust_risk: str = "unknown"
    ust_sites_nearby: int = 0
    known_contamination: bool = False
    phase_i_recommended: bool = False
    red_flags: List[str] = field(default_factory=list)


@dataclass
class EconomicIndicators:
    """Economic indicators for a county/region."""
    # Demographics
    population: int = 0
    population_growth_5yr_pct: float = 0
    median_household_income: int = 0
    per_capita_income: int = 0
    income_growth_5yr_pct: float = 0
    poverty_rate_pct: float = 0
    bachelor_degree_pct: float = 0

    # Employment
    total_employment: int = 0
    employment_growth_5yr_pct: float = 0
    wage_growth_5yr_pct: float = 0
    top_employers: List[str] = field(default_factory=list)
    unemployment_rate_pct: float = 0

    # Housing
    median_home_value: int = 0
    home_price_appreciation_1yr_pct: float = 0
    home_price_appreciation_5yr_pct: float = 0
    rent_vs_own_pct: float = 0
    rental_vacancy_rate_pct: float = 0

    # Signals
    tailwinds: List[str] = field(default_factory=list)
    headwinds: List[str] = field(default_factory=list)
    sources: Dict[str, str] = field(default_factory=dict)


# ════════════════════════════════════════════════════════════════
# Comparable Sales
# ════════════════════════════════════════════════════════════════

@dataclass
class Comp:
    """A single comparable sale."""
    source: str
    address: str
    sale_date: Optional[str] = None
    sale_price: Optional[float] = None
    sf: Optional[float] = None
    price_per_sf: Optional[float] = None
    property_type: Optional[str] = None
    dom: Optional[int] = None

    def __post_init__(self):
        if self.price_per_sf is None and self.sale_price and self.sf:
            self.price_per_sf = round(self.sale_price / self.sf, 2)
