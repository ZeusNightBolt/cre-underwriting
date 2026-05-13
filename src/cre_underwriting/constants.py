"""
cre_underwriting.constants — All thresholds, mappings, and configuration values.

Centralizes magic numbers scattered across the codebase into named constants.
All thresholds are tunable without code changes. In production, these would be
loaded from a YAML/JSON config file, but for v1.0.0, Python constants are
sufficient and type-checkable.
"""

from dataclasses import dataclass


# ════════════════════════════════════════════════════════════════
# Convexity Thresholds
# ════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ConvexityThresholds:
    """Convexity ratio classification thresholds."""
    high: float = 2.5         # Ratio >= 2.5 → HIGH convexity
    positive: float = 1.5     # Ratio >= 1.5 → POSITIVE convexity
    marginal: float = 1.0     # Ratio >= 1.0 → MARGINAL convexity
    # Below 1.0 → NEGATIVE convexity

    # Verdict multipliers (used in generate_verdict)
    floor_target_multiplier: float = 1.15   # Hard floor × multiplier → target
    floor_conditional_multiplier: float = 1.25
    ask_walk_multiplier: float = 0.90       # Ask × multiplier → walk-away


CONVEXITY = ConvexityThresholds()


# ════════════════════════════════════════════════════════════════
# Moat Scoring Thresholds
# ════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MoatThresholds:
    """8-moat scoring classification thresholds."""
    wide_moat_min: int = 19      # ≥ 19 → WIDE MOAT
    narrow_moat_min: int = 12    # ≥ 12 → NARROW MOAT
    # Below 12 → NO MOAT
    max_total: int = 24          # 8 dimensions × 3 max each

    # Asset stack coverage (hard floor as % of ask)
    stack_high_pct: float = 66.0   # ≥ 66% → score 3
    stack_medium_pct: float = 50.0 # ≥ 50% → score 2
    stack_low_pct: float = 33.0    # ≥ 33% → score 1

    # Brand longevity (years)
    brand_long_years: int = 50     # 50+ years → score 3
    brand_medium_years: int = 30   # 30+ years → score 2
    brand_short_years: int = 10    # 10+ years → score 1

    # Rent-to-market gap percentages
    rent_gap_high_pct: float = 25.0  # ≥ 25% → score 3
    rent_gap_medium_pct: float = 10.0 # ≥ 10% → score 2


MOATS = MoatThresholds()


# ════════════════════════════════════════════════════════════════
# Offer Ladder Multipliers
# ════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class OfferThresholds:
    """Multipliers for generating offer price ladders from hard floor."""
    aggressive_multiplier: float = 1.35   # Aggressive target = floor × 1.35
    midpoint_multiplier: float = 1.65     # Midpoint = floor × 1.65
    walk_multiplier: float = 1.80         # Walk-away = floor × 1.80
    ask_cap_pct: float = 0.86            # Walk-away cap = ask × 0.86


OFFERS = OfferThresholds()


# ════════════════════════════════════════════════════════════════
# Geographic Tiers
# ════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TierConfig:
    """Cap rate minimums by geographic tier."""
    tier1_stabilized: float = 5.5     # NJ Tier 1 stabilized min cap rate
    tier1_value_add: float = 7.0      # NJ Tier 1 value-add min cap rate
    tier2_stabilized: float = 7.0     # PA/DE Tier 2 stabilized min
    tier2_value_add: float = 9.0      # PA/DE Tier 2 value-add min
    tier3_stabilized: float = 6.5     # Growth markets stabilized min


TIERS = TierConfig()

# Tier classification by NJ county
NJ_TIER1_COUNTIES = {
    "middlesex", "union", "somerset", "morris", "essex",
    "hudson", "bergen", "passaic", "mercer",
}


# ════════════════════════════════════════════════════════════════
# Scenario Name Categories
# ════════════════════════════════════════════════════════════════

SCENARIO_CATEGORIES = {
    "worst":  ["worst", "worst case", "scenario 1"],
    "base":   ["baseline", "base", "scenario 2", "as-is"],
    "best":   ["phase 2 expand", "phase 1 optimize",
               "best case", "best", "scenario 4", "scenario 5"],
}

# Default probability weights for PWEV
DEFAULT_PROBABILITIES = {
    "worst": 0.20,
    "base":  0.50,
    "best":  0.30,
}


# ════════════════════════════════════════════════════════════════
# Environmental Risk Thresholds
# ════════════════════════════════════════════════════════════════

# NJ counties with elevated flood risk
NJ_HIGH_FLOOD_RISK_COUNTIES = {
    "atlantic", "bergen", "cape may", "essex", "hudson",
    "middlesex", "monmouth", "ocean", "passaic", "union",
}

# UST risk classification by count
UST_RISK_THRESHOLDS = {
    "high": 2000,      # ≥ 2000 sites → high risk
    "medium": 1000,    # ≥ 1000 sites → medium risk
    "low": 500,        # ≥ 500 sites → low risk
}


# ════════════════════════════════════════════════════════════════
# Effective Frontier Zones
# ════════════════════════════════════════════════════════════════

FRONTIER_ZONES = {
    "pursue_aggressively": {"worst_max_pct": 25, "best_min_moic": 2.5},
    "acceptable_selectively": {"worst_min_pct": 25, "best_min_moic": 2.5},
    "pass_portfolio": {"worst_max_pct": 25, "best_max_moic": 2.5},
    "walk_away": {"worst_min_pct": 25, "best_max_moic": 2.5},
}
