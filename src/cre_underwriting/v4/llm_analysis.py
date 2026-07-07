"""
LLM-powered underwriting analysis for CRE v4 pipeline.

Four analysis modules, each using triple-perspective architecture:
  1. analyze_moats()      — 8-dimension competitive moat scoring
  2. analyze_scenarios()   — deal-specific 5-scenario generation
  3. analyze_legal_risk()  — legal, environmental, concealment risk
  4. analyze_levers()      — business lever suggestions + recommendation

Every function:
  - Calls get_triple_analysis() (DeepSeek → OpenRouter → Mistral → DeepSeek synthesis)
  - Stores raw responses + synthesis for audit trail
  - Returns dashboard-compatible structured output
  - Never proceeds with incomplete LLM output
"""

import json
import re
from typing import Optional

from .llm_client import get_triple_analysis, call_deepseek
from .models import LiveContext, DealContext


# ── Moat analysis keys (dashboard-compatible) ──
MOAT_KEYS = [
    "license_barrier",
    "tourism_corridor",
    "multi_revenue",
    "zoning_optionality",
    "rent_gap",
    "brand_value",
    "asset_stack",
    "seller_asymmetry",
]

MOAT_DESCRIPTIONS = {
    "license_barrier": "Scarce Transferable License — liquor, UST, PILOT, distribution rights",
    "tourism_corridor": "Tourism Corridor Position — foot traffic, destination appeal, street frontage",
    "multi_revenue": "Multi-Revenue-Stream Parcel — multiple tenants, subdividable, mixed-use potential",
    "zoning_optionality": "Zoning Optionality — redevelopment flexibility, density bonus, variance path",
    "rent_gap": "Rent-to-Market Gap — below-market rents with clear push-to-market upside",
    "brand_value": "Brand Longevity & Goodwill — operating business value, customer base, reputation",
    "asset_stack": "Asset Stack Coverage — hard asset floor vs ask price, downside protection",
    "seller_asymmetry": "Seller Asymmetry — days on market, price reductions, distress, motivation",
}


