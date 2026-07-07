"""
v5 Data Models — Structured, validated, LLM-compatible.

Every LLM output is parsed into one of these Pydantic-style models.
Validation at parse time — invalid JSON → retry with error context.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ═══════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════

class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"

class Verdict(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    PASS = "PASS"
    CONDITIONAL = "CONDITIONAL"

class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class Effort(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class MoatClass(str, Enum):
    WIDE = "WIDE MOAT"
    NARROW = "NARROW MOAT"
    NONE = "NO MOAT"


# ═══════════════════════════════════════════════════════════
# Ranged Value (used everywhere for NOI, cap rate, etc.)
# ═══════════════════════════════════════════════════════════

@dataclass
class Range:
    """A value expressed as a low-mid-high triple."""
    low: float = 0.0
    mid: float = 0.0
    high: float = 0.0

    def to_dict(self) -> dict:
        return {"low": self.low, "mid": self.mid, "high": self.high}


# ═══════════════════════════════════════════════════════════
# LiveContext v5 — all accumulated live data
# ═══════════════════════════════════════════════════════════

@dataclass
class LiveContext:
    """All live-fetched data for a deal. Populated progressively by K1-K5."""

    # ── Property data (K1) ──
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    property_type: str = ""
    ask_price: float = 0.0
    building_sf: float = 0.0
    lot_acres: float = 0.0
    year_built: int = 0
    building_class: str = ""
    zoning: str = ""
    days_on_market: int = 0
    price_reductions: int = 0
    listing_id: str = ""
    listing_source: str = ""  # "loopnet", "zillow", "crexi", "fixture"

    # ── Income / Rent Roll (K1 + LLM reconstruction) ──
    rent_psf_range: Range = field(default_factory=Range)
    expense_structure: str = ""  # "NNN", "Gross", "Modified Gross"
    tenant_names: List[str] = field(default_factory=list)
    lease_expirations: List[str] = field(default_factory=list)
    noi_estimated: Range = field(default_factory=Range)
    cap_rate_estimated: float = 0.0

    # ── FRED Economics (K2) ──
    msa_name: str = ""
    hpi_1yr_pct: Optional[float] = None
    hpi_5yr_annualized_pct: Optional[float] = None
    hpi_source: str = ""
    county_median_income: Optional[int] = None
    county_unemployment_pct: Optional[float] = None
    county_population: Optional[int] = None
    county_population_growth_pct: Optional[float] = None
    retail_sales_trend_pct: Optional[float] = None

    # ── Demographics (K3, granular) ──
    zip_median_hhi: Optional[int] = None
    population_1mi: Optional[int] = None
    population_3mi: Optional[int] = None
    traffic_count_daily: Optional[int] = None
    school_district_rating: Optional[int] = None
    recent_business_activity: str = ""  # "growing", "stable", "declining"

    # ── Comps (K4) ──
    comps: List[dict] = field(default_factory=list)

    # ── Environmental (K5) ──
    ust_found: Optional[bool] = None
    flood_zone: str = ""
    superfund_proximity_miles: Optional[float] = None
    brownfield_flag: bool = False
    environmental_liability_estimate: float = 0.0

    # ── Web search findings ──
    corridor_news: List[dict] = field(default_factory=list)
    environmental_findings: List[dict] = field(default_factory=list)
    county_records: List[dict] = field(default_factory=list)

    # ── Audit ──
    data_sources: dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    analysis_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ═══════════════════════════════════════════════════════════
# LLM Output Models — every LLM call returns one of these
# ═══════════════════════════════════════════════════════════

@dataclass
class MoatOutput:
    """Triple-LLM moat analysis output. Validated on parse."""
    scores: dict = field(default_factory=dict)  # {dimension: {"score": int, "rationale": str}}
    total: int = 0
    classification: str = "NO MOAT"
    verdict: str = ""
    strongest: List[str] = field(default_factory=list)
    weakest: List[str] = field(default_factory=list)
    # Audit
    deepseek_raw: str = ""
    openrouter_raw: str = ""
    mistral_raw: str = ""
    synthesis_raw: str = ""
    v3_scorecard: dict = field(default_factory=dict)  # v3 MoatScorer output for comparison

    def validate(self) -> List[str]:
        """Validate internal consistency. Returns list of errors."""
        errors = []
        computed = sum(s.get("score", 0) for s in self.scores.values())
        if computed != self.total:
            errors.append(f"Moat total mismatch: scores sum to {computed}, declared {self.total}")
        for dim in ["license_barrier", "tourism_corridor", "multi_revenue", "zoning_optionality",
                     "rent_gap", "brand_value", "asset_stack", "seller_asymmetry"]:
            if dim not in self.scores:
                errors.append(f"Missing dimension: {dim}")
        return errors


@dataclass
class Scenario:
    """A single scenario in the 5-scenario set."""
    name: str = ""
    probability: float = 0.0
    noi: int = 0
    exit_cap: float = 0.08
    exit_value: int = 0
    moic: float = 0.0
    description: str = ""
    triggers: List[str] = field(default_factory=list)
    key_assumptions: List[str] = field(default_factory=list)

    def validate(self, purchase_price: float) -> List[str]:
        """Validate numerical consistency."""
        errors = []
        # exit_value ≈ round(noi / exit_cap, -3)
        if self.exit_cap > 0:
            expected = round(self.noi / self.exit_cap, -3)
            if abs(self.exit_value - expected) > max(expected * 0.05, 5000):
                errors.append(
                    f"Scenario '{self.name}': exit_value ${self.exit_value:,} ≠ "
                    f"round(NOI ${self.noi:,} / cap {self.exit_cap}) = ${expected:,}"
                )
        # moic ≈ exit_value / purchase_price
        if purchase_price > 0:
            expected_moic = round(self.exit_value / purchase_price, 2)
            if abs(self.moic - expected_moic) > 0.015:
                errors.append(
                    f"Scenario '{self.name}': moic {self.moic} ≠ "
                    f"exit ${self.exit_value:,} / price ${purchase_price:,.0f} = {expected_moic}"
                )
        return errors


@dataclass
class ScenarioOutput:
    """5-scenario set with cross-validation."""
    scenarios: List[Scenario] = field(default_factory=list)
    purchase_price: float = 0.0
    hard_floor_mid: float = 0.0
    scenario_narratives: List[dict] = field(default_factory=list)
    # Audit
    deepseek_raw: str = ""
    openrouter_raw: str = ""
    mistral_raw: str = ""
    synthesis_raw: str = ""
    v3_scenarios: dict = field(default_factory=dict)  # v3 formula-driven scenarios

    def validate(self) -> List[str]:
        """Validate all scenarios."""
        errors = []
        if len(self.scenarios) != 5:
            errors.append(f"Expected 5 scenarios, got {len(self.scenarios)}")
        prob_sum = sum(s.probability for s in self.scenarios)
        if abs(prob_sum - 1.0) > 0.015:
            errors.append(f"Probabilities sum to {prob_sum}, expected 1.0")
        for s in self.scenarios:
            errors.extend(s.validate(self.purchase_price))
        return errors


@dataclass
class LegalOutput:
    """Legal/concealment risk analysis."""
    risk_score: float = 5.0
    risk_level: str = "MODERATE"
    environmental_liability_estimate: float = 0.0
    concealment_flags: List[str] = field(default_factory=list)
    top_3_risks: List[str] = field(default_factory=list)
    legal_due_diligence_required: List[str] = field(default_factory=list)
    insurance_red_flags: List[str] = field(default_factory=list)
    tax_reassessment_risk: str = ""
    summary: str = ""
    # Audit
    deepseek_raw: str = ""
    openrouter_raw: str = ""
    mistral_raw: str = ""
    synthesis_raw: str = ""
    v3_legal: dict = field(default_factory=dict)


@dataclass
class Lever:
    """A single business lever suggestion."""
    name: str = ""
    category: str = ""  # Revenue, Cost, Capital, Financing, Use-Change
    effort: str = "MEDIUM"
    noi_impact_pct: float = 0.0
    timeline_months: int = 0
    description: str = ""


@dataclass
class Recommendation:
    """Investment recommendation."""
    verdict: str = "ANALYZE"
    target_offer: float = 0.0
    walk_away: float = 0.0
    target_cap_rate: float = 0.0
    key_conditions: List[str] = field(default_factory=list)
    negotiation_strategy: str = ""
    single_biggest_risk: str = ""
    confidence: str = "MEDIUM"


@dataclass
class LeverOutput:
    """Levers + recommendation."""
    levers: List[Lever] = field(default_factory=list)
    recommendation: Recommendation = field(default_factory=Recommendation)
    offers: List[dict] = field(default_factory=list)
    # Audit
    deepseek_raw: str = ""
    openrouter_raw: str = ""
    mistral_raw: str = ""
    synthesis_raw: str = ""
    v3_levers: dict = field(default_factory=dict)


@dataclass
class ValuationOutput:
    """Valuation triangulation."""
    hard_floor_low: float = 0.0
    hard_floor_mid: float = 0.0
    hard_floor_high: float = 0.0
    stabilized_re_value: float = 0.0
    noi_reconstructed: Range = field(default_factory=Range)
    exit_cap_rate: float = 0.08
    approach_breakdown: str = ""
    pwev: float = 0.0
    # Audit
    deepseek_raw: str = ""
    openrouter_raw: str = ""
    mistral_raw: str = ""
    synthesis_raw: str = ""
    v3_valuation: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════
# Synthesis Output (K11)
# ═══════════════════════════════════════════════════════════

@dataclass
class SynthesisOutput:
    """Final validated, unified analysis."""
    moats: MoatOutput = field(default_factory=MoatOutput)
    scenarios: ScenarioOutput = field(default_factory=ScenarioOutput)
    legal_risk: LegalOutput = field(default_factory=LegalOutput)
    levers: LeverOutput = field(default_factory=LeverOutput)
    valuation: ValuationOutput = field(default_factory=ValuationOutput)
    # Audit
    validation_errors: List[str] = field(default_factory=list)
    divergences: List[str] = field(default_factory=list)  # v3 vs LLM disagreements
    learning_updates: dict = field(default_factory=dict)  # what v3 engines learned


# ═══════════════════════════════════════════════════════════
# Pipeline Input
# ═══════════════════════════════════════════════════════════

@dataclass
class DealInput:
    """Input to the pipeline: either a fixture or a URL to scrape."""
    source_type: str = ""  # "url", "fixture", "listing_id"
    source_value: str = ""  # URL, file path, or listing ID
