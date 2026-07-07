"""
v5 Cross-Validator — v3 engine ⨂ Triple-LLM comparison.

Wires the deterministic v3 engines (MoatScorer, LawyerBrain, ConvexityEngine,
valuation_triangulation, lever_analysis, _build_scenarios) into the v5 pipeline.

Each K6-K10 node:
  1. Runs the v3 deterministic engine
  2. Compares v3 output against LLM output
  3. Flags divergences (≥2pt moat gap, >25% scenario value gap, etc.)
  4. Returns merged output with v3 audit trail
"""

from typing import Dict, Any, List, Optional, Tuple
from .models import LiveContext, Range


def live_context_to_deal_dict(ctx: LiveContext) -> dict:
    """Convert v5 LiveContext into the flat dict format v3 engines expect."""
    ask = ctx.ask_price or 1
    sf = ctx.building_sf or 1

    return {
        "property": {
            "address": ctx.address,
            "city": ctx.city,
            "state": ctx.state,
            "price": ctx.ask_price,
            "sf": ctx.building_sf,
            "building_size_sf": ctx.building_sf,
            "building_sf": ctx.building_sf,
            "lot_acres": ctx.lot_acres,
            "lot_size_ac": ctx.lot_acres,
            "year_built": ctx.year_built,
            "building_class": ctx.building_class,
            "zoning": ctx.zoning,
            "property_type": ctx.property_type or "Retail",
            "days_on_market": ctx.days_on_market,
            "price_reduction": False,
            "municipality": ctx.city,
            "county": getattr(ctx, 'county', ''),
            "assessment_total": int(ask * 0.59),  # typical NJ assessment ratio
            "listing_id": ctx.listing_id,
        },
        "income": {
            "noi_estimated": int(ask * (ctx.cap_rate_estimated / 100 if ctx.cap_rate_estimated > 1
                                        else max(ctx.cap_rate_estimated, 0.06))),
            "noi_source": "ESTIMATED — from cap rate × ask",
            "noi": int(ask * (ctx.cap_rate_estimated / 100 if ctx.cap_rate_estimated > 1
                             else max(ctx.cap_rate_estimated, 0.06))),
            "cap_rate_est_pct": ctx.cap_rate_estimated,
            "rent_range_per_sf": f"${ctx.rent_psf_range.low:.0f}-${ctx.rent_psf_range.high:.0f}/SF",
            "gross_rent_estimated": int(sf * ctx.rent_psf_range.mid) if ctx.rent_psf_range.mid > 0 else 0,
        },
        "hard_asset_floor": {
            "low": int(ask * 0.35),
            "mid": int(ask * 0.45),
            "high": int(ask * 0.55),
        },
        "pricing": {
            "ask": ask,
            "hard_floor_low": int(ask * 0.35),
            "hard_floor_mid": int(ask * 0.45),
            "hard_floor_high": int(ask * 0.55),
            "floor_to_ask_pct": 45,
        },
        "tax": {
            "post_sale": {
                "annual_tax_estimated": int(ask * 0.022),
                "tax_increase_pct": 70,
            },
        },
        "tax_bomb": {
            "tax_increase_pct": 70,
            "current_tax_estimated": int(ask * 0.013),
            "post_sale_tax": int(ask * 0.022),
        },
        "leases": {
            "market_rent_psf": ctx.rent_psf_range.high if ctx.rent_psf_range.high > 0 else 20,
            "current_rent_psf": ctx.rent_psf_range.mid if ctx.rent_psf_range.mid > 0 else 16,
        },
        "market": {
            "submarket": ctx.city,
        },
        "purchase_price": ask,
        "exit_cap_rate": ctx.cap_rate_estimated / 100 if ctx.cap_rate_estimated > 1
                         else max(ctx.cap_rate_estimated, 0.08),
        "description": f"{ctx.property_type or 'Commercial'} property at {ctx.address}. "
                       f"Built {ctx.year_built}. {ctx.building_sf:,} SF. "
                       f"Zoning: {ctx.zoning}. Class: {ctx.building_class}.",
    }