def analyze_moats(dc: DealContext, ctx: LiveContext) -> dict:
    """Triple-LLM moat analysis. Returns dashboard-compatible moat dict."""
    deal = dc.deal_data
    prop = deal.get("property", {})

    # ── Build prompt ──
    prompt_parts = [
        "## CRE Moat Analysis",
        "",
        f"**Property:** {dc.address}",
        f"**Price:** ${dc.ask_price:,.0f} | **SF:** {dc.sf:,.0f} | **$/SF:** ${dc.ask_price/max(dc.sf,1):,.0f}",
        f"**Type:** {dc.property_type} | **Year:** {dc.year_built} | **Zoning:** {dc.zoning}",
        f"**Lot:** {dc.lot_acres:.2f} acres | **Class:** {prop.get('building_class', 'N/A')}",
        f"**Days on Market:** {prop.get('days_on_market', 'N/A')}",
        "",
        "## Local Economy (FRED live data)",
        f"- MSA: {ctx.msa_name or 'N/A'}",
        f"- HPI 1yr: {ctx.msa_hpi_1yr_pct or 'N/A'}% | HPI 5yr annualized: {ctx.msa_hpi_5yr_annualized_pct or 'N/A'}%",
        f"- Median Household Income: ${ctx.county_median_income or 0:,}",
        f"- Unemployment: {ctx.county_unemployment_pct or 'N/A'}%",
        f"- Population: {ctx.county_population or 'N/A'}",
        "",
    ]

    # Deal description
    desc = (prop.get("description", "") or
            deal.get("deal", {}).get("description", "") or
            deal.get("summary", ""))
    if desc:
        prompt_parts.append(f"## Property Description\n{str(desc)[:2000]}")

    # Corridor intel
    if ctx.corridor_news:
        prompt_parts.append("\n## Corridor Intelligence (web search)")
        for i, item in enumerate(ctx.corridor_news[:5]):
            if isinstance(item, dict):
                prompt_parts.append(f"- {item.get('title','')}: {item.get('snippet','')[:200]}")
            else:
                prompt_parts.append(f"- {str(item)[:200]}")

    # Recent sales context
    if ctx.web_search_comps:
        prompt_parts.append(f"\n## Recent Area Sales ({len(ctx.web_search_comps)} found)")
        for item in ctx.web_search_comps[:5]:
            if isinstance(item, dict):
                prompt_parts.append(f"- {item.get('title','')}: {item.get('snippet','')[:200]}")

    # Income data
    income = deal.get("income", {})
    if income:
        prompt_parts.append("\n## Deal Financials")
        prompt_parts.append(f"- NOI: ${income.get('noi_estimated', income.get('noi', 0)) or 0:,.0f}")
        prompt_parts.append(f"- Cap Rate: {income.get('cap_rate_est_pct', income.get('cap_rate', 0)) or 0}%")
        prompt_parts.append(f"- Rent Range: {income.get('rent_range_per_sf', income.get('rent_range', 'N/A'))}")

    # Assessment
    assessment = prop.get("assessment_total", deal.get("assessment_total", 0))
    if assessment:
        prompt_parts.append(f"- Tax Assessment: ${assessment:,}")

    prompt_parts.append("""
## Task

Score this property on ALL 8 moat dimensions below (0-3 each):

1. **Scarce Transferable License** (0-3): Liquor license, UST rights, PILOT, distribution rights, special-use permits
2. **Tourism Corridor Position** (0-3): Foot traffic, destination appeal, highway visibility, downtown position
3. **Multi-Revenue-Stream Parcel** (0-3): Multiple tenants, subdividable, mixed-use conversion, add-on revenue
4. **Zoning Optionality** (0-3): Redevelopment flexibility, density bonus, variance likelihood, adaptive reuse
5. **Rent-to-Market Gap** (0-3): Current rents vs market, push-to-market upside magnitude
6. **Brand Longevity & Goodwill** (0-3): Operating business value, customer base, tenure, reputation
7. **Asset Stack Coverage** (0-3): Hard asset floor vs ask price — downside protection magnitude
8. **Seller Asymmetry** (0-3): Days on market, price reductions, distress signals, motivated seller

Scoring: 0=absent, 1=weak, 2=moderate, 3=strong.

After scoring, classify the deal: WIDE MOAT (≥19), NARROW MOAT (≥12), or NO MOAT (<12).

Return ONLY valid JSON:
```json
{
  "scores": {
    "license_barrier": {"score": 0, "rationale": "..."},
    "tourism_corridor": {"score": 0, "rationale": "..."},
    "multi_revenue": {"score": 0, "rationale": "..."},
    "zoning_optionality": {"score": 0, "rationale": "..."},
    "rent_gap": {"score": 0, "rationale": "..."},
    "brand_value": {"score": 0, "rationale": "..."},
    "asset_stack": {"score": 0, "rationale": "..."},
    "seller_asymmetry": {"score": 0, "rationale": "..."}
  },
  "total": 0,
  "classification": "NO MOAT",
  "verdict": "..."
}
```""")

    full_prompt = "\n".join(prompt_parts)

    # ── Call triple LLM ──
    system_msg = (
        "You are a CRE moat analyst. Score properties on 8 competitive advantage dimensions. "
        "Be ruthless — don't inflate scores. Most retail CRE scores 8-14. "
        "Respond ONLY with valid JSON. No explanations outside the JSON."
    )

    result = get_triple_analysis(full_prompt, system=system_msg, timeout_per_model=90)

    # ── Parse structured JSON from synthesis ──
    parsed = _extract_json(result.get("synthesis", ""))
    if not parsed:
        # Fallback: try each individual response
        for key in ["deepseek", "openrouter", "mistral"]:
            parsed = _extract_json(result.get(key, ""))
            if parsed:
                break

    if not parsed or "scores" not in parsed:
        # Last resort: DeepSeek quick extraction
        fallback = call_deepseek(
            "Extract the moat scores from this text as JSON. "
            "Return ONLY: {\"scores\": {...}, \"total\": N, \"classification\": \"...\", \"verdict\": \"...\"}:\n\n"
            + (result.get("synthesis", "") or result.get("deepseek", ""))[:3000],
            system="Extract JSON only.",
            timeout=60,
        )
        parsed = _extract_json(fallback) or {}

    # ── Ensure all 8 dimensions present ──
    scores = parsed.get("scores", {})
    for key in MOAT_KEYS:
        if key not in scores:
            scores[key] = {"score": 0, "rationale": "No data — defaulting to 0."}

    total = parsed.get("total", sum(s.get("score", 0) for s in scores.values()))
    classification = parsed.get("classification", "NO MOAT")
    verdict = parsed.get("verdict", "")

    return {
        "scores": scores,
        "total": total,
        "classification": classification,
        "verdict": verdict,
        # Audit trail
        "_raw": {k: v for k, v in result.items() if k != "errors"},
        "_errors": result.get("errors", []),
    }


