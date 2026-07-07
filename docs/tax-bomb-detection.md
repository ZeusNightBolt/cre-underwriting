# Property Tax Reassessment Detection — Mandatory Pre-Analysis Step

## Universal Pattern

When a property hasn't been reassessed in years and the seller improved it, the current tax assessment is STALE. The listing's claimed NOI uses the stale (low) tax number. On sale, tax reassessment can multiply the tax bill by 2-4×. This applies in any jurisdiction — the specific reassessment trigger varies by state.

**This reference covers NJ in detail (most aggressive reassessment state). For other states, apply the same pattern with jurisdiction-specific rates:**

| State | Reassessment Trigger | Key Rule |
|-------|---------------------|----------|
| NJ | At sale price (or municipal revaluation) | County effective rates: 1.8-4.2% |
| CA | Prop 13: 1% of purchase price + 2% annual max | Purchase price becomes new base |
| TX | Annual reassessment (no state income tax) | High rates: 2.0-2.8% |
| FL | Annual with 3% homestead cap ("Save Our Homes") | Non-homestead: uncapped |
| PA | County-level, varies widely | Some counties haven't reassessed in decades |

## NJ-Specific: The Pattern (Fully Documented)

**Session evidence (May 2026): 3 of 4 deals analyzed had this issue.**

| Deal | Current Assessment | Ask | Current Tax | Post-Sale Tax | Increase |
|------|-------------------|-----|-------------|---------------|----------|
| 4 Market St, Passaic | $208,700 | $865K | $8,604 | ~$35,638 | +314% |
| 931 Amboy Ave, Edison | $270,000 | $899K | $6,450 | ~$21,477 | +233% |
| 341 WHP, Galloway | $5,500 | $450K | n/a | ~$9,360 | +70% |

## Where to Find Tax Data on LoopNet

The "Property Facts" section of any LoopNet listing page includes:
- **Total Assessment**
- **Land Assessment**
- **Improvement Assessment**
- **Annual Taxes** (sometimes behind login wall but present in raw HTML)

Look for these in the HTML:
```html
<span class="taxes-zoning__nowrap">$208,700</span>  <!-- Total Assessment -->
<span class="taxes-zoning__nowrap">$8,604</span>     <!-- Annual Taxes -->
```

## NJ County Effective Tax Rates

| County | Effective Rate | Notes |
|--------|---------------|-------|
| Essex (Irvington, Newark) | 3.0-3.5% | Higher urban rates |
| Passaic (Passaic City) | 3.8-4.2% | Very high — PILOT critical |
| Hudson (Hoboken, Jersey City) | 1.8-2.2% | Lower rates, revalued more often |
| Middlesex (Edison) | 2.2-2.5% | Moderate |
| Atlantic (Galloway) | 2.0-2.4% | Lower |
| Bergen | 2.2-2.8% | Moderate |
| Monmouth | 1.8-2.2% | Lower |
| Mercer | 2.8-3.2% | Higher |

**Formula:** Post-sale tax = Ask Price × County Effective Rate × Equalization Ratio (~0.85-1.0)

Conservative assumption: use Ask Price directly × Effective Rate.

## Red-Flag Phrases in Listings

When you see these, the tax bomb is likely:

- "Exceptionally low taxes" → taxes are stale, will jump on sale
- "Cap rate over 8%" → probably based on pre-renovation taxes
- "Taxes only $X,XXX/year" → check assessment vs ask
- Any mention of "renovated 20XX" with old assessment → reno wasn't captured in assessment

## Hidden-NOI Pattern (May 2026 — Fords, NJ case)

**When NOI/Cap Rate is hidden behind LoopNet's login wall on a property that should have financials, treat it as a deliberate concealment signal.** Properties listed as "fully leased" or "NNN" that hide their NOI are almost certainly doing so because the real numbers make the asking price look indefensible.

**Red-flag checklist for hidden-NOI listings:**
1. Property is "fully leased" / "investment" / "NNN" but NOI is NOT visible without logging in
2. Assessment is <20% of asking price (massive tax bomb incoming)
3. Days on market >180 (stale — market already rejected the ask)
4. "Recent price reduction" visible in listing
5. "Buyer can occupy units" language → tenant turnover planned or in progress

**If 3+ of these are true, the seller is hiding something.** Demand rent roll + tax returns through the broker before any offer. Use the hidden NOI as negotiation leverage: "I can't price this if you won't show me the numbers."

**Session evidence (May 2026):** 566-568 New Brunswick Ave, Fords, NJ — 475 DOM, price reduction, NOI hidden, assessment 14.7% of ask, tax bomb +578%. All analysis was on estimated NOI. The broker's refusal to show financials on a "fully leased" NNN property is the #1 concealment risk.

## Counter-Plays

1. **PILOT (Payment In Lieu of Taxes):** Available in NJ redevelopment zones. Typically 10-15% of gross revenue instead of property tax. Requires municipal approval. Check if property is in a redevelopment zone (MSRA, B-2R, etc.). PILOT can make a 4% cap deal into a 9% cap deal.

2. **Tax appeal:** After purchase, appeal the assessment. NJ allows annual appeals by April 1. Requires appraisal showing purchase price isn't market value (unlikely to succeed at purchase price).

3. **Price negotiation:** If the seller is pricing based on claimed (pre-tax-bomb) NOI, the real cap rate after reassessment justifies a lower offer. Use this as negotiating leverage.

4. **1031 exchange / OZ:** If the property is in an Opportunity Zone, the tax benefits on capital gains can offset the property tax burden over a 10-year hold.

## Mandatory Analysis Step

On EVERY deal, before computing NOI or cap rate:

1. Extract current assessment and annual taxes from LoopNet "Property Facts"
2. Compute post-sale taxes at the county effective rate
3. Compute REAL NOI = claimed gross - post-sale taxes - other expenses
4. Compare real NOI to claimed NOI — if the difference exceeds 15%, flag it prominently
5. Investigate PILOT eligibility (zoning = redevelopment zone?)

Never present the listing's claimed cap rate without also showing the real (post-tax-reassessment) cap rate.