def build_county_profile(ctx: LiveContext) -> dict:
    """Build county_profile dict for MoatScorer from LiveContext."""
    return {
        "median_hhi": ctx.county_median_income or 103500,
        "population": ctx.county_population or 23000,
        "unemployment_pct": ctx.county_unemployment_pct or 4.0,
        "hpi_1yr_pct": ctx.hpi_1yr_pct or 3.0,
        "msa_name": ctx.msa_name or "",
    }


# ═══════════════════════════════════════════════════════
# Engine Callers
# ═══════════════════════════════════════════════════════

def run_v3_moats(ctx: LiveContext) -> dict:
    """Run v3 MoatScorer and return normalized scores dict."""
    from cre_underwriting.enhanced import MoatScorer

    deal = live_context_to_deal_dict(ctx)
    county = build_county_profile(ctx)
    scorecard = MoatScorer.score(deal, county)

    scores = {}
    for dim in scorecard.dimensions:
        # Map dimension names to LLM schema keys
        key = _moat_dimension_to_key(dim.name)
        scores[key] = {"score": dim.score, "rationale": dim.rationale[:300]}

    return {
        "scores": scores,
        "total": scorecard.total_score,
        "classification": scorecard.classification,
        "verdict": scorecard.verdict_text,
        "strongest": scorecard.strongest,
        "weakest": scorecard.weakest,
    }


def run_v3_legal(ctx: LiveContext) -> dict:
    """Run v3 LawyerBrain and return normalized legal risk dict."""
    from cre_underwriting.lawyer_brain import LawyerBrain

    deal = live_context_to_deal_dict(ctx)
    lb = LawyerBrain()
    result = lb.analyze(deal)

    concealment_flags = [
        f"{f.get('risk','')}: {f.get('severity','')}"
        for f in result.get("concealment_flags", [])
    ]

    return {
        "risk_score": float(result.get("legal_risk_score", 5)),
        "risk_level": result.get("legal_risk_severity", "MODERATE"),
        "top_3_risks": concealment_flags[:3],
        "concealment_flags": concealment_flags,
        "summary": result.get("narrative", ""),
        "environmental_liability_estimate": float(result.get("env_liability_adjustment", 0)),
    }


def run_v3_scenarios(ctx: LiveContext) -> dict:
    """Run v3 _build_scenarios and return normalized scenarios list."""
    deal = live_context_to_deal_dict(ctx)
    purchase = ctx.ask_price or 1

    try:
        # _build_scenarios expects (deal_data, levers, valuation)
        # We pass empty levers/valuation since it handles defaults internally
        from cre_underwriting.orchestrator_v3 import CREPipelineV3

        # Create a minimal pipeline instance just for _build_scenarios
        class _MinimalPipeline(CREPipelineV3):
            def __init__(self):
                self.deal_data = deal

        pipe = _MinimalPipeline()
        pipe.deal_data = deal
        v3_scenarios = pipe._build_scenarios(deal, {}, {})

        scenarios_list = []
        prob_map = {
            "worst": 0.05, "baseline": 0.50,
            "phase 1": 0.25, "phase 2": 0.15, "phase 3": 0.05,
        }
        idx = 0
        for name, data in v3_scenarios.items():
            prob = prob_map.get(name.lower().split("—")[0].strip().split(" ")[0].lower(),
                               prob_map.get(name.lower().split(" ")[0], 0.20))
            scenarios_list.append({
                "name": name,
                "probability": prob,
                "noi": int(data.get("noi", 0) or 0),
                "exit_cap": deal.get("exit_cap_rate", 0.08),
                "exit_value": int(data.get("value", 0) or 0),
                "moic": float(data.get("moic_5yr", 0) or 0),
                "description": data.get("description", ""),
                "triggers": [name.split("—")[-1].strip() if "—" in name else ""],
                "key_assumptions": [],
            })
            idx += 1
        return {
            "scenarios": scenarios_list,
            "purchase_price": purchase,
            "hard_floor_mid": int(purchase * 0.45),
        }
    except Exception as e:
        # Fallback: simple formula-driven scenarios
        cap = max(ctx.cap_rate_estimated / 100 if ctx.cap_rate_estimated > 1
                  else (ctx.cap_rate_estimated or 0.08), 0.06)
        noi_est = int(purchase * cap)
        return {
            "scenarios": [
                {"name": "Worst Case — Distressed", "probability": 0.05,
                 "noi": int(noi_est * 0.6), "exit_cap": cap + 0.02,
                 "exit_value": int(purchase * 0.50), "moic": 0.50,
                 "description": "Distressed sale scenario", "triggers": [], "key_assumptions": []},
                {"name": "Baseline — Stable", "probability": 0.50,
                 "noi": noi_est, "exit_cap": cap,
                 "exit_value": int(noi_est / cap), "moic": round(noi_est / cap / purchase, 2),
                 "description": "Stable operations", "triggers": [], "key_assumptions": []},
                {"name": "Phase 1 — Optimize", "probability": 0.25,
                 "noi": int(noi_est * 1.15), "exit_cap": cap - 0.0025,
                 "exit_value": int(int(noi_est * 1.15) / (cap - 0.0025)),
                 "moic": round(int(noi_est * 1.15) / (cap - 0.0025) / purchase, 2),
                 "description": "Optimization scenario", "triggers": [], "key_assumptions": []},
                {"name": "Phase 2 — Expand", "probability": 0.15,
                 "noi": int(noi_est * 1.35), "exit_cap": cap - 0.005,
                 "exit_value": int(int(noi_est * 1.35) / (cap - 0.005)),
                 "moic": round(int(noi_est * 1.35) / (cap - 0.005) / purchase, 2),
                 "description": "Expansion scenario", "triggers": [], "key_assumptions": []},
                {"name": "Phase 3 — Strategic", "probability": 0.05,
                 "noi": int(noi_est * 1.50), "exit_cap": cap - 0.0075,
                 "exit_value": int(int(noi_est * 1.50) / (cap - 0.0075)),
                 "moic": round(int(noi_est * 1.50) / (cap - 0.0075) / purchase, 2),
                 "description": "Strategic exit", "triggers": [], "key_assumptions": []},
            ],
            "purchase_price": purchase,
            "hard_floor_mid": int(purchase * 0.45),
        }


