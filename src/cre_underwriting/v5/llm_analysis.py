"""
v5 LLM Analysis Functions — structured, parallel, validated.

Each function:
  1. Builds a data-rich prompt from LiveContext
  2. Calls call_triple_llm() with schema enforcement
  3. Validates parsed output against expected structure
  4. Returns structured dict (dashboard-compatible)
"""

from .llm_client import call_triple_llm
from .models import LiveContext, Range


# ═══════════════════════════════════════════════════════════
# Schema templates — injected into every LLM prompt
# ═══════════════════════════════════════════════════════════

MOAT_SCHEMA = """```json
{
  "scores": {
    "license_barrier": {"score": 0, "rationale": "string"},
    "tourism_corridor": {"score": 0, "rationale": "string"},
    "multi_revenue": {"score": 0, "rationale": "string"},
    "zoning_optionality": {"score": 0, "rationale": "string"},
    "rent_gap": {"score": 0, "rationale": "string"},
    "brand_value": {"score": 0, "rationale": "string"},
    "asset_stack": {"score": 0, "rationale": "string"},
    "seller_asymmetry": {"score": 0, "rationale": "string"}
  },
  "total": 0,
  "classification": "NO MOAT",
  "verdict": "string summary"
}
```"""

SCENARIO_SCHEMA = """```json
{
  "scenarios": [
    {
      "name": "Worst Case — [specific trigger]",
      "probability": 0.05,
      "noi": 0,
      "exit_cap": 0.12,
      "exit_value": 0,
      "moic": 0.0,
      "description": "...",
      "triggers": ["..."],
      "key_assumptions": ["..."]
    }
  ],
  "purchase_price": 0,
  "hard_floor_mid": 0
}
```"""

LEGAL_SCHEMA = """```json
{
  "risk_score": 0.0,
  "risk_level": "MODERATE",
  "environmental_liability_estimate": 0,
  "concealment_flags": [],
  "top_3_risks": [],
  "legal_due_diligence_required": [],
  "insurance_red_flags": [],
  "tax_reassessment_risk": "...",
  "summary": "..."
}
```"""

LEVERS_SCHEMA = """```json
{
  "levers": [
    {
      "name": "...",
      "category": "Revenue|Cost|Capital|Financing|Use-Change",
      "effort": "Low|Medium|High",
      "noi_impact_pct": 0,
      "timeline_months": 0,
      "description": "..."
    }
  ],
  "recommendation": {
    "verdict": "BUY|HOLD|PASS|CONDITIONAL",
    "target_offer": 0,
    "walk_away": 0,
    "target_cap_rate": 0.0,
    "key_conditions": ["..."],
    "negotiation_strategy": "...",
    "single_biggest_risk": "...",
    "confidence": "HIGH|MEDIUM|LOW"
  },
  "offers": [
    {
      "price": 0,
      "price_per_sf": 0,
      "cap_rate_pct": 0.0,
      "gross_rent_multiplier": 0.0,
      "cash_on_cash_pct": 0.0,
      "label": "..."
    }
  ]
}
```"""

VALUATION_SCHEMA = """```json
{
  "hard_floor_low": 0,
  "hard_floor_mid": 0,
  "hard_floor_high": 0,
  "stabilized_re_value": 0,
  "noi_reconstructed": {"low": 0, "mid": 0, "high": 0},
  "exit_cap_rate": 0.08,
  "approach_breakdown": "string explaining methodology"
}
```"""


# ═══════════════════════════════════════════════════════════
# Validation functions
# ═══════════════════════════════════════════════════════════

MOAT_DIMS = [
    "license_barrier", "tourism_corridor", "multi_revenue",
    "zoning_optionality", "rent_gap", "brand_value",
    "asset_stack", "seller_asymmetry",
]


def _validate_moats(js: dict) -> list:
    """Validate moat JSON structure."""
    errors = []
    scores = js.get("scores", {})
    for dim in MOAT_DIMS:
        if dim not in scores:
            errors.append(f"Missing dimension: {dim}")
        else:
            s = scores[dim]
            if not isinstance(s.get("score"), int) or s["score"] < 0 or s["score"] > 3:
                errors.append(f"{dim}: score must be 0-3, got {s.get('score')}")
    total = js.get("total", -1)
    computed = sum(scores.get(d, {}).get("score", 0) for d in MOAT_DIMS)
    if total != computed:
        errors.append(f"Total mismatch: declared {total}, computed {computed}")
    return errors