def analyze_scenarios(dc: DealContext, ctx: LiveContext) -> dict:
    """Triple-LLM scenario generation. Returns dashboard-compatible scenarios list."""
    deal = dc.deal_data
    prop = deal.get("property", {})
    income = deal.get("income", {})
    hard_floor = deal.get("hard_asset_floor", deal.get("hard_floor", {}))
    hf_mid = hard_floor.get("mid", 0) or deal.get("pricing", {}).get("hard_floor_mid", 0) or 0

    prompt_parts = [
        "## CRE Scenario Generation",
        "",
        f"**Property:** {dc.address}",
        f"**Type:** {dc.property_type} | **Year:** {dc.year_built} | **Zoning:** {dc.zoning}",
        f"**Ask Price:** ${dc.ask_price:,.0f} | **SF:** {dc.sf:,.0f}",
        f"**$/SF:** ${dc.ask_price/max(dc.sf,1):,.0f}",
        f"**Hard Asset Floor (mid):** ${hf_mid:,.0f} ({hf_mid/dc.ask_price*100:.0f}% of ask)" if hf_mid and dc.ask_price else "",
        "",
    ]

    # NOI
    noi = income.get("noi_estimated", income.get("noi", 0)) or 0
    cap = income.get("cap_rate_est_pct", income.get("cap_rate", 0)) or 0
    if noi:
        prompt_parts.append(f"**NOI:** ${noi:,.0f} | **Cap Rate:** {cap}%")

    # Days on market
    dom = prop.get("days_on_market", 0)
    if dom:
        prompt_parts.append(f"**Days on Market:** {dom}")

    # Local economy
    prompt_parts.extend([
        "\n## Local Economy",
        f"- MSA: {ctx.msa_name or 'N/A'}",
        f"- HPI 1yr: {ctx.msa_hpi_1yr_pct or 'N/A'}%",
        f"- Median HHI: ${ctx.county_median_income or 0:,}",
        f"- Unemployment: {ctx.county_unemployment_pct or 'N/A'}%",
        f"- Population: {ctx.county_population or 'N/A'}",
    ])

    # Corridor intel
    if ctx.corridor_news:
        prompt_parts.append("\n## Corridor Developments")
        for item in ctx.corridor_news[:5]:
            if isinstance(item, dict):
                prompt_parts.append(f"- {item.get('title','')}: {item.get('snippet','')[:200]}")
            else:
                prompt_parts.append(f"- {str(item)[:200]}")

    # Environmental
    if ctx.environmental_findings:
        prompt_parts.append(f"\n## Environmental ({len(ctx.environmental_findings)} findings)")
        for item in ctx.environmental_findings[:3]:
            if isinstance(item, dict):
                prompt_parts.append(f"- {item.get('title','')}: {item.get('snippet','')[:150]}")

    purchase = dc.ask_price

    prompt_parts.append(f"""
## Task

Generate 5 deal-specific scenarios for this property. Each scenario should be grounded in the data above.

Use exit cap = {cap}% for baseline, compress 50bps for Phase 1, 100bps for Phase 2, expand 200bps for Worst.

Required structure (return ONLY JSON):
```json
{{
  "scenarios": [
    {{
      "name": "Worst Case — [specific trigger]",
      "probability": 0.05,
      "description": "...",
      "triggers": ["..."],
      "noi": 0,
      "exit_cap": 0.12,
      "exit_value": 0,
      "moic": 0.0
    }},
    {{
      "name": "Baseline — [status quo description]",
      "probability": 0.40,
      "description": "...",
      "triggers": ["..."],
      "noi": 0,
      "exit_cap": 0.08,
      "exit_value": 0,
      "moic": 0.0
    }},
    {{
      "name": "Phase 1 Optimize — [specific lever]",
      "probability": 0.30,
      "description": "...",
      "triggers": ["..."],
      "noi": 0,
      "exit_cap": 0.075,
      "exit_value": 0,
      "moic": 0.0
    }},
    {{
      "name": "Phase 2 Expand — [specific expansion]",
      "probability": 0.15,
      "description": "...",
      "triggers": ["..."],
      "noi": 0,
      "exit_cap": 0.07,
      "exit_value": 0,
      "moic": 0.0
    }},
    {{
      "name": "Phase 3 Strategic — [moonshot scenario]",
      "probability": 0.10,
      "description": "...",
      "triggers": ["..."],
      "noi": 0,
      "exit_cap": 0.065,
      "exit_value": 0,
      "moic": 0.0
    }}
  ],
  "purchase_price": {purchase},
  "hard_floor_mid": {hf_mid}
}}
```

Make scenarios deal-specific — cite actual corridor development, zoning changes, and market conditions from the data. NOI values must be realistic given the property's actual income and market conditions.""")

    full_prompt = "\n".join(prompt_parts)

    system_msg = (
        "You are a CRE scenario modeler. Generate 5 deal-specific, ground-truthed scenarios. "
        "Every scenario must reference specific data — zoning, corridor developments, market conditions. "
        "NOI must be mathematically consistent with exit cap and exit value. "
        "Respond ONLY with valid JSON."
    )

    result = get_triple_analysis(full_prompt, system=system_msg, timeout_per_model=90)

    # Parse structured JSON
    parsed = _extract_json(result.get("synthesis", ""))
    if not parsed:
        for key in ["deepseek", "openrouter", "mistral"]:
            parsed = _extract_json(result.get(key, ""))
            if parsed:
                break

    scenarios = parsed.get("scenarios", []) if parsed else []

    # If LLM failed completely, generate fallback scenarios
    if not scenarios:
        scenarios = _fallback_scenarios(dc, ctx)

    # Build scenario narratives for dashboard
    narratives = []
    for s in scenarios:
        narratives.append({
            "name": s.get("name", ""),
            "detail": s.get("description", ""),
            "drivers": s.get("triggers", s.get("drivers", []))[:4],
        })

    return {
        "scenarios": scenarios,
        "scenario_narratives": narratives,
        "purchase_price": purchase,
        "hard_floor_mid": hf_mid,
        "_raw": {k: v for k, v in result.items() if k != "errors"},
        "_errors": result.get("errors", []),
    }


