# Owner-User Vacant Condo Underwriting Template

**Worked example: 6 Boonton Ave, Butler, NJ 07405 (LoopNet 40453341)**

## Quick Reference

| Field | Value | Source |
|-------|-------|--------|
| Ask | $289,000 ($193/SF) | Listing |
| SF | 1,500 | Listing |
| Structure | Fee Simple Condo | Description: "Retail storefront condo for sale" |
| Delivery | Vacant | "Delivered vacant for buyer occupancy" |
| Zoning | CBD - Commercial CBD | Listing facts |
| Year Built | 1905 | Listing facts |
| Class | C | Listing facts |
| County | Morris, NJ | Address lookup |
| Walk Score | 60/100 | Listing |

## Step 1: Classify Structure

**NOT leasehold.** Keywords confirming fee simple:
- "Retail storefront condo for sale" (not "lease assignment" or "business only")
- "Current ownership will vacate" (owner is selling unit, not assigning lease)
- "Condo Use: Retail" with no lease language
- No "ground lease", "option term", or "expires" anywhere in description

## Step 2: Hard Floor

**Method:** Distressed market value of condo unit = SF × distressed PSF for submarket.

Morris County Class C retail condo comps:
- Butler Main St: vacant shells $130-$160/SF
- Buildout premium: existing bakery kitchen/HVAC/restroom adds $30-50K over shell

| Floor | PSF | Value | Pct of Ask |
|-------|-----|-------|-------------|
| Low (fire sale) | $88 | $132,000 | 46% |
| Mid (bank REO) | $112 | $168,000 | 58% |
| High (motivated) | $136 | $204,000 | 71% |

Stabilized RE value: $160/SF × 1,500 = $240,000 (83% of ask)

## Step 3: Business Modeling

**Implicit RE NOI** (if rented out, NNN):
- Market rent: $14/SF NNN × 1,500 = $21,000/yr
- Owner RE costs (management + reserves): $2,000/yr
- Implied RE NOI: $19,000/yr

**Business concepts modeled:**

| # | Concept | Capex | Revenue | EBITDA | Margin |
|---|---------|-------|---------|--------|--------|
| 1 | Specialty Coffee + Bakery | $15K | $140K | $32K | 23% |
| 2 | Quick-Service Café + Lunch | $20K | $180K | $36K | 20% |
| 3 | Boutique Retail + Gift Shop | $10K | $90K | $22.5K | 25% |
| 4 | Bakery Wholesale + Retail | $25K | $200K | $50K | 25% |
| 5 | Service Office (Insurance/RE) | $8K | N/A | N/A | N/A |

## Step 4: Scenarios

Use going-concern exit values: **exit = RE_value + (business_EBITDA × multiple)**

Food service multiples: 2-3x for small operations, 2.5-3.5x for proven multi-revenue.

| Scenario | Prob | RE Value | Biz EBITDA | Multiple | Exit | MOIC |
|----------|------|----------|------------|----------|------|------|
| Worst Case — Distressed Resale | 10% | $168K | $0 | — | $168K | 0.58x |
| Baseline — Stable Coffee Shop | 40% | $240K | $0 | — | $240K | 0.83x |
| Phase 1 Optimize — Profitable Bakery/Café | 30% | $260K | $30K | 2.0x | $320K | 1.11x |
| Phase 2 Expand — Café + Retail + Events | 15% | $300K | $45K | 2.7x | $420K | 1.45x |
| Phase 3 Strategic — Butler Downtown Revival | 5% | $340K | $60K | 3.3x | $540K | 1.87x |

**Convexity:** 2.5 (strong asymmetry — $2.50 upside per $1 downside)
**PWEV:** $298,800 (3.4% above ask)
**Effective worst:** $168,000 (hard floor mid)

## Step 5: Moats (10/24 — Moderate)

| Moat | Score | Rationale |
|------|-------|-----------|
| License Barrier | 1/3 | No liquor license, food permits are routine |
| Tourism Corridor | 1/3 | Residential borough, limited drive-by traffic |
| Multi-Revenue | 2/3 | Potential for 3-4 streams (retail, wholesale, catering, events) |
| Zoning Optionality | 2/3 | CBD permits retail, food, office, service — flexible |
| Rent Gap | 0/3 | Owner-user model, no rent arbitrage |
| Brand Value | 0/3 | No existing brand, built from scratch |
| Asset Stack | 2/3 | Fee simple condo + bakery buildout, floor at 58% |
| Seller Asymmetry | 2/3 | Vacating owner, recent listing (5 days), owner-user pool smaller |

## Step 6: Offer Ladder

| Label | Price | % of Ask | Rationale |
|-------|-------|----------|-----------|
| AGGRESSIVE | $184,800 | 64% | 10% above distressed, exploit motivated seller |
| **TARGET** | **$210,000** | **73%** | **Fair: quick exit for seller + built-in equity** |
| MIDPOINT | $228,500 | 79% | Split difference, most likely negotiated outcome |
| WALK | $245,650 | 85% | Max acceptable, above this CoC returns fall below threshold |
| ASK | $289,000 | 100% | Only if high-confidence business plan generating $40K+ EBITDA |

## Step 7: Key Risks

1. **Tax Bomb (+93%)** — Post-sale tax ~$7,658/yr vs current ~$3,975. Absorbed as business expense in owner-operator model.
2. **1905 Building** — Deferred maintenance risk. Inspection + condo doc review mandatory.
3. **Condo Association** — Unknown reserves, possible special assessments. Review docs before offer.
4. **Single Parking Space** — Constraint for customer-facing business. Validate street parking.
5. **Owner-User Business Risk** — Startup failure risk. Mitigated by hard floor at 58% of ask.

## Step 8: Verdict

**CONDITIONAL — PURSUE AT $210,000**

Target: 73% of ask, 88% of stabilized RE value. Walk at $245,650.

Key conditions: condo docs review, building inspection, parking validation, business plan commitment, 21-day contingency period.

## Anti-Patterns to Avoid

- **Do NOT use cap-rate exit values** for owner-operator scenarios. NOI/cap-rate formulas produce absurd numbers for small condos.
- **Do NOT flag "no NOI" as concealment** for vacant owner-user listings. It's expected.
- **Do NOT use the standard income-property playbook.** This is a different deal type.
- **Do NOT skip business idea analysis** — it's the core of the owner-operator value proposition.
