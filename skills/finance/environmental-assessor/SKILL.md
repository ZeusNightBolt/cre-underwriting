---
name: environmental-assessor
description: "Assess CRE location risks: flood zone, UST, Phase I recommendation, economic/demographic profile. Wraps cre_underwriting.environmental.assess_location()."
version: 1.0.0
metadata:
  hermes:
    tags: [cre, environmental, flood, ust, phase1, demographics]
---

# Environmental Assessor

Assesses property location risks. Wraps `cre_underwriting.environmental.assess_location()`.

## Quick Start

```bash
python3 scripts/assess.py --input property.json --output environmental.json
```

## Input Contract

```json
{
  "address": "123 Main St",
  "city": "Anytown",
  "state": "NJ",
  "lot_size_sf": 10000,
  "year_built": 1965
}
```

## Output Contract

```json
{
  "flood_zone": { "zone": "X", "risk": "minimal" },
  "ust_risk": "low",
  "phase1_recommendation": "Not required",
  "economic_profile": { "median_income": 85000, "population": 15000 },
  "county": "Morris"
}
```

## Coverage

Currently covers 10 NJ counties with hardcoded profiles. City→county lookup via manual table. For other states, uses Census Geocoder fallback.

## Pitfalls

1. **City→county lookup table needs periodic population**. Unincorporated communities (like Succasunna) may not be in the table.
2. **Census Geocoder fallback**: Falls back to `geocoding.geo.census.gov` when city not found in lookup table.
3. **UST database**: NJ-specific. PA and other states need different sources.


---
## Project Specialization: cre-underwriting
*Specialized: 2026-05-13 12:53*
*Master: finance/environmental-assessor*

> ⚠ This is a specialized copy. Changes to the master skill do NOT propagate here.
> To update: re-run `skill_specialize.py copy` with `--force`.
