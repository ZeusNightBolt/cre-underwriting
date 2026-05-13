#!/usr/bin/env python3
"""
cre_underwriting.financial_levers — Pillar 4: Financial Modeling & Business Levers.

Builds 5-year pro forma with lever-enhanced scenarios.
Property-type-specific lever catalog.
"""
from typing import Dict, Any, List, Optional


# ── Business Lever Catalog (by property type) ──
RETAIL_LEVERS = [
    {
        "name": "Push rents to market",
        "category": "operational",
        "revenue_impact_annual": 15000,  # placeholder, calculated dynamically
        "capex": 0,
        "zoning_risk": "none",
        "timeline_months": 12,
        "probability": 0.70,
        "description": "In-place rents $9.99/SF, market $13-14/SF. 30-40% upside."
    },
    {
        "name": "Add vending machines",
        "category": "ancillary",
        "revenue_impact_annual": 3000,
        "capex": 2000,
        "zoning_risk": "none",
        "timeline_months": 1,
        "probability": 0.90,
        "description": "Place 2-3 vending machines in common area. $1-3K/yr net."
    },
    {
        "name": "Add ATM",
        "category": "ancillary",
        "revenue_impact_annual": 1800,
        "capex": 0,
        "zoning_risk": "none",
        "timeline_months": 1,
        "probability": 0.85,
        "description": "ATM surcharge revenue sharing. ~$150/mo net."
    },
    {
        "name": "Convert storage to rentable SF",
        "category": "operational",
        "revenue_impact_annual": 5000,
        "capex": 15000,
        "zoning_risk": "low",
        "timeline_months": 3,
        "probability": 0.60,
        "description": "Convert 500-800 SF of storage/utility space to rentable area."
    },
    {
        "name": "Add outdoor seating/patio",
        "category": "improvement",
        "revenue_impact_annual": 4000,
        "capex": 20000,
        "zoning_risk": "low",
        "timeline_months": 3,
        "probability": 0.50,
        "description": "Add outdoor seating for restaurant tenant. Increases rent premium."
    },
    {
        "name": "Add cell tower lease",
        "category": "ancillary",
        "revenue_impact_annual": 24000,
        "capex": 0,
        "zoning_risk": "medium",
        "timeline_months": 12,
        "probability": 0.15,
        "description": "Lease rooftop/land to cell carrier. $2K/mo typical. Requires carrier need."
    },
    {
        "name": "Subdivide large bay",
        "category": "structural",
        "revenue_impact_annual": 10000,
        "capex": 40000,
        "zoning_risk": "medium",
        "timeline_months": 6,
        "probability": 0.40,
        "description": "Split one large bay into 2 smaller units. Smaller units rent at higher $/SF."
    },
    {
        "name": "Add drive-thru",
        "category": "structural",
        "revenue_impact_annual": 15000,
        "capex": 75000,
        "zoning_risk": "medium",
        "timeline_months": 6,
        "probability": 0.25,
        "description": "Add drive-thru lane for QSR tenant. Commands significant rent premium."
    },
    {
        "name": "Convert to smoke shop / specialty retail",
        "category": "tenant_mix",
        "revenue_impact_annual": 8000,
        "capex": 10000,
        "zoning_risk": "medium",
        "timeline_months": 3,
        "probability": 0.30,
        "description": "Reposition one bay as smoke shop or specialty retail. Higher rent tolerance."
    },
    {
        "name": "Add apartment unit (if zoning allows)",
        "category": "structural",
        "revenue_impact_annual": 12000,
        "capex": 80000,
        "zoning_risk": "high",
        "timeline_months": 12,
        "probability": 0.10,
        "description": "Convert portion to residential. C2 zoning likely needs variance."
    },
    {
        "name": "Acquire neighboring rental house",
        "category": "expansion",
        "revenue_impact_annual": 9600,
        "capex": 150000,
        "zoning_risk": "low",
        "timeline_months": 3,
        "probability": 0.20,
        "description": "Listing mentions 'neighboring rental house can potentially be included.'"
    },
]