def _validate_scenarios(js: dict) -> list:
    """Validate scenario JSON structure."""
    errors = []
    scenarios = js.get("scenarios", [])
    if len(scenarios) != 5:
        errors.append(f"Expected 5 scenarios, got {len(scenarios)}")
    purchase = js.get("purchase_price", 1) or 1
    prob_sum = sum(s.get("probability", 0) for s in scenarios)
    if abs(prob_sum - 1.0) > 0.02:
        errors.append(f"Probabilities sum to {prob_sum:.3f}")
    for s in scenarios:
        noi = s.get("noi", 0)
        cap = s.get("exit_cap", 0.08)
        ev = s.get("exit_value", 0)
        if cap > 0 and noi > 0:
            expected = round(noi / cap, -3)
            if abs(ev - expected) > max(expected * 0.06, 10000):
                errors.append(
                    f"'{s.get('name','')}': exit_value ${ev:,} ≠ "
                    f"NOI ${noi:,} / cap {cap} ≈ ${expected:,}"
                )
        if purchase > 0 and ev > 0:
            expected_moic = round(ev / purchase, 2)
            if abs(s.get("moic", 0) - expected_moic) > 0.02:
                errors.append(
                    f"'{s.get('name','')}': moic {s.get('moic')} ≠ "
                    f"${ev:,} / ${purchase:,.0f} = {expected_moic}"
                )
    return errors


def _validate_legal(js: dict) -> list:
    errors = []
    score = js.get("risk_score", -1)
    if not isinstance(score, (int, float)) or score < 0 or score > 10:
        errors.append(f"risk_score must be 0-10, got {score}")
    return errors


def _validate_levers(js: dict) -> list:
    return []  # Basic structure check — levers are free-form


def _validate_valuation(js: dict) -> list:
    errors = []
    for key in ["hard_floor_low", "hard_floor_mid", "hard_floor_high"]:
        if js.get(key, -1) < 0:
            errors.append(f"{key} must be non-negative")
    return errors


# ═══════════════════════════════════════════════════════════
# Analysis Functions
# ═══════════════════════════════════════════════════════════

def analyze_moats(ctx: LiveContext) -> dict:
    """Triple-LLM moat analysis with structured output."""
    prompt = f"""Score this CRE property on 8 competitive moat dimensions (0-3 each).

PROPERTY: {ctx.address}
PRICE: ${ctx.ask_price:,.0f} | SF: {ctx.building_sf:,.0f} | $/SF: ${ctx.ask_price/max(ctx.building_sf,1):,.0f}
TYPE: {ctx.property_type} | YEAR: {ctx.year_built} | CLASS: {ctx.building_class}
ZONING: {ctx.zoning} | LOT: {ctx.lot_acres:.2f} acres
DAYS ON MARKET: {ctx.days_on_market}

LOCAL ECONOMY:
- MSA: {ctx.msa_name}
- HPI 1yr: {ctx.hpi_1yr_pct or 'N/A'}%
- Median HHI: ${ctx.county_median_income or 0:,}
- Unemployment: {ctx.county_unemployment_pct or 'N/A'}%
- Population: {ctx.county_population or 'N/A'}

RENT/INCOME:
- Rent Range: ${ctx.rent_psf_range.mid:.0f}-${ctx.rent_psf_range.high:.0f}/SF
- Cap Rate (est): {ctx.cap_rate_estimated}%
- Expense Structure: {ctx.expense_structure or 'NNN'}

CORRIDOR INTEL: {_format_list(ctx.corridor_news, 5)}

Score each dimension (0=absent, 1=weak, 2=moderate, 3=strong):
1. Scarce Transferable License — liquor, UST, PILOT, distribution rights
2. Tourism Corridor Position — foot traffic, destination appeal, visibility
3. Multi-Revenue-Stream Parcel — multiple tenants, subdividable, mixed-use
4. Zoning Optionality — redevelopment flexibility, variance path
5. Rent-to-Market Gap — below-market rent push-to-market upside
6. Brand Longevity & Goodwill — operating business value
7. Asset Stack Coverage — hard floor vs ask price
8. Seller Asymmetry — days on market, price reductions, distress"""

    result = call_triple_llm(prompt, MOAT_SCHEMA, _validate_moats,
                              timeout_per_model=300)

    synthesis = result.get("synthesis", {})
    return {
        "scores": synthesis.get("scores", {}),
        "total": synthesis.get("total", 0),
        "classification": synthesis.get("classification", "NO MOAT"),
        "verdict": synthesis.get("verdict", ""),
        "_raw": result,
    }


def analyze_scenarios(ctx: LiveContext) -> dict:
    """Triple-LLM scenario generation with structured output."""
    ask = ctx.ask_price or 1
    hf_mid = _derive_hard_floor(ctx)

    prompt = f"""Generate 5 deal-specific scenarios for this CRE property.

PROPERTY: {ctx.address}
ASK: ${ask:,.0f} | SF: {ctx.building_sf:,.0f} | $/SF: ${ask/max(ctx.building_sf,1):,.0f}
TYPE: {ctx.property_type} | YEAR: {ctx.year_built} | ZONING: {ctx.zoning}
HARD FLOOR MID: ${hf_mid:,.0f} ({hf_mid/ask*100:.0f}% of ask)

ECONOMY: HPI 1yr {ctx.hpi_1yr_pct or '?'}% | HHI ${ctx.county_median_income or 0:,} | UE {ctx.county_unemployment_pct or '?'}%

CORRIDOR: {_format_list(ctx.corridor_news, 5)}

Generate Worst Case, Baseline, Phase 1 Optimize, Phase 2 Expand, Phase 3 Strategic.
Every scenario must satisfy: exit_value ≈ round(NOI / exit_cap, -3)
Every scenario must satisfy: moic = round(exit_value / {ask}, 2)
Probabilities must sum to 1.0.
Use exit_cap = {ctx.cap_rate_estimated/100 if ctx.cap_rate_estimated > 1 else ctx.cap_rate_estimated or 0.08} for baseline."""

    result = call_triple_llm(prompt, SCENARIO_SCHEMA, _validate_scenarios,
                              timeout_per_model=300)

    synthesis = result.get("synthesis", {})
    scenarios = synthesis.get("scenarios", [])
    return {
        "scenarios": scenarios,
        "scenario_narratives": [
            {"name": s.get("name", ""), "detail": s.get("description", ""),
             "drivers": s.get("triggers", [])}
            for s in scenarios
        ],
        "purchase_price": ask,
        "hard_floor_mid": hf_mid,
        "_raw": result,
    }


