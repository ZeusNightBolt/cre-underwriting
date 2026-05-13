# cre-underwriting — Local Context

> Referenced by `cre-underwriting` skill. Version-specific details, state overrides, and deal-specific notes live here, not in new skills.

## Current State (May 13, 2026)

- **Pipeline version**: v3 (8-pillar framework via `orchestrator_v3.py`)
- **Dashboard design**: Open-Design Fusion (Trading Terminal × Warm Editorial), terracotta accent
- **Last deal**: 3904-3914 Augusta Rd, Greenville, SC (40159875)
- **Deployed**: https://augusta-greenville.vercel.app

## Known Issues

1. `enhanced.py:129` — crashes on `days_on_market=None`. Workaround: always set in deal JSON.
2. `loopnet_utils.detect_tax_bomb()` — NJ/PA only. For SC/NC/GA/FL, build manual analysis.
3. `setuptools.backends` — pip install -e fails. Workaround: PYTHONPATH.
4. Frontier threshold can be None if no price crosses into attractive zone — bug in `_build_frontier_data()`.
5. License detection false positives on "ust" → "investment" — fixed with `\b` boundaries May 13.
6. Moats scored as generic 8-dimension template unless replaced with property-type-specific dimensions.

## State Tax Quick Reference

| State | Ratio | Trigger | Code |
|-------|-------|---------|------|
| NJ | 100% | Auto at sale | County millage |
| SC | 6% | Deed conveyance | §12-43-220(e), §12-37-3150 |
| PA | Varies | County-specific | Check county |

## File Map

```
~/cre-underwriting/
├── src/cre_underwriting/
│   ├── orchestrator_v3.py    # Main entry: EnhancedPipelineOrchestrator
│   ├── valuation.py          # Node 3: triangulation
│   ├── financial_levers.py   # Node 7: pro forma + levers
│   ├── convexity.py          # Node 10: convexity engine
│   ├── enhanced.py           # Node 8: moats + offers
│   ├── dashboard.py          # Node 11: generate_dashboard()
│   ├── environmental.py      # assess_location()
│   └── comps.py              # find_comps()
├── scripts/
│   ├── loopnet_listing.py    # Node 1: single listing scrape
│   ├── loopnet_utils.py      # BiDi lifecycle, tax/condo/noi
│   └── loopnet_search.py     # Search scraper
└── references/
    ├── open-design-fusion.md # Dashboard design tokens
    └── sc-tax-mechanics.md   # SC tax primary sources
```