OFFICE_LEVERS = [
    {"name": "Convert to co-working", "category": "operational", "revenue_impact_annual": 20000, "capex": 50000, "zoning_risk": "low", "timeline_months": 6, "probability": 0.50},
    {"name": "Add executive suites", "category": "structural", "revenue_impact_annual": 15000, "capex": 35000, "zoning_risk": "low", "timeline_months": 4, "probability": 0.60},
    {"name": "Medical office conversion", "category": "tenant_mix", "revenue_impact_annual": 25000, "capex": 75000, "zoning_risk": "medium", "timeline_months": 6, "probability": 0.40},
    {"name": "Add conference room rental", "category": "ancillary", "revenue_impact_annual": 6000, "capex": 10000, "zoning_risk": "none", "timeline_months": 2, "probability": 0.75},
]


def get_lever_catalog(property_type: str) -> List[Dict]:
    """Return the lever catalog for a given property type."""
    catalogs = {"Retail": RETAIL_LEVERS, "Office": OFFICE_LEVERS}
    return catalogs.get(property_type, RETAIL_LEVERS)


def build_pro_forma(deal: Dict[str, Any], purchase_price: float = None) -> Dict[str, Any]:
    """
    Build 5-year pro forma:
    - Gross rent (starting + annual escalation)
    - Vacancy (market rate, improves with active management)
    - Operating expenses (by lease type)
    - Property taxes (post-sale)
    - NOI → exit value → IRR
    """
    prop = deal.get("property", {})
    sf = prop.get("sf", 0) or 0
    leases = deal.get("leases", {})
    tax = deal.get("tax", {})
    post_sale = tax.get("post_sale", {})
    
    current_rent_psf = leases.get("current_rent_psf", 10) or 10
    market_rent_psf = leases.get("market_rent_psf", 13) or 13
    purchase = purchase_price or deal.get("purchase_price", prop.get("price", 0) or 0)
    exit_cap = deal.get("exit_cap_rate", 0.08) or 0.08
    
    # Conservative assumptions
    rent_growth = 0.03       # 3% annual escalation
    vacancy_yr1 = 0.15       # 15% vacancy year 1 (stabilizing)
    vacancy_stabilized = 0.08  # 8% long-term
    expense_ratio = 0.25     # 25% of EGI for operating expenses (NNN/modified gross retail)
    mgmt_fee = 0.04          # 4% of EGI
    reserves_sf_month = 0.12  # $0.12/SF/month reserves (Class C retail)
    
    years = []
    for yr in range(1, 6):
        # Rent ramps from current to market over 3 years
        if yr == 1:
            avg_rent = current_rent_psf
            vacancy = vacancy_yr1
        elif yr == 2:
            avg_rent = current_rent_psf + (market_rent_psf - current_rent_psf) * 0.33
            vacancy = vacancy_yr1 * 0.7
        elif yr == 3:
            avg_rent = current_rent_psf + (market_rent_psf - current_rent_psf) * 0.67
            vacancy = vacancy_stabilized
        else:
            avg_rent = market_rent_psf * (1 + rent_growth) ** (yr - 3)
            vacancy = vacancy_stabilized
        
        pgi = sf * avg_rent                          # Potential Gross Income
        vcl = pgi * vacancy                           # Vacancy & Collection Loss
        egi = pgi - vcl                               # Effective Gross Income
        
        # Property taxes (explicit, post-sale)
        prop_tax = post_sale.get("annual_tax_estimated", egi * 0.20)
        
        opex_ex_tax = egi * (expense_ratio - 0.05)    # OpEx excluding property tax
        mgmt = egi * mgmt_fee                         # Management Fee
        resv = reserves_sf_month * sf * 12            # Annual Reserves
        noi = egi - opex_ex_tax - mgmt - resv - prop_tax  # Net Operating Income
        
        years.append({
            "year": yr,
            "avg_rent_psf": round(avg_rent, 2),
            "pgi": round(pgi),
            "vacancy_pct": round(vacancy * 100, 1),
            "egi": round(egi),
            "opex": round(opex_ex_tax),
            "property_tax": round(prop_tax),
            "noi": round(noi),
            "cap_rate_implied": round(noi / purchase * 100, 1) if purchase else 0,
        })
    yr5_noi = years[-1]["noi"]
    exit_value = yr5_noi / exit_cap if exit_cap > 0 else 0
    
    # IRR (simplified: equity multiple based)
    total_cash_flow = sum(y["noi"] for y in years)
    equity_multiple = (total_cash_flow + exit_value) / purchase if purchase > 0 else 0
    simple_irr = (equity_multiple ** (1/5) - 1) * 100 if equity_multiple > 0 else 0
    
    return {
        "purchase_price": purchase,
        "exit_cap_rate": exit_cap,
        "exit_value": round(exit_value, -3),
        "yearly_projections": years,
        "total_5yr_noi": round(total_cash_flow),
        "equity_multiple": round(equity_multiple, 2),
        "simple_irr_pct": round(simple_irr, 1),
        "cash_on_cash_yr1_pct": round(years[0]["noi"] / purchase * 100, 1) if purchase else 0,
    }


