---
name: comp-finder
description: "Find CRE comparable properties from multiple sources. Zillow, LoopNet, NJ ACTB. Returns comps with source status and data quality warnings."
version: 1.0.0
metadata:
  hermes:
    tags: [cre, comps, comparable, valuation, real-estate]
---

# Comp Finder

Finds comparable CRE properties from multiple sources. Wraps `cre_underwriting.comps.find_comps()`.

## Quick Start

```bash
python3 scripts/find_comps.py --input property.json --output comps.json
```

## Input Contract

```json
{
  "address": "123 Main St, Anytown, NJ 07001",
  "property_type": "retail",
  "sf": 2500,
  "price": 450000
}
```

## Output Contract

```json
{
  "summary": { "count": 3 },
  "source_status": {
    "zillow": { "count": 2, "status": "ok" },
    "loopnet": { "count": 1, "status": "ok" },
    "nj_actb": { "count": 0, "status": "stub" }
  },
  "comps": [
    { "address": "...", "price": 420000, "sf": 2400, "price_per_sf": 175, "source": "zillow" }
  ],
  "data_quality_warning": null
}
```

## Pitfalls

1. **Zillow blocks frequently (403)**. Check `source_status` — if all sources return 0, the issue is blocking, not "no comps."
2. **LoopNet and NJ ACTB are stubs** — expect `"status": "stub"`. Zillow is the primary source.
3. **Return source_status always** — distinguish "no comps found" from "source blocked."


---
## Project Specialization: cre-underwriting
*Specialized: 2026-05-13 12:53*
*Master: finance/comp-finder*

> ⚠ This is a specialized copy. Changes to the master skill do NOT propagate here.
> To update: re-run `skill_specialize.py copy` with `--force`.
