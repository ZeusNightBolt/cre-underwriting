"""v4 data models — LiveContext flows through all pipeline nodes."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class LiveContext:
    """All live-fetched and LLM-analyzed data for a deal.

    Populated progressively as the pipeline executes each node.
    Every field has a source attribution for audit trail.
    """

    # ── FRED economic data ──
    msa_name: str = ""
    msa_hpi_1yr_pct: Optional[float] = None
    msa_hpi_5yr_annualized_pct: Optional[float] = None
    msa_hpi_source: str = ""
    county_median_income: Optional[int] = None
    county_income_source: str = ""
    county_unemployment_pct: Optional[float] = None
    county_unemployment_source: str = ""
    county_population: Optional[int] = None
    county_population_growth_pct: Optional[float] = None
    county_population_source: str = ""

    # ── Web search findings ──
    recent_area_sales: list = field(default_factory=list)
    corridor_news: list = field(default_factory=list)
    zoning_changes: list = field(default_factory=list)
    development_plans: list = field(default_factory=list)
    environmental_findings: list = field(default_factory=list)
    tax_assessment_raw: dict = field(default_factory=dict)

    # ── LLM analyses (triple-perspective) ──
    moat_analysis: dict = field(default_factory=dict)
    scenario_analysis: dict = field(default_factory=dict)
    legal_risk_analysis: dict = field(default_factory=dict)
    lever_suggestions: dict = field(default_factory=dict)
    recommendation: dict = field(default_factory=dict)

    # ── Comps (from all sources) ──
    loopnet_comps: list = field(default_factory=list)
    web_search_comps: list = field(default_factory=list)
    synthetic_comps: list = field(default_factory=list)
    unified_comps: list = field(default_factory=list)

    # ── Audit ──
    analysis_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data_sources: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dict for dashboard compatibility."""
        return {
            "msa_name": self.msa_name,
            "msa_hpi_1yr_pct": self.msa_hpi_1yr_pct,
            "msa_hpi_5yr_annualized_pct": self.msa_hpi_5yr_annualized_pct,
            "county_median_income": self.county_median_income,
            "county_unemployment_pct": self.county_unemployment_pct,
            "county_population_growth_pct": self.county_population_growth_pct,
            "recent_area_sales_count": len(self.recent_area_sales),
            "corridor_news_count": len(self.corridor_news),
            "zoning_changes_count": len(self.zoning_changes),
            "development_plans_count": len(self.development_plans),
            "environmental_flags": len(self.environmental_findings),
            "analysis_timestamp": self.analysis_timestamp,
            "data_sources": self.data_sources,
            "warnings": self.warnings,
        }


@dataclass
class DealContext:
    """The original deal data + pipeline-computed metrics."""
    # Raw deal input
    deal_data: dict = field(default_factory=dict)

    # Extracted
    address: str = ""
    city: str = ""
    state: str = ""
    property_type: str = ""
    ask_price: float = 0.0
    sf: float = 0.0
    lot_acres: float = 0.0
    year_built: int = 0
    zoning: str = ""
    county: str = ""

    # Computed
    hard_floor_low: float = 0.0
    hard_floor_mid: float = 0.0
    hard_floor_high: float = 0.0
    noi: float = 0.0
    cap_rate: float = 0.0
    purchase_price: float = 0.0
    capital_invested: float = 0.0
