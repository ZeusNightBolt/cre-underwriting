# CRE Underwriting & Convexity Analysis — Complete Methodology

Version: 1.0 — May 2026
Source: KT — Institutional fixed-income PM background, central NJ-based, hunting convex asymmetric real estate bets.

---

## 1. CORE PHILOSOPHY

Hunt positive convexity. Every deal must have the shape: "heads you win big, tails you lose small." The hard-asset floor creates a kill switch on losses. Operational and optional value-add creates a fat right tail. If a deal does not have this shape, pass.

Build a portfolio of 5 deeply understood concentrated bets, not 30 shallow ones.

Risk tolerance per deal: can absorb a 25% capital loss on a single deal once per year without portfolio-level damage. If worst case exceeds 25% of capital, upside must be proportionally larger. If worst case is unbounded (zoning disputes with no resolution path, environmental spirals, partner control issues), pass regardless of upside.

---

## 2. THE FOUR QUESTIONS

Answer these in order on every deal. Do not skip any.

**Q1 — What is the hard-asset floor?**
Sum of: real estate appraised/assessed value + transferable license market value + equipment at depreciated book or auction value. This is the liquidation value — what you recover without ever running the business. It sets maximum downside.

**Q2 — What is the going-concern value across five scenarios?**
Worst, Baseline, Phase 1 Optimize, Phase 2 Expand, Phase 3 Strategic. Compute the spread between worst and best in dollars and as a multiple of capital.

**Q3 — What is the seller actually hiding?**
Apply lawyer brain. Identify top 3 concealment risks. Distinguish stated reason for selling from the most likely actual reason. Provide specific evidence for any gap.

**Q4 — Where does the deal plot on the effective frontier?**
X-axis = worst case as % of capital. Y-axis = best case 5-year MOIC. Compute convexity ratio. Is it high enough to pursue?

---

## 3. ASSET DECOMPOSITION & FORMULAS

### Core Identity
```
Purchase Price = Real Estate Value + Transferable License Value + Equipment/FF&E Value + Implied Goodwill
```

The first three components = hard asset floor (liquidation recovery without running the business).
The fourth = what you pay for going-concern earnings.

For pure real estate deals, collapse to two layers:
```
Purchase Price = Real Estate Value + Implied Premium
```
Premium justified only by: location scarcity, zoning optionality, or rent-to-market gap.

### Metrics & Thresholds

**Cap Rate = NOI / All-in Cost** (purchase + closing + immediate stabilization capex)

- Tier 1 NJ stabilized minimum: 5.5% (value-add: 7.0% year-2 stabilized)
- Tier 2 PA/DE stabilized minimum: 7.0% (value-add: 9.0% year-2 stabilized)
- Tier 3 direct stabilized minimum: 6.5% with operational mitigant
- Below tier minimum = appreciation bet. Do not make appreciation bets without an explicit growth thesis tied to fundamentals.

**Cash-on-Cash Return = Annual Pre-Tax Cash Flow / Cash Invested**
- At 25-30% down conventional: target 10%+
- All-cash deals: target 15%+ (forgoing leverage multiplier)

**Gross Rent Multiplier = Purchase Price / Annual Gross Rent**
- Under 8: buy signal
- Under 6: steal
- Over 10: investigate before walking

**The 1% Rule = Monthly Rent / Purchase Price**
- Target: 1% or higher