def lever_analysis(deal: Dict[str, Any], purchase_price: float = None) -> Dict[str, Any]:
    """
    Analyze applicable business levers. Score each by: revenue potential, 
    capex required, zoning risk, timeline, probability.
    """
    prop = deal.get("property", {})
    property_type = prop.get("property_type", "Retail")
    listing_text = deal.get("description", prop.get("description", "")) or ""
    
    catalog = get_lever_catalog(property_type)
    
    # Dynamic adjustments based on property specifics
    sf = prop.get("sf", 0) or 0
    market_rent_psf = deal.get("leases", {}).get("market_rent_psf", 13)
    current_rent_psf = deal.get("leases", {}).get("current_rent_psf", 10)
    rent_gap = market_rent_psf - current_rent_psf
    
    levers = []
    for lever in catalog:
        # Dynamically compute revenue for rent-push lever
        if "push rents" in lever["name"].lower() or "market" in lever["name"].lower():
            lever = dict(lever)
            lever["revenue_impact_annual"] = round(sf * rent_gap * 0.8)  # 80% capture of gap
        
        score = (
            lever["revenue_impact_annual"] / 1000 * 1.0 +  # revenue weight
            (1 - lever.get("capex", 0) / 200000) * 1.0 +  # capex efficiency
            (1 - {"none": 0, "low": 0.2, "medium": 0.5, "high": 0.8}[lever.get("zoning_risk", "none")]) * 1.0 +
            lever.get("probability", 0) * 2.0  # probability weight
        )
        
        levers.append({
            **lever,
            "score": round(score, 1),
            "roi_year1_pct": round(lever["revenue_impact_annual"] / max(lever["capex"], 1) * 100, 1) if lever.get("capex") else 999,
        })
    
    # Sort by score descending
    levers.sort(key=lambda l: l["score"], reverse=True)
    
    top_levers = levers[:5]
    
    return {
        "property_type": property_type,
        "total_levers_catalogued": len(catalog),
        "top_levers": top_levers,
        "all_levers": levers,
        "recommended_phasing": {
            "phase_1_immediate": [l for l in levers if l["capex"] < 5000 and l["timeline_months"] <= 3],
            "phase_2_medium": [l for l in levers if 5000 <= l["capex"] <= 50000],
            "phase_3_structural": [l for l in levers if l["capex"] > 50000 or l["timeline_months"] > 6],
        },
        "total_potential_revenue_uplift": sum(l["revenue_impact_annual"] for l in levers),
    }


if __name__ == "__main__":
    test_deal = {
        "property": {"sf": 7500, "property_type": "Retail", "price": 825000},
        "leases": {"current_rent_psf": 9.99, "market_rent_psf": 13.00},
        "purchase_price": 550000,
        "exit_cap_rate": 0.08,
        "tax": {"post_sale": {"annual_tax_estimated": 17325}},
    }
    
    import json
    proforma = build_pro_forma(test_deal)
    print("=== PRO FORMA ===")
    print(json.dumps(proforma, indent=2))
    
    levers = lever_analysis(test_deal)
    print("\n=== TOP LEVERS ===")
    for l in levers["top_levers"]:
        print(f"  {l['name']}: +${l['revenue_impact_annual']:,}/yr | Capex ${l.get('capex',0):,} | Score {l['score']}")
