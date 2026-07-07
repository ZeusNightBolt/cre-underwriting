---
name: deal-underwriter
description: "Full CRE deal underwriting: 5 scenarios, 4 valuations, 8 moats, lawyer-brain concealment, convexity analysis, offer ladder. Wraps cre_underwriting.pipeline.PipelineOrchestrator."
version: 1.0.0
metadata:
  hermes:
    tags: [cre, underwriting, convexity, moat, valuation, offer]
---

# Deal Underwriter

Runs the full underwriting playbook on a structured CRE deal. Wraps `cre_underwriting.pipeline.PipelineOrchestrator`.

## Quick Start

```bash
python3 scripts/underwrite.py --input deal.json --output analysis.json

# With optional environmental + comps
python3 scripts/underwrite.py --input deal.json --output analysis.json \
  --env environmental.json --comps comps.json
```

## Input Contract

A structured deal JSON from `listing-parser`:

```json
{
  "deal_id": "34554176",
  "address": "123 Main St, Anytown, NJ",
  "ask_price": 450000,
  "purchase_price": 400000,
  "hard_floor": { "low": 275000, "mid": 300000, "high": 325000 },
  "real_estate_value": 380000,
  "scenarios": [
    { "name": "Worst Case — Vacancy spike", "moic": null, "exit_value": 320000 },
    { "name": "Baseline — Status quo", "moic": null, "exit_value": 420000 },
    { "name": "Phase 1 Optimize — Rent bumps", "moic": null, "exit_value": 500000 },
    { "name": "Phase 2 Expand — Add unit", "moic": null, "exit_value": 620000 },
    { "name": "Phase 3 Strategic — Parcel assembly", "moic": null, "exit_value": 850000 }
  ],
  "exit_year": 5,
  "capital_invested": 50000,
  "notes": {
    "concealment_risks": ["NOI behind login wall"],
    "positives": ["Below replacement cost"],
    "property_type": "retail",
    "description": "..."
  }
}
```

## Output Contract

```json
{
  "convexity": {
    "verdict": "PURSUE AT $380K",
    "convexity_ratio": 1.85,
    "pwev": 430000,
    "scenario_analysis": { "...": "..." }
  },
  "enhanced": {
    "moat_score": 14,
    "moats": { "license": 2, "tourism": 1, "...": "..." },
    "offers": [
      { "label": "Aggressive", "price": 350000, "probability": 15 },
      { "label": "Target", "price": 380000, "probability": 50 },
      { "label": "Walk Away", "price": 425000, "probability": 90 }
    ]
  },
  "environmental": { "...": "..." },
  "comps": { "...": "..." }
}
```

## Scenario Naming Rules

Scenario names MUST contain specific keywords for the engine to match them:

| Category | Required Keywords |
|----------|-------------------|
| Worst | "worst case", "scenario 1" |
| Base | "baseline", "base", "scenario 2", "as-is" |
| Best | "phase 2 expand", "phase 1 optimize", "best case", "scenario 4", "scenario 5" |
| Moonshot | "phase 3 strategic" (excluded from convexity best-case) |

## Pitfalls

1. **Scenario names must match keywords** — engine raises ValueError if it can't match worst/base/best.
2. **Use hard floor as effective worst case** — convexity formula uses `max(worst_scenario, hard_floor_mid)`.
3. **Exclude Phase 3 from convexity best-case** — moonshot scenarios inflate convexity unrealistically.
4. **NNN vs Gross lease**: Verify lease type before computing NOI. NNN: owner pays management + reserves only.
5. **Post-sale taxes**: Every scenario must use reassessed taxes (NJ reassesses at sale).
6. **Deep-copy scenarios**: Engine deep-copies scenarios to prevent mutation. Caller's original objects are untouched.
7. **Offer multipliers**: Both convexity and enhanced engines import from `constants.py`. Changing constants changes both.


---
## Project Specialization: cre-underwriting
*Specialized: 2026-05-13 12:53*
*Master: finance/deal-underwriter*

> ⚠ This is a specialized copy. Changes to the master skill do NOT propagate here.
> To update: re-run `skill_specialize.py copy` with `--force`.