**SDE (Seller's Discretionary Earnings) = Net Income + Owner Salary + Interest + D&A + One-time/Personal Expenses**
- PA family restaurants: 2.0–3.0x SDE multiple (median ~2.38x)
- PA liquor stores: 2.5–3.5x SDE
- NJ liquor stores with strong lottery income: 3.0–4.0x SDE
- Always quote the range, not a point estimate.

**Break-Even Rent = PITI / (1 − Expense Ratio)**
- Residential multifamily expense ratio: 30%
- Mixed-use with commercial: 40–45%

**MOIC = (Cumulative Cash + Exit Proceeds) / Purchase Price**
**IRR = Annualized version of MOIC**
**Payback Period = Year cumulative cash flow crosses purchase price**

**DSCR = NOI / Annual Debt Service**
- Lender minimum: 1.25x
- Comfort threshold: 1.5x+

**Risk/Reward Ratio = Best Case MOIC / Worst Case % of Capital**
- Above 12: highly convex — pursue
- 6–12: deal-by-deal judgment
- Below 6: not convex enough — likely pass

---

## 4. SCENARIO ARCHITECTURE

Run every deal through five scenarios. Never skip any.

### Scenario 1 — Worst Case
- Revenue falls 15–30% from seller's stated baseline
- One apartment vacant 3 months/year
- COGS inflates 3–5% without corresponding price increase
- No operational upgrades happen
- Labor stays at current levels
- Question: What is my floor? If hard asset floor catches the loss = bounded. If worst case = total capital loss = walk.

### Scenario 2 — Baseline
- Business runs as-is under new ownership
- No revenue growth assumed
- Payroll falls modestly if owner/family operates (family labor at 15% of revenue vs hired-labor 25–30%)
- Tells you the day-one cash yield without doing anything

### Scenario 3 — Phase 1 Optimize (Year 1–2)
Low-capital, high-leverage operational moves. Under $25K capex. Can lift SDE 30–60%.
- Raise rents on under-market apartments to market
- Add skill games (3–5 machines at $2,500–$4,000/month gross per machine)
- Launch online ordering
- Fix menu margin leaks
- Run loyalty program
- Optimize hours

### Scenario 4 — Phase 2 Expand (Year 2–3)
Add meaningful new revenue stream:
- Smoke/vape counter: $150K–$250K annual revenue at 40–50% margins
- Convenience-store micro-corner: $75K–$125K annual revenue
- Upgrade beer-and-wine (E) license to full restaurant liquor (R): adds $50K+ in license asset value
- Convert underused space to STR or office

### Scenario 5 — Phase 3 Strategic (Year 3+)
Optionality moves:
- Corner lot resubdivision
- Adjacent parcel acquisition
- Sale-leaseback to lock below-market basis
- Refinance pulling out large chunk of original equity after value-add

### Per-Scenario Outputs (compute all)
Annual revenue, COGS, labor, other operating expenses, NOI, SDE, cap rate at purchase price, cash-on-cash, projected year-end enterprise value

### Probability Weights (default, adjustable)
- Worst: 20%, Base: 50%, Best (Phase 1+2 blend): 30%
- Adjust: strong operational levers + tired seller → shift to 15/45/40
- Concealment red flags or thin margin → shift to 30/50/20

---

## 5. VALUATION TRIANGULATION

Three methods always. Do not rely on one.

### Method 1 — Asset-Based Valuation (the floor)
```
Hard Asset Floor = RE Appraised Value + Transferable License Market Value + Equipment at Auction/Depreciated Book
```

### Method 2 — Income-Based Valuation
```
Enterprise Value = (Baseline SDE × Market SDE Multiple) + Hard RE Value + Hard License Value
```
Do NOT apply SDE multiple to the real estate component — that is the double-count that makes deals look better than they are.

### Method 3 — Revenue Multiple (sanity check)
```
Revenue-Based Value = Annual Revenue × Market Revenue Multiple
```
- PA pizzerias: 0.3–0.5x revenue
- Liquor stores: 0.6–0.8x revenue
- C-stores: 0.15–0.25x revenue
- Bars: 0.5–0.75x revenue

### Method 4 — Probability-Weighted Expected Value
```
PWEV = (P_worst × Worst_Outcome) + (P_base × Base_Outcome) + (P_best × Best_Outcome)
```

### Convergence Test
All four methods should triangulate to a range. If they diverge by more than 30%, something is wrong — usually the baseline earnings are either depressed or inflated. Investigate which.

### Synthesis Template (use on every deal)
> "Comps suggest a value of roughly $X to $Y based on [N] recent sales at $Z per [unit]. Location fundamentals — [2–3 most relevant indicators with direction and magnitude] — suggest a [positive/neutral/negative] trajectory over the next 3–5 years. The income-based valuation produces $A based on [SDE/NOI] of $B times [multiple] plus hard RE and license value of $C. The probability-weighted expected outcome at $X ask is $Y, with worst case at $W and best case at $E. The four estimates [converge at ~$X / diverge between $X and $Y, with divergence driven by (specific factor)]. I am weighting [comps/fundamentals/income/divergence] more heavily here because [one-sentence reason grounded in the deal and tier]. My target offer is $P, my walk-away is $W, and my settlement target is $S."

---

## 6. MOAT SCORING FRAMEWORK

Score each deal on 8 moats (0–3 scale: absent / weak / present / strong). Total out of 24.

### Gate Thresholds
- 18–24: Move aggressively. Ideal shape.
- 12–17: Strong deal, negotiate hard, verify contingent moats.
- 7–11: Marginal. Point-estimate numbers must be exceptional.
- 0–6: Pass. Downside not bounded, upside capped.
- Any deal with total moat score below 4 is a pass regardless of point-estimate returns.

### Moat 1 — Scarce Transferable License (0–3)
PA liquor licenses (R/E/H) are quota-restricted by county. Unused R-license in Monroe County: $75K–$150K. NJ plenary licenses capped at ~1 per 3,000 residents. Bergen/Monmouth municipalities: $500K–$1.5M.

### Moat 2 — Tourism Corridor Position (0–3)
Property on a road feeding a durable tourism attraction = free marketing forever. NPS, state parks, ski resorts, lakes, historic districts.

### Moat 3 — Multi-Revenue-Stream Parcel (0–3)
Single address spanning multiple independent revenue streams = natural hedge. Score high: ≥3 streams. Score medium: 2 streams. Score low: monoline.

### Moat 4 — Zoning Optionality (0–3)
Zoning permitting multiple uses above current operation = embedded call option. Must be verified by direct contact with zoning officer.

### Moat 5 — Rent-to-Market Gap (0–3)
Under-market rents from a tired/nice landlord = automatic value-add. Gap ≥20% = score high. Gap 10–20% = score medium. At or above market = zero.

### Moat 6 — Brand Longevity & Local Goodwill (0–3)
25+ year continuous operations with 4.0+ Google Maps rating and 100+ reviews: Score 3. 10–25 years: Score 2. Newer businesses or deteriorating reviews: Score 0.

### Moat 7 — Asset Stack Coverage (0–3)
Hard assets as % of purchase price: 80%+ = 3, 60–80% = 2, 40–60% = 1, Below 40% = 0.

### Moat 8 — Seller Asymmetry (0–3)
Transaction moat. Score high: health issues, retirement with no successor, listing >180 days with price cuts, estate sale, divorce-driven. Score zero: fresh listing, motivated ambitious seller.

---

## 7. DUE DILIGENCE EXECUTION ORDER

Work through this sequence on every deal in order. Do not skip ahead.

1. **Step 1 — Confirm the Actual Property**: Pull parcel ID, owner name, deed book and page, land and improvement assessed values, most recent sale price and date, legal description.
2. **Step 2 — Tax Assessment & Reassessment Risk**: Model post-sale tax bill, not current tax bill.
3. **Step 3 — Zoning Verification**: Verify via municipal zoning ordinance. Never assume.
4. **Step 4 — FEMA Flood Zone**: Pull FEMA flood map at msc.fema.gov.
5. **Step 5 — Comparable Sales**: 3–5 recent sold comps from Zillow, Redfin, LoopNet.
6. **Step 6 — Neighborhood Intelligence**: Local power structure, chamber of commerce, competing businesses.
7. **Step 7 — Seller Circumstances**: Why is the seller selling?
8. **Step 8 — Operational Fundamentals**: Tax returns, bank statements, POS reports.
9. **Step 9 — Traffic, Employment, & Demographics**: AADT from state DOT, Census ACS, top 3 employers.
10. **Step 10 — Binary-Question Inventory**: Every question whose answer could kill the deal.

---

## 8. LAWYER BRAIN — CONCEALMENT ANALYSIS

### Default Assumption
The seller has spent more time with this property than you will in due diligence by an order of magnitude. The broker has every economic incentive to ensure you do not know what the seller knows. Assume anything not affirmatively disclosed and verified is undisclosed for a reason.

### Why Are They Really Selling?
|Stated Reason |Typical Reality |Verification |
|--------------|----------------|-------------|
|Retirement |Usually genuine for 65+ with no successor |Deed history, business registration date |
|Health issues |Usually genuine — more specific = more believable |Vague "family health concerns" = probe |
|Pursuing other opportunities |Soft yellow flag — often means something is going wrong |Dig deeper |
|Estate sale |Operator died, business likely lost momentum |Check timeline of estate vs operations |
|Spending more time with family (working age) |Almost always insufficient — dig |Cross-reference with financials |

### Categories of Concealment
Environmental (USTs, ACM, LBP, Phase I ESA), Title & Legal (easements, liens, mortgages), Building & Code (open permits, unpermitted work, ADA non-compliance), Lease & Tenant (side agreements, missing security deposits, related-party tenancies), Tax & Assessment (model post-sale, not current), Operational Financial (above-market related-party rents, one-time revenue events), License & Regulatory (pending violations), Equipment (leased not owned), Employment (misclassification), Litigation, Insurance & Claims.

---

## 9. DIVERGENCE & EFFECTIVE FRONTIER

### Three Divergence Metrics
- **Absolute Spread** = Best Case $ − Worst Case $
- **Capital-Normalized Spread** = (Best − Worst) / Capital Invested
- **Convexity Ratio** = (Best − Base) / (Base − Worst)

Above 2.5: highly convex. Above 1.5: positive convexity. Below 1.0: negative convexity — pass. Above 4.0: rare, investigate.

### PWEV
```
PWEV = (P_worst × Worst_$) + (P_base × Base_$) + (P_best × Best_$)
```
If PWEV at ask < ask price → over-priced. If PWEV well above ask → under-priced.

### Effective Frontier Chart
- X-axis: Worst case as % of capital (0–100%)
- Y-axis: Best case 5-year MOIC (1.0x–5.0x+)
- Vertical line at 25% (max acceptable worst case)
- Horizontal line at 2.5x (minimum acceptable best case MOIC)

|Zone |Worst Case |Best Case |Action |
|-----|-----------|----------|-------|
|Upper Left |Low (<25%) |High (>2.5x) |**Pursue aggressively** |
|Upper Right |High (>25%) |High (>2.5x) |Acceptable selectively |
|Lower Left |Low (<25%) |Low (<2.5x) |Pass unless portfolio reason |
|Lower Right |High (>25%) |Low (<2.5x) |**Walk away** |

---

## 10. COMPARABLE SALES METHODOLOGY

### Sources (in order of reliability)
1. County assessor deed transfer record
2. Zillow sold filter
3. Redfin sold listings
4. LoopNet sold transactions
5. BizBuySell closed listings

### Three Comp-Based Value Angles
- Angle 1 — Price per Square Foot
- Angle 2 — SDE Multiple (going-concern deals)
- Angle 3 — Revenue Multiple (sanity check)

### Red-Flag Comps (weight lower)
- Recent sale at same/adjacent address at dramatically lower price
- Comps all sold by same broker at top of range
- Identical round-number pricing (three sales at exactly $200K)
- Unusually short DOM in otherwise slow market

---

## 11. LOCATION FUNDAMENTALS

Pull on every deal: wage/income trajectory (BLS QCEW), population growth (Census), home price appreciation (Zillow ZHVI, FHFA HPI), employment base (top 5 employers), rental demand (Census ACS % renter), school district (GreatSchools), tourism visitation (NPS IRMA), traffic counts (PennDOT/NJDOT), planned infrastructure.

---

## 12. 5-AGENT DEBATE FRAMEWORK

### Non-Overlap Doctrine
Each agent has a primary domain and may not opine outside it:
1. **The Trader** — Transaction microstructure & exit liquidity. Does NOT opine on property fundamentals.
2. **The Portfolio Manager** — Position sizing & opportunity cost. Does NOT opine on micro-level cash flow.
3. **The Fundamental Analyst** — Bottoms-up cash flow. Does NOT opine on market timing.
4. **The Quantitative Lens** — Distributions & sensitivities. Does NOT opine on operational strategy.
5. **The Pessimist** — Hidden risks & tail scenarios. Does NOT soften, hedge, or echo.

---

## 13. GEOGRAPHIC TIERS & RETURN TARGETS

### Tier 1 — Core Operator Geography (Direct Ownership Default)
NJ: Middlesex, Union, Somerset, Morris, Essex, Hudson, Bergen, Passaic, Mercer.
Cap rates: Stabilized multifamily 5.0–6.5%, Mixed-use 6.0–7.5%, Retail strip 6.5–8.0%.

### Tier 2 — Acceptable Geography (Deal Must Be Exceptional)
Eastern PA (Bucks, Montgomery, Northampton, Lehigh), Delaware (New Castle), Southern NJ.
Cap rates: 50–150 bps higher than Tier 1. Minimum stabilized: 7.0% | Value-add: 9.0%.

### Tier 3 — Growth Markets (LP Default)
Charlotte, Raleigh-Durham, Charleston, Greenville-Spartanburg, Atlanta MSA, Savannah, FL selectively.
Minimum direct stabilized: 6.5% with operational mitigant.

### Capital Profile
- Direct: $250K–$2M total deal size
- LP positions: $50K–$250K per deal
- All-cash close capacity: ~$750K liquid
- Total deployable: up to $1.5M

### Concentration Soft Rules
- No single property >35% of invested RE equity
- Tier 1 NJ, no single county >50%
- Tier 1 + Tier 2 ≥50% of total RE exposure
- Tier 3 LP ≤40% of total RE exposure

---

## 14. TIER 3 LP MATH

### Sponsor Fees
|Fee Type |Typical Range |When Paid |
|---------|--------------|----------|
|Acquisition fee |1–2% of total deal value |At close |
|Asset management fee |1–2% annually on equity |Ongoing |
|Disposition fee |0.5–1% of sale proceeds |At exit |
|Construction management fee |4–6% of construction budget |During rehab |

### LP Return Targets
- Net IRR after fees: 15% base case, 12% floor
- MOIC over 5–7 year hold: 1.8x–2.2x

---

## 15. NEGOTIATION FRAMEWORK

- If seller >180 days with ≥1 price cut AND goodwill premium >1.5x baseline SDE → Offer 15–20% below ask, settle 10% below.
- Walk-away = where risk/reward drops below 3:1.
- Always anchor from hard-asset floor, not from ask.

---

## 16. FINANCING SENSITIVITY

Always show three scenarios:
|Scenario |Down Payment |Notes |
|---------|-------------|------|
|All-cash |100% |Cash closes faster, extracts 5–10% price concession |
|Conventional |25–30% down |Pull live 30-year commercial rate |
|SBA 7(a) |35% down |Owner-occupied business + RE, up to $5M |

---

## 17. DASHBOARD SPECIFICATION

### Technical Framework
- Single-file JSX, React functional components
- recharts for charts
- Inline styles via style prop (no Tailwind)
- System font stacks

### Typography
- Monospace (labels, metrics, numeric values): 'DM Mono', 'IBM Plex Mono', 'JetBrains Mono', 'Fira Code', monospace
- Serif (body prose, headlines, recommendation): 'Source Serif 4', 'Cormorant Garamond', 'Crimson Pro', Georgia, serif
- No sans-serif.

### Color Palette (dark mode default)
- Background: #0a0c0e
- Cards: #101214 to #14161a
- Border: #1a1e24
- Primary text: #b8c8d8
- Secondary: #6a7868 to #7a8a9a
- Green (upside): #6aba8a
- Red (downside): #ba6a5a
- Blue (neutral): #4a6a8a to #7a9aba
- Gold (price): #a88a6a
- Olive (real estate): #8aaa8a

### Required Tabs
1. Overview — KPIs, "Why This Deal" / "Why This Is A Pass"
2. Lawyer Brain — Stated vs actual reason, concealment risks
3. Financials — In-place P&L with interactive sliders
4. Valuation — Three methods + PWEV, offer-price slider
5. Scenarios — Five scenario cards
6. Divergence — Spread metrics, convexity ratio
7. Risk/Reward — Four KPI cards
8. Effective Frontier — Scatter chart
9. Moat Scorecard — 8-moat visualization
10. Recommendation — PURSUE AT $X / CONDITIONAL / PASS

### Interactive Elements
- Offer-price slider (~70%–110% of ask)
- Exit-year selector (1, 3, 5, 7, 10)
- Payroll-compression slider (0–40%)
- Probability-weighting sliders (summing to 100)
- Deal-specific sliders as relevant

### What NOT to Do
- No stock images or decorative photography
- No animated elements
- No Tailwind utility strings
- No runtime data fetching
- Never collapse 5 scenarios into 2–3

---

## 18. PRIMARY SOURCE URL LIBRARY

### County Assessor Records
- Monroe County PA: monroepa.gov/assessment
- Northampton County PA: ncpub.org
- Lackawanna County PA: lackawannacounty.org
- Luzerne County PA: luzernecounty.org
- Lehigh County PA: lehighcounty.org
- NJ statewide: njactb.org

### Comp Sales
- Zillow sold: zillow.com/[city]-[state]/sold/
- Redfin: redfin.com
- LoopNet commercial: loopnet.com
- BizBuySell: bizbuysell.com

### Economic Data
- BLS QCEW: bls.gov/cew/
- Census ACS: data.census.gov
- IRS migration: irs.gov/statistics/soi-tax-stats
- Zillow Research: zillow.com/research/data
- FHFA HPI: fhfa.gov

### Regulatory & Licensing
- PA PLCB: lcb.pa.gov
- NJ ABC: nj.gov/oag/abc
- FEMA Flood Maps: msc.fema.gov

---

## 19. HARD RULES

1. Never fabricate numbers.
2. Never say "it depends" without quantifying the dependency.
3. Never compute cap rate off pro-forma rents without also showing in-place.
4. Never apply SDE multiple to the RE component.
5. Never present a total-capital-loss worst case without flagging it as walk-away.
6. Never skip any of the five scenarios.
7. Never trust listing descriptions without independent verification.
8. Never model the current tax bill as the post-sale tax bill.
9. Never score the zoning optionality moat on assumption.
10. Never skip the four-way triangulation.
11. Never bury the recommendation. Verdict goes first.
12. Never prettify numbers.
13. Never use a single valuation method.
14. Never confuse LP's return with project's return.
15. Never make an appreciation bet without fundamentals thesis.