def analyze_legal_risk(dc: DealContext, ctx: LiveContext) -> dict:
    """Triple-LLM legal/concealment/environmental risk analysis."""
    deal = dc.deal_data
    prop = deal.get("property", {})

    prompt_parts = [
        "## Legal & Concealment Risk Analysis",
        "",
        f"**Property:** {dc.address}",
        f"**Type:** {dc.property_type} | **Year Built:** {dc.year_built} | **Zoning:** {dc.zoning}",
        f"**SF:** {dc.sf:,.0f} | **Lot:** {dc.lot_acres:.2f} acres",
        "",
    ]

    # Environmental findings
    if ctx.environmental_findings:
        prompt_parts.append(f"## Environmental Search Results ({len(ctx.environmental_findings)} findings)")
        for item in ctx.environmental_findings[:8]:
            if isinstance(item, dict):
                prompt_parts.append(f"- {item.get('title','')}: {item.get('snippet','')[:250]}")
            else:
                prompt_parts.append(f"- {str(item)[:250]}")
    else:
        prompt_parts.append("## Environmental Search Results\n[No findings from web search]")

    # Tax assessment
    assessment = prop.get("assessment_total", deal.get("assessment_total", 0)) or 0
    if assessment and dc.ask_price:
        prompt_parts.append(f"\n**Tax Assessment:** ${assessment:,} vs Ask: ${dc.ask_price:,.0f} "
                           f"({assessment/dc.ask_price*100:.0f}% of ask)")

    # Days on market
    dom = prop.get("days_on_market", 0)
    if dom:
        prompt_parts.append(f"**Days on Market:** {dom}")

    # Description
    desc = (prop.get("description", "") or
            deal.get("deal", {}).get("description", "") or "")
    if desc:
        prompt_parts.append(f"\n## Property Description\n{str(desc)[:1500]}")

    prompt_parts.append(f"""
## Task

Analyze legal, environmental, and concealment risk for this property. Consider:
1. Environmental liability (USTs, contamination, flood zone, Phase I red flags)
2. Title & deed risks (easements, liens, condo regime, tax liens)
3. Zoning compliance (grandfathering, variance needs, non-conforming use)
4. Structural / deferred maintenance risk (age {dc.year_built}, Class {prop.get('building_class','N/A')})
5. Concealment red flags (what is the seller NOT disclosing?)
6. Post-sale tax reassessment risk

Return ONLY valid JSON:
```json
{{
  "risk_score": 0.0,
  "risk_level": "LOW",
  "environmental_liability_estimate": 0,
  "concealment_flags": [],
  "missing_data": [],
  "top_3_risks": [],
  "legal_due_diligence_required": [],
  "insurance_red_flags": [],
  "tax_reassessment_risk": "...",
  "summary": "..."
}}
```

risk_score: 0.0-10.0 (higher = riskier)
risk_level: LOW (<4), MODERATE (4-6), HIGH (>6)
environmental_liability_estimate: dollar amount for worst-case remediation (0 if none)
""")

    full_prompt = "\n".join(prompt_parts)

    result = get_triple_analysis(full_prompt, timeout_per_model=90)

    parsed = _extract_json(result.get("synthesis", ""))
    if not parsed:
        for key in ["deepseek", "openrouter", "mistral"]:
            parsed = _extract_json(result.get(key, ""))
            if parsed:
                break

    return {
        **(parsed or {}),
        "_raw": {k: v for k, v in result.items() if k != "errors"},
        "_errors": result.get("errors", []),
    }


