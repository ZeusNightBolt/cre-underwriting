# Convexity Engine — Module Reference

**Module:** `~/.hermes/scripts/cre_convexity.py`
**Built:** May 2026
**Validated against:** Fords 34554176 (convexity ratio 1.21 match, verdict CONDITIONAL match)

## Quick Usage

```python
from cre_convexity import ConvexityEngine, DealInput, Scenario, from_json

# Option 1: From analysis JSON (dict-based scenario format)
import json
with open("listing_34554176_analysis.json") as f:
    data = json.load(f)
result = from_json(data)
print(result.verdict.verdict)        # "CONDITIONAL"
print(result.divergence.convexity_ratio)  # 1.21

# Option 2: Programmatic
deal = DealInput(
    ask_price=799_000,
    purchase_price=799_000,
    hard_floor_low=400_000,
    hard_floor_mid=530_000,
    hard_floor_high=650_000,
    scenarios=[
        Scenario("Worst Case", probability=0.2, exit_value=292_632),
        Scenario("Baseline", probability=0.55, exit_value=796_778),
        Scenario("Phase 2 Expand", probability=0.25, exit_value=1_119_246),
    ]
)
engine = ConvexityEngine()
result = engine.analyze(deal)
```

## Dataclasses

| Class | Fields |
|-------|--------|
| `Scenario` | name, probability, revenue, cogs, labor, other_opex, noi (auto), exit_value, moic (auto) |
| `DealInput` | ask_price, purchase_price, hard_floor_low/mid/high, scenarios, exit_year, capital_invested |
| `DivergenceOutput` | absolute_spread, convexity_ratio, convexity_verdict, effective_worst, worst/ best_case_pct_capital, best_case_moic, risk_reward_ratio |
| `PWEVOutput` | pwev, pwev_vs_ask_pct, is_underpriced, worst/base/best contributions |
| `FrontierPoint` | x (worst% capital), y (best MOIC), zone (str) |
| `VerdictOutput` | verdict, target_offer, walk_away, reasoning, risk_reward_summary |
| `ConvexityResult` | Complete analysis bundle with `.to_dict()` serializer |

## Key Design Decisions

### 1. Effective Worst = max(operating_worst, hard_floor_mid)
If the operating worst-case falls below the hard asset floor, the owner would liquidate (sell the building) before letting operations deteriorate that far. Using bare operating worst produces artificially low convexity.

**Pitfall from Fords 34554176:** Operating worst = $292,632, hard floor mid = $530,000. Using bare worst → convexity 0.63 → PASS. Using effective worst → **1.21 → CONDITIONAL** (correct).

### 2. Phase 3 Strategic Excluded from Standard Best Case
Phase 3 Strategic represents moonshot optionality (parcel assembly, rezoning, PILOT eligibility). Its exit values are typically 2-3× Phase 2 Expand, inflating convexity to 3-4×. Standard analysis uses Phase 2 Expand as the "best case" — the highest-probability achievable upside.

Phase 3 remains available for explicit selection but is NOT in the default `best_names` match list. If you want moonshot convexity, name your scenario "Phase 3 Strategic" and call `ScoringEngine(include_moonshot=True)` (future enhancement).

### 3. PWEV Sums All Scenarios (Not Just Worst/Base/Best)
`compute_pwev()` iterates all scenarios with probability > 0, not just the three matched categories. This keeps PWEV rooted in realistic expectations (Phase 1 Optimize at 25% weight) while convexity uses maximum upside (Phase 2 Expand) for the tail.

### 4. Walk-Away Frontier Zone Allows CONDITIONAL
The strict playbook rule puts "worst > 25% capital AND best MOIC < 2.5×" → Walk away. But marginal convexity (ratio ≥ 1.0) with seller asymmetry signals justifies CONDITIONAL with heavy price discipline.

## Verdict Logic (Hierarchical Gates)

| Gate | Condition | Outcome |
|------|-----------|---------|
| 1 | Convexity ratio < 1.0 | PASS (negative convexity) |
| 2 | Frontier zone "Walk away" + ratio ≥ 1.0 | CONDITIONAL (asymmetric at right price) |
| 2b | Frontier zone "Walk away" + ratio < 1.0 | PASS (unreachable — caught by gate 1) |
| 3 | Frontier zone "Pursue aggressively" | PURSUE AT $X |
| 4 | MARGINAL convexity or "Acceptable selectively" | CONDITIONAL |
| 5 | HIGH or POSITIVE convexity | PURSUE AT $X |

## Scenario Name Matching

The engine matches scenarios by case-insensitive substring:

| Category | Matches |
|----------|---------|
| **worst** | "worst case", "worst", "scenario 1" |
| **base** | "baseline", "base", "scenario 2", "as-is" |
| **best** | "phase 2 expand", "phase 1 optimize", "best case", "scenario 4" |

**NOT in best:** "phase 3 strategic" (moonshot — separate category)

## Integration Points

- `pipeline_entry(deal_json_path)` — Parse an analysis JSON and return pipeline-ready flat dict
- `from_json(data_dict)` — Load from analysis JSON dict (handles both dict and list scenario formats)
- `analyze_deal(ask_price, ...)` — Convenience function, one-call analysis

## CLI

```bash
python cre_convexity.py listing_34554176_analysis.json
python cre_convexity.py --test  # Uses Fords fixture
```
