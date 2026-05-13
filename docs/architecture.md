# CRE Underwriting — Architecture

## Pipeline Data Flow

```
LoopNet Listing (Firefox BiDi)
    │
    ▼
deal_analysis.json  ──→  PipelineOrchestrator.run()
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              Convexity   Enhanced   Environmental
              Engine      Analyzer   Assessment
                    │         │         │
                    └─────────┼─────────┘
                              ▼
                      pipeline_result dict
                              │
                              ▼
                     generate_dashboard()
                              │
                              ▼
                      dashboard.html
                              │
                              ▼
                      Vercel / GH Pages
```

## Module Dependency Graph

```
models.py          ← Zero deps — all dataclasses
constants.py       ← Zero deps — all thresholds
utils.py           ← Zero deps — address parsing
    │
    ├──→ convexity.py     (imports models, constants)
    ├──→ enhanced.py      (imports models, constants)
    ├──→ environmental.py (imports models, constants, utils)
    ├──→ comps.py         (imports models, utils, scraping)
    ├──→ scraping.py      (imports models)
    └──→ pipeline.py      (imports convexity, enhanced, environmental)
         │
         └──→ dashboard.py (imports from pipeline output dict)
```

## Key Design Decisions

### Effective Worst = max(operating_worst, hard_floor_mid)
If the operating worst case falls below the hard asset floor, the owner would liquidate before letting operations deteriorate that far. Using the bare operating worst produces artificially low convexity. (Bug discovered on Fords 34554176: 0.63 → PASS with bare worst, 1.21 → CONDITIONAL with effective worst.)

### Phase 3 Excluded from Standard Best Case
Phase 3 Strategic (parcel assembly, rezoning, PILOT) produces exit values 2-3× Phase 2, inflating convexity if incorrectly used as the standard best case. The standard best case is Phase 2 Expand — the highest-probability achievable upside.

### Offer Formulas Use Unified OFFERS Constants
Both `ConvexityEngine.generate_verdict()` and `OfferAnalyzer.ladder()` use the same `OFFERS` constants from `constants.py`. No magic numbers.

### Single FireFox Instance (OOM Prevention)
The `BidiSession` context manager enforces a lock-file-based single-instance guard. On the CHUWI LarkBox X (5.7GB RAM), two Firefox instances + LLM = OOM → system freeze.

### Scraping Cascade: T0 → T1 → T2
- **T0**: curl_cffi with TLS impersonation (fastest, beats TLS fingerprint checks)
- **T1**: Camoufox headless with macOS fingerprint (beats JS checks)
- **T2**: Firefox BiDi with real browser (beats Akamai, everything else)
- Domain-tier cache (sqlite, 7-day TTL) avoids re-probing

## Scenario Architecture

```
Worst Case (20%)  →  Baseline (50%)  →  Phase 1 Optimize  →  Phase 2 Expand  →  Phase 3 Strategic
Lowest value         Day-1 cash yield   Low-capex ops        New revenue         Moonshot
                                         (< $25K)            ($25-150K)          ($250K+)
```

PWEV uses 20/50/30 weights by default. Convexity best case = Phase 2 Expand (highest-probability upside). Phase 3 is analyzed separately as moonshot.

## Testing Strategy

| Test File | What It Covers |
|-----------|---------------|
| `test_convexity.py` | Convexity engine, effective worst, PWEV, verdicts, edge cases |
| `test_enhanced.py` | 8-moat scoring, offer ladder, EnhancedAnalyzer orchestration |
| `test_environmental_comps.py` | Address parsing, NJ county profiles, comps source tracking |
| `test_pipeline.py` | Full pipeline, dashboard generation, anti-slop compliance |

**43 tests, 1.75s runtime.** All test against known fixtures (Fords 34554176, Succasunna 35674774).