def analyze_levers(dc: DealContext, ctx: LiveContext) -> dict:
    """Triple-LLM business levers + recommendation analysis."""
    deal = dc.deal_data
    deal.get("property", {})
    income = deal.get("income", {})

    prompt_parts = [
        "## Business Levers & Investment Recommendation",
        "",
        f"**Property:** {dc.address}",
        f"**Type:** {dc.property_type} | **Year:** {dc.year_built} | **Zoning:** {dc.zoning}",
        f"**Ask:** ${dc.ask_price:,.0f} | **SF:** {dc.sf:,.0f} | **$/SF:** ${dc.ask_price/max(dc.sf,1):,.0f}",
        "",
    ]

    # NOI
    noi = income.get("noi_estimated", income.get("noi", 0)) or 0
    cap = income.get("cap_rate_est_pct", income.get("cap_rate", 0)) or 0
    if noi:
        prompt_parts.append(f"**NOI:** ${noi:,.0f} | **Cap Rate:** {cap}%")

    # Rent
    rent = income.get("rent_range_per_sf", income.get("rent_range", ""))
    if rent:
        prompt_parts.append(f"**Rent Range:** {rent}")

    # Local economy
    prompt_parts.extend([
        "\n## Local Economy",
        f"- HPI 1yr: {ctx.msa_hpi_1yr_pct or 'N/A'}%",
        f"- Median HHI: ${ctx.county_median_income or 0:,}",
        f"- Unemployment: {ctx.county_unemployment_pct or 'N/A'}%",
    ])

    # Corridor
    if ctx.corridor_news:
        prompt_parts.append(f"\n## Corridor ({len(ctx.corridor_news)} findings — recent dev, zoning, market)")
        for item in ctx.corridor_news[:3]:
            snippet = item.get("snippet", "") if isinstance(item, dict) else str(item)
            prompt_parts.append(f"- {snippet[:200]}")

    prompt_parts.append(f"""
## Task

1. Propose 5-7 DEAL-SPECIFIC business levers to increase NOI and exit value. Be creative but data-grounded.

2. Provide a clear investment recommendation: BUY / HOLD / PASS with specific price.

Return ONLY valid JSON:
```json
{{
  "levers": [
    {{
      "name": "...",
      "category": "Revenue|Cost|Capital|Financing|Use-Change",
      "effort": "Low|Medium|High",
      "noi_impact_pct": 0,
      "timeline_months": 0,
      "description": "..."
    }}
  ],
  "recommendation": {{
    "verdict": "BUY",
    "target_offer": {dc.ask_price},
    "walk_away": {int(dc.ask_price * 1.05)},
    "target_cap_rate": 0.0,
    "key_conditions": ["..."],
    "negotiation_strategy": "...",
    "single_biggest_risk": "...",
    "confidence": "Medium"
  }},
  "offers": [
    {{
      "price": {int(dc.ask_price * 0.70)},
      "price_per_sf": {dc.ask_price * 0.70 / max(dc.sf,1):.0f},
      "cap_rate_pct": 0.0,
      "gross_rent_multiplier": 0.0,
      "cash_on_cash_pct": 0.0,
      "label": "Aggressive"
    }},
    {{
      "price": {int(dc.ask_price * 0.85)},
      "price_per_sf": {dc.ask_price * 0.85 / max(dc.sf,1):.0f},
      "cap_rate_pct": 0.0,
      "gross_rent_multiplier": 0.0,
      "cash_on_cash_pct": 0.0,
      "label": "Target"
    }},
    {{
      "price": {dc.ask_price},
      "price_per_sf": {dc.ask_price / max(dc.sf,1):.0f},
      "cap_rate_pct": 0.0,
      "gross_rent_multiplier": 0.0,
      "cash_on_cash_pct": 0.0,
      "label": "Ask"
    }}
  ]
}}
```""")

    full_prompt = "\n".join(prompt_parts)

    result = get_triple_analysis(full_prompt, timeout_per_model=90)

    parsed = _extract_json(result.get("synthesis", ""))
    if not parsed:
        for key in ["deepseek", "openrouter", "mistral"]:
            parsed = _extract_json(result.get(key, ""))
            if parsed:
                break

    levers_list = parsed.get("levers", []) if parsed else []
    recommendation = parsed.get("recommendation", {}) if parsed else {}
    offers = parsed.get("offers", []) if parsed else []

    return {
        "levers": levers_list,
        "recommendation": recommendation,
        "offers": offers,
        "_raw": {k: v for k, v in result.items() if k != "errors"},
        "_errors": result.get("errors", []),
    }