def run_v3_levers(ctx: LiveContext) -> dict:
    """Run v3 lever_analysis and return normalized levers + recommendation."""
    from cre_underwriting.financial_levers import lever_analysis

    deal = live_context_to_deal_dict(ctx)
    purchase = ctx.ask_price or 1
    result = lever_analysis(deal, purchase)

    levers_list = []
    for l in result.get("levers", [])[:7]:
        levers_list.append({
            "name": l.get("name", ""),
            "category": l.get("category", "Revenue"),
            "effort": str(l.get("effort", "MEDIUM")).upper(),
            "noi_impact_pct": float(l.get("noi_impact_pct", l.get("revenue_impact_annual", 0) / 1000)),
            "timeline_months": int(l.get("timeline_months", 12)),
            "description": l.get("description", ""),
        })

    rec = result.get("recommendation", {})
    return {
        "levers": levers_list,
        "recommendation": {
            "verdict": rec.get("verdict", "ANALYZE"),
            "target_offer": rec.get("target_offer", int(purchase * 0.90)),
            "walk_away": rec.get("walk_away", int(purchase * 1.05)),
            "target_cap_rate": rec.get("target_cap_rate",
                                        ctx.cap_rate_estimated / 100 if ctx.cap_rate_estimated > 1 else 0.08),
            "key_conditions": rec.get("key_conditions", []),
            "negotiation_strategy": rec.get("negotiation_strategy", f"Start at {int(purchase*0.85):,}"),
            "single_biggest_risk": rec.get("single_biggest_risk", ""),
            "confidence": str(rec.get("confidence", "MEDIUM")).upper(),
        },
        "offers": rec.get("offers", []),
    }


def run_v3_valuation(ctx: LiveContext) -> dict:
    """Run v3 valuation_triangulation and return normalized valuation dict."""
    from cre_underwriting.valuation import valuation_triangulation

    deal = live_context_to_deal_dict(ctx)
    result = valuation_triangulation(deal)

    return {
        "hard_floor_low": float(result.get("hard_floor_low", 0) or 0),
        "hard_floor_mid": float(result.get("hard_floor_mid", 0) or 0),
        "hard_floor_high": float(result.get("hard_floor_high", 0) or 0),
        "stabilized_re_value": float(result.get("stabilized_re_value", 0) or 0),
        "noi_reconstructed": result.get("noi_reconstructed", {}),
        "exit_cap_rate": float(result.get("exit_cap_rate", ctx.cap_rate_estimated / 100
                                          if ctx.cap_rate_estimated > 1 else 0.08)),
        "pwev": float(result.get("pwev", 0) or 0),
        "approach_breakdown": result.get("approach_breakdown", ""),
    }


