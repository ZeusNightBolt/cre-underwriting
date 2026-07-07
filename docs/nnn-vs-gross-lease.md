# NNN vs Gross Lease NOI Modeling

**Trapped by:** Session May 10, 2026 — Fords NJ listing 34554176

## The Bug Pattern

NNN (triple-net) leases are the standard for retail properties on LoopNet. The lease type can usually be inferred from:
- Property subtype "Storefront" + no mention of gross/full-service → likely NNN
- Listing mentions "NNN" or "CAM" or "tenant pays taxes/insurance" 
- LoopNet property facts often list lease type

When NOI must be estimated (financials behind login wall), the default assumption for retail should be NNN unless explicitly stated otherwise.

## Correct Expense Structure

| Lease Type | Owner Pays | Tenant Pays |
|-----------|-----------|-------------|
| NNN | Management (3-5% EGI), Structural reserves ($0.25/SF) | Taxes, Insurance, CAM, Utilities |
| Gross/Full-Service | Management, Reserves, Taxes, Insurance, CAM, Utilities | Nothing (all included in rent) |

## NNN NOI Formula

```
EGI = Gross Rent × (1 - Vacancy%)
NOI = EGI - (Management% × EGI) - (Reserves $/SF × Building SF)
```

Do NOT include: taxes, insurance, CAM, or utilities in owner expenses for NNN.

## Impact of Getting This Wrong

Including insurance (~$2,500/yr on a 4,000 SF building) in NNN NOI:
- Deflates NOI by ~4-5%
- Deflates cap rate estimate by ~30 bps
- Can make a borderline deal look like a pass

## Verification

When the listing doesn't disclose lease type:
1. Assume NNN for retail unless contradicted
2. Flag "Lease type — assumed NNN, not verified" in missing data
3. If the property is below-market rent, it could be gross lease (owner is subsidizing via low rent) — investigate further