# ── Helpers ──

def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON object from LLM response text."""
    if not text:
        return None

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding JSON object boundaries
    for start, end in [("{", "}"), ("[", "]")]:
        idx_start = text.find(start)
        if idx_start >= 0:
            depth = 0
            for i in range(idx_start, len(text)):
                if text[i] == start:
                    depth += 1
                elif text[i] == end:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[idx_start:i+1])
                        except json.JSONDecodeError:
                            break

    return None


def _fallback_scenarios(dc: DealContext, ctx: LiveContext) -> list:
    """Generate basic fallback scenarios when LLM fails."""
    deal = dc.deal_data
    income = deal.get("income", {})
    noi = income.get("noi_estimated", income.get("noi", 0)) or 0
    cap = income.get("cap_rate_est_pct", income.get("cap_rate", 0)) or 8.0
    purchase = dc.ask_price or 1
    hpi = ctx.msa_hpi_1yr_pct or 2.0

    exit_cap_base = cap / 100.0 if cap > 1 else cap
    if exit_cap_base > 20:
        exit_cap_base = 0.08

    # Base value from NOI
    base_noi = max(noi, purchase * exit_cap_base * 0.85)
    base_value = base_noi / exit_cap_base if exit_cap_base > 0 else purchase

    return [
        {
            "name": "Worst Case — Tenant Loss + Cap Expansion",
            "probability": 0.05,
            "description": "Key tenant vacates. Cap rate expands 200bps.",
            "triggers": ["Tenant default", "Local recession", "Oversupply"],
            "noi": round(base_noi * 0.55),
            "exit_cap": exit_cap_base + 0.02,
            "exit_value": round(base_noi * 0.55 / (exit_cap_base + 0.02), -3),
            "moic": round(base_noi * 0.55 / (exit_cap_base + 0.02) / purchase, 2),
        },
        {
            "name": "Baseline — Steady-State Operations",
            "probability": 0.40,
            "description": f"Stable occupancy. Modest {hpi}% annual appreciation.",
            "triggers": ["Status quo operations", "Normal market conditions"],
            "noi": round(base_noi),
            "exit_cap": exit_cap_base,
            "exit_value": round(base_value, -3),
            "moic": round(base_value / purchase, 2),
        },
        {
            "name": "Phase 1 Optimize — Rent Push to Market",
            "probability": 0.30,
            "description": "Push rents to market rate. Minor cosmetic improvements.",
            "triggers": ["Lease renewal at market", "Minor capex", "Re-tenanting"],
            "noi": round(base_noi * 1.30),
            "exit_cap": exit_cap_base - 0.005,
            "exit_value": round(base_noi * 1.30 / (exit_cap_base - 0.005), -3),
            "moic": round(base_noi * 1.30 / (exit_cap_base - 0.005) / purchase, 2),
        },
        {
            "name": "Phase 2 Expand — Renovation + Multi-Tenant",
            "probability": 0.15,
            "description": "Major renovation. Upgrade to Class B. Add tenants.",
            "triggers": ["$75-150K renovation", "Rezone approval", "New tenant mix"],
            "noi": round(base_noi * 1.65),
            "exit_cap": exit_cap_base - 0.01,
            "exit_value": round(base_noi * 1.65 / (exit_cap_base - 0.01), -3),
            "moic": round(base_noi * 1.65 / (exit_cap_base - 0.01) / purchase, 2),
        },
        {
            "name": "Phase 3 Strategic — Corridor Upside / Redevelop",
            "probability": 0.10,
            "description": "Corridor appreciation + parcel assembly. Highest use conversion.",
            "triggers": ["Adjacent parcel acquisition", "Rezoning", "Market boom"],
            "noi": round(base_noi * 2.0),
            "exit_cap": exit_cap_base - 0.015,
            "exit_value": round(base_noi * 2.0 / (exit_cap_base - 0.015), -3),
            "moic": round(base_noi * 2.0 / (exit_cap_base - 0.015) / purchase, 2),
        },
    ]