# ═══════════════════════════════════════════════════════
# Cross-Validation Logic
# ═══════════════════════════════════════════════════════

def _moat_dimension_to_key(name: str) -> str:
    """Map v3 MoatDimension name to LLM schema key."""
    mapping = {
        "scarce transferable license": "license_barrier",
        "tourism corridor position": "tourism_corridor",
        "multi-revenue-stream parcel": "multi_revenue",
        "zoning optionality": "zoning_optionality",
        "rent-to-market gap": "rent_gap",
        "brand longevity & goodwill": "brand_value",
        "asset stack coverage": "asset_stack",
        "seller asymmetry": "seller_asymmetry",
    }
    return mapping.get(name.lower(), name.lower().replace(" ", "_"))


def cross_validate_moats(llm_result: dict, ctx: LiveContext) -> Tuple[dict, List[str]]:
    """Cross-validate moats: v3 vs LLM. Returns (merged, divergence_flags)."""
    try:
        v3 = run_v3_moats(ctx)
    except Exception as e:
        return llm_result, [f"v3 MoatScorer failed: {e}"]

    divergences = []
    llm_scores = llm_result.get("scores", {})
    v3_scores = v3.get("scores", {})

    for key in v3_scores:
        if key not in llm_scores:
            llm_scores[key] = v3_scores[key]
            continue
        v3_score = v3_scores[key].get("score", 0)
        llm_score = llm_scores[key].get("score", 0) if isinstance(llm_scores[key], dict) else llm_scores[key]
        if isinstance(llm_score, dict):
            llm_score = llm_score.get("score", 0)
        gap = abs(v3_score - llm_score)
        if gap >= 2:
            divergences.append(
                f"Moat '{key}': v3={v3_score}/3 vs LLM={llm_score}/3 (Δ{gap})"
            )

    # Merge: prefer LLM scores but flag divergences
    merged = dict(llm_result)
    merged["scores"] = llm_scores
    merged["v3_scores"] = v3_scores
    merged["v3_total"] = v3.get("total", 0)
    merged["v3_classification"] = v3.get("classification", "")

    # If ≥3 dimensions diverge, mark as HIGH divergence
    if len(divergences) >= 3:
        merged["divergence_level"] = "HIGH"
    elif len(divergences) >= 1:
        merged["divergence_level"] = "MODERATE"

    return merged, divergences


def cross_validate_scenarios(llm_result: dict, ctx: LiveContext) -> Tuple[dict, List[str]]:
    """Cross-validate scenarios: v3 vs LLM. Returns (merged, divergence_flags)."""
    try:
        v3 = run_v3_scenarios(ctx)
    except Exception as e:
        return llm_result, [f"v3 _build_scenarios failed: {e}"]

    divergences = []
    llm_scens = llm_result.get("scenarios", [])
    v3_scens = v3.get("scenarios", [])

    # Pair-match by position
    for i in range(min(len(llm_scens), len(v3_scens))):
        llm_ev = llm_scens[i].get("exit_value", 0)
        v3_ev = v3_scens[i].get("exit_value", 0)
        if llm_ev > 0 and v3_ev > 0:
            pct_diff = abs(llm_ev - v3_ev) / max(llm_ev, v3_ev) * 100
            if pct_diff > 25:
                divergences.append(
                    f"Scenario position {i}: LLM=${llm_ev:,} vs v3=${v3_ev:,} ({pct_diff:.0f}% gap)"
                )

    merged = dict(llm_result)
    merged["v3_scenarios"] = v3_scens
    merged["scenario_divergence_count"] = len(divergences)

    return merged, divergences


