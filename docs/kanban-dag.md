# CRE Underwriting — Kanban Pipeline DAG

## Board: cre-underwriting

### Phase 1: LoopNet Scrape
- **Card**: `loopnet-scrape`
- **Skill**: `loopnet-scraper` (master)
- **Input**: search params (state=NJ, max_price=1500000)
- **Output**: `deals/{date}/listings.json`
- **Dependency**: none
- **Pre-flight**: `bash ~/hermes-firefox-remote.sh start`

### Phase 2: Parse Listings
- **Card**: `parse-listings`
- **Skill**: `listing-parser` (master)
- **Input**: `deals/{date}/listings.json`
- **Output**: `deals/{date}/deals.json` (array of structured deals)
- **Dependency**: Phase 1

### Phase 3a: Underwrite (parallel with 3b, 3c)
- **Card**: `underwrite-deal`
- **Skill**: `deal-underwriter` (specialized: `projects/cre-underwriting/skills/finance/deal-underwriter/`)
- **Input**: `deals/{deal_id}/deal.json`
- **Output**: `deals/{deal_id}/analysis.json`
- **Dependency**: Phase 2 (one card per deal)
- **Parallel**: ✓ (with Phase 3b, 3c — all per deal)

### Phase 3b: Find Comps (parallel with 3a)
- **Card**: `find-comps`
- **Skill**: `comp-finder` (specialized)
- **Input**: `deals/{deal_id}/deal.json`
- **Output**: `deals/{deal_id}/comps.json`
- **Dependency**: Phase 2

### Phase 3c: Environmental (parallel with 3a)
- **Card**: `assess-environmental`
- **Skill**: `environmental-assessor` (specialized)
- **Input**: `deals/{deal_id}/deal.json`
- **Output**: `deals/{deal_id}/environmental.json`
- **Dependency**: Phase 2

### Phase 4: Build Dashboard
- **Card**: `build-dashboard`
- **Skill**: `cre-dashboard-builder` (specialized)
- **Input**: `deals/{deal_id}/analysis.json` + `comps.json` + `environmental.json`
- **Output**: `deals/{deal_id}/dashboard.html`
- **Dependency**: Phase 3a AND Phase 3b AND Phase 3c

### Phase 5: Deploy
- **Card**: `vercel-deploy`
- **Skill**: `vercel-deploy` (master)
- **Input**: `deals/{deal_id}/dashboard.html`
- **Output**: deployed Vercel URL
- **Dependency**: Phase 4

## Kanban Graph

```
[scrape] ──→ [parse] ──┬──→ [underwrite] ──┐
                        ├──→ [comps] ────────┤
                        └──→ [environmental] ┤
                                              ├──→ [dashboard] ──→ [deploy]
                                              
(one set of Phase 3 cards PER DEAL — up to 5 deals parallel)
```

## Multi-Deal Fan-Out

When scraping multiple listings:
1. Phase 1: Single `loopnet-scrape` card → `listings.json` with N listings
2. Phase 2: Single `parse-listings` card → `deals.json` with N deals
3. Phase 3: N × 3 cards (one underwriter + one comps + one environmental per deal)
4. Phase 4: N dashboard cards (one per deal)
5. Phase 5: N deploy cards (one per deal)

All deal-level cards run in parallel. No dependencies between different deals.

## Firefox Pre-Flight

LoopNet scraping requires Firefox BiDi. The orchestrator must:
1. Check `bash ~/hermes-firefox-remote.sh status`
2. If not running: `bash ~/hermes-firefox-remote.sh start`
3. Wait for `ws://127.0.0.1:9222/session` to be available
4. THEN create Kanban card for `loopnet-scrape`