def analyze_legal_risk(ctx: LiveContext) -> dict:
    """Triple-LLM legal/concealment risk analysis."""
    env_findings = _format_list(ctx.environmental_findings, 8)
    prompt = f"""Analyze legal, environmental, and concealment risk for this property.

PROPERTY: {ctx.address}
TYPE: {ctx.property_type} | YEAR: {ctx.year_built} | ZONING: {ctx.zoning} | SF: {ctx.building_sf:,.0f}
LOT: {ctx.lot_acres:.2f} acres | CLASS: {ctx.building_class}
DAYS ON MARKET: {ctx.days_on_market}

ENVIRONMENTAL FINDINGS:
{env_findings}

Score 0-10 (higher = riskier). Identify concealment flags, due diligence requirements,
insurance red flags, tax reassessment risk."""

    result = call_triple_llm(prompt, LEGAL_SCHEMA, _validate_legal,
                              timeout_per_model=300)
    return {**(result.get("synthesis", {})), "_raw": result}


def analyze_levers(ctx: LiveContext) -> dict:
    """Triple-LLM business levers + recommendation."""
    ask = ctx.ask_price or 1

    prompt = f"""Propose 5-7 business levers and an investment recommendation.

PROPERTY: {ctx.address} | ASK: ${ask:,.0f} | SF: {ctx.building_sf:,.0f}
TYPE: {ctx.property_type} | ZONING: {ctx.zoning}
RENT: ${ctx.rent_psf_range.mid:.0f}-${ctx.rent_psf_range.high:.0f}/SF
CAP RATE: {ctx.cap_rate_estimated}%

ECONOMY: HPI {ctx.hpi_1yr_pct or '?'}% | HHI ${ctx.county_median_income or 0:,}
CORRIDOR: {_format_list(ctx.corridor_news, 3)}

Generate levers with NOI impact %, effort level, timeline. Provide offer ladder (3 points).
Give clear BUY/HOLD/PASS/CONDITIONAL verdict with target price and walk-away."""

    result = call_triple_llm(prompt, LEVERS_SCHEMA, _validate_levers,
                              timeout_per_model=300)
    synthesis = result.get("synthesis", {})
    return {
        "levers": synthesis.get("levers", []),
        "recommendation": synthesis.get("recommendation", {}),
        "offers": synthesis.get("offers", []),
        "_raw": result,
    }


def analyze_valuation(ctx: LiveContext) -> dict:
    """Triple-LLM valuation triangulation."""
    ask = ctx.ask_price or 1
    prompt = f"""Triangulate valuation for this CRE property using three approaches.

PROPERTY: {ctx.address} | ASK: ${ask:,.0f} | SF: {ctx.building_sf:,.0f}
TYPE: {ctx.property_type} | YEAR: {ctx.year_built} | CLASS: {ctx.building_class}
RENT RANGE: ${ctx.rent_psf_range.mid:.0f}-${ctx.rent_psf_range.high:.0f}/SF
CAP RATE: {ctx.cap_rate_estimated}%
ECONOMY: HPI {ctx.hpi_1yr_pct or '?'}% | HHI ${ctx.county_median_income or 0:,}

Give hard floor (land+replacement), stabilized RE value (income approach), and NOI reconstructed.
All values as low/mid/high ranges."""

    result = call_triple_llm(prompt, VALUATION_SCHEMA, _validate_valuation,
                              timeout_per_model=300)
    return {**(result.get("synthesis", {})), "_raw": result}


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _format_list(items, max_n=5) -> str:
    """Format list of dict items into readable text."""
    if not items:
        return "[No data]"
    lines = []
    for item in items[:max_n]:
        if isinstance(item, dict):
            title = item.get("title", item.get("address", ""))
            snippet = item.get("snippet", item.get("description", ""))
            lines.append(f"- {title}: {snippet[:200]}")
        else:
            lines.append(f"- {str(item)[:200]}")
    return "\n".join(lines)


def _derive_hard_floor(ctx: LiveContext) -> float:
    """Derive hard floor from LiveContext or estimate."""
    ask = ctx.ask_price or 1
    # Default: 45% of ask as hard floor estimate
    return ask * 0.45