def cross_validate_legal(llm_result: dict, ctx: LiveContext) -> Tuple[dict, List[str]]:
    """Cross-validate legal: v3 LawyerBrain vs LLM. Returns (merged, divergence_flags)."""
    try:
        v3 = run_v3_legal(ctx)
    except Exception as e:
        return llm_result, [f"v3 LawyerBrain failed: {e}"]

    divergences = []
    llm_score = llm_result.get("risk_score", 5.0)
    v3_score = v3.get("risk_score", 5.0)

    if abs(llm_score - v3_score) >= 3:
        divergences.append(
            f"Legal risk: LLM={llm_score}/10 vs v3={v3_score}/10 (Δ{abs(llm_score-v3_score):.0f})"
        )

    # v3 concealment flags that LLM missed
    v3_flags = set(v3.get("concealment_flags", []))
    llm_flags = set(llm_result.get("concealment_flags", []) or llm_result.get("top_3_risks", []))
    v3_only = v3_flags - llm_flags
    for flag in list(v3_only)[:3]:
        divergences.append(f"v3 LawyerBrain caught: {flag[:100]}")

    merged = dict(llm_result)
    merged["v3_legal_risk_score"] = v3_score
    merged["v3_concealment_flags"] = list(v3_flags)

    return merged, divergences


def cross_validate_levers(llm_result: dict, ctx: LiveContext) -> Tuple[dict, List[str]]:
    """Cross-validate levers: v3 lever_analysis vs LLM. Returns (merged, divergence_flags)."""
    try:
        v3 = run_v3_levers(ctx)
    except Exception as e:
        return llm_result, [f"v3 lever_analysis failed: {e}"]

    divergences = []
    llm_rec = llm_result.get("recommendation", {})
    v3_rec = v3.get("recommendation", {})

    if llm_rec.get("verdict") != v3_rec.get("verdict"):
        divergences.append(
            f"Recommendation verdict: LLM={llm_rec.get('verdict')} vs v3={v3_rec.get('verdict')}"
        )

    merged = dict(llm_result)
    merged["v3_levers"] = v3.get("levers", [])
    merged["v3_recommendation"] = v3_rec

    return merged, divergences


def cross_validate_valuation(llm_result: dict, ctx: LiveContext) -> Tuple[dict, List[str]]:
    """Cross-validate valuation: v3 valuation_triangulation vs LLM."""
    try:
        v3 = run_v3_valuation(ctx)
    except Exception as e:
        return llm_result, [f"v3 valuation_triangulation failed: {e}"]

    divergences = []
    llm_hf = llm_result.get("hard_floor_mid", 0)
    v3_hf = v3.get("hard_floor_mid", 0)

    if llm_hf > 0 and v3_hf > 0:
        pct_diff = abs(llm_hf - v3_hf) / max(llm_hf, v3_hf) * 100
        if pct_diff > 20:
            divergences.append(
                f"Hard floor: LLM=${llm_hf:,.0f} vs v3=${v3_hf:,.0f} ({pct_diff:.0f}% gap)"
            )

    merged = dict(llm_result)
    merged["v3_hard_floor_mid"] = v3_hf
    merged["v3_stabilized_re_value"] = v3.get("stabilized_re_value", 0)
    merged["v3_pwev"] = v3.get("pwev", 0)

    return merged, divergences


# ═══════════════════════════════════════════════════════
# Master Cross-Validation Entry Point
# ═══════════════════════════════════════════════════════

CROSS_VALIDATORS = {
    "moats": cross_validate_moats,
    "scenarios": cross_validate_scenarios,
    "legal": cross_validate_legal,
    "levers": cross_validate_levers,
    "valuation": cross_validate_valuation,
}


def run_cross_validation(analysis_name: str, llm_result: dict, ctx: LiveContext) -> Tuple[dict, List[str]]:
    """Run v3 engine for a given analysis node and cross-validate against LLM output.

    Args:
        analysis_name: One of "moats", "scenarios", "legal", "levers", "valuation"
        llm_result: The result dict from the LLM analysis function
        ctx: LiveContext with deal data

    Returns:
        (merged_result, divergence_flags) — merged has both llm and v3 data
    """
    validator = CROSS_VALIDATORS.get(analysis_name)
    if validator is None:
        return llm_result, []
    return validator(llm_result, ctx)
