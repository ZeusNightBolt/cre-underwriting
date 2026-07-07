#!/usr/bin/env python3
"""
cre_underwriting.valuation — Pillar 1: Valuation Triangulation.

Hard asset dissection: land value, building replacement cost (depreciated),
equipment value, license detection and valuation.
"""
import json
from typing import Dict, Any, List, Optional


# ── Building replacement cost by property type, class, region ──
REPLACEMENT_COST = {
    "Retail": {
        "A": {"southeast": (180, 250)},
        "B": {"southeast": (130, 180)},
        "C": {"southeast": (80, 130)},
    },
    "Office": {
        "A": {"southeast": (200, 300)},
        "B": {"southeast": (150, 200)},
        "C": {"southeast": (90, 150)},
    },
    "Industrial": {
        "A": {"southeast": (100, 150)},
        "B": {"southeast": (70, 100)},
        "C": {"southeast": (50, 70)},
    },
    "Multifamily": {
        "A": {"southeast": (180, 250)},
        "B": {"southeast": (130, 180)},
        "C": {"southeast": (90, 130)},
    },
}

# ── Depreciation table: age + renovation discount ──
def compute_depreciation(year_built: int, year_renovated: Optional[int] = None,
                          current_year: int = 2026) -> float:
    """Estimate physical depreciation as % of replacement cost."""
    effective_age: float = current_year - (year_renovated or year_built)
    
    # Renovation resets effective age (not to zero, but reduces)
    if year_renovated:
        # Renovation restores ~60% of remaining life
        pre_reno_age = year_renovated - year_built
        post_reno_age = current_year - year_renovated
        effective_age = pre_reno_age * 0.4 + post_reno_age
    
    # Straight-line over 60-year life, minimum residual 15%
    depreciation = min(0.85, effective_age / 60 * 0.85)
    return round(depreciation, 2)


# ── License detection patterns ──
LICENSE_PATTERNS: List[Dict[str, Any]] = [
    {
        "type": "Liquor License",
        "keywords": ["liquor license", "abc license", "alcohol license", "beer and wine",
                      "bar", "tavern", "pub", "restaurant with alcohol"],
        "typical_value": {"SC": (15000, 50000), "NJ": (100000, 350000), "default": (10000, 50000)},
        "transferable_default": True,
        "note": "Value highly state-dependent. SC: relatively affordable. NJ: scarce and expensive."
    },
    {
        "type": "Operating Gas Station",
        "keywords": ["gas station", "fuel station", "filling station", "convenience store with gas"],
        "typical_value": {"default": (50000, 200000)},
        "transferable_default": True,
        "note": "Operating gas station with active permits, fuel contracts, UST compliance."
    },
    {
        "type": "Distribution License",
        "keywords": ["distribution", "wholesale", "warehouse license", "beer distributor",
                      "wine distributor"],
        "typical_value": {"default": (50000, 200000)},
        "transferable_default": True,
        "note": "State-specific. Often tied to territory rights."
    },
    {
        "type": "PILOT / Tax Abatement",
        "keywords": ["pilot", "tax abatement", "payment in lieu", "tax exemption",
                      "abatement", "421-a", "tax incentive"],
        "typical_value": {"default": (0, 500000)},  # NPV calculation
        "transferable_default": True,
        "note": "Present value of remaining tax savings. Property-specific."
    },
    {
        "type": "Cell Tower Lease",
        "keywords": ["cell tower", "antenna", "telecom lease", "wireless facility"],
        "typical_value": {"default": (50000, 150000)},
        "transferable_default": True,
        "note": "Valued at 12-15x annual rent. Typical rent $1,200-3,000/mo."
    },
    {
        "type": "Billboard / Signage Lease",
        "keywords": ["billboard", "outdoor advertising", "pylon sign lease"],
        "typical_value": {"default": (20000, 80000)},
        "transferable_default": True,
        "note": "Highway-facing billboards command premium."
    },
]


def estimate_land_value(lot_acres: float, zoning: str, corridor: str,
                         submarket_context: str = "") -> Dict[str, Any]:
    """Estimate land value range based on acreage, zoning, and location context."""
    # Base land values by context
    if any(w in submarket_context.lower() for w in ["prime", "downtown", "main st", "waterfront"]):
        base_low, base_high = 15, 30  # $/SF
    elif any(w in submarket_context.lower() for w in ["i-85", "i-95", "i-26", "interstate", "freeway"]):
        base_low, base_high = 8, 18
    elif any(w in submarket_context.lower() for w in ["corridor", "highway"]):
        base_low, base_high = 4, 10
    elif any(w in submarket_context.lower() for w in ["growing", "blooming", "emerging"]):
        base_low, base_high = 3, 8
    else:
        base_low, base_high = 2, 6
    
    # Zoning multiplier
    zoning_mult = 1.0
    if any(z in zoning.upper() for z in ["C2", "C3", "C4", "GC", "HC", "MU", "MX"]):
        zoning_mult = 1.2  # broader commercial = more valuable
    elif any(z in zoning.upper() for z in ["I", "M", "IN"]):
        zoning_mult = 0.8  # industrial = less valuable per SF
    
    sf = lot_acres * 43560
    low = sf * base_low * zoning_mult
    high = sf * base_high * zoning_mult
    mid = (low + high) / 2
    
    return {
        "lot_acres": lot_acres,
        "lot_sf": round(sf),
        "value_per_sf_low": round(base_low * zoning_mult, 1),
        "value_per_sf_high": round(base_high * zoning_mult, 1),
        "value_low": round(low, -3),    # round to nearest $1K
        "value_mid": round(mid, -3),
        "value_high": round(high, -3),
        "methodology": f"Land value by acreage: {lot_acres} acres × ${base_low}-{base_high}/SF corridor land × {zoning_mult}x zoning multiplier",
        "zoning_multiplier": zoning_mult,
        "corridor_type": submarket_context[:100]
    }


def estimate_building_value(sf: int, property_type: str, building_class: str,
                             year_built: int, year_renovated: Optional[int] = None,
                             region: str = "southeast") -> Dict[str, Any]:
    """Estimate building replacement cost and depreciated value."""
    # Get replacement cost range
    pt = REPLACEMENT_COST.get(property_type, REPLACEMENT_COST["Retail"])
    bc = pt.get(building_class, pt.get("C", pt[list(pt.keys())[0]]))
    cost_low, cost_high = bc.get(region, bc.get("southeast", (80, 130)))
    
    replacement_low = sf * cost_low
    replacement_high = sf * cost_high
    replacement_mid = (replacement_low + replacement_high) / 2
    
    depreciation = compute_depreciation(year_built, year_renovated)
    
    return {
        "building_sf": sf,
        "property_type": property_type,
        "building_class": building_class,
        "year_built": year_built,
        "year_renovated": year_renovated,
        "replacement_cost_psf_low": cost_low,
        "replacement_cost_psf_high": cost_high,
        "replacement_cost_low": round(replacement_low, -3),
        "replacement_cost_mid": round(replacement_mid, -3),
        "replacement_cost_high": round(replacement_high, -3),
        "depreciation_pct": round(depreciation * 100, 1),
        "depreciated_value_low": round(replacement_low * (1 - depreciation), -3),
        "depreciated_value_mid": round(replacement_mid * (1 - depreciation), -3),
        "depreciated_value_high": round(replacement_high * (1 - depreciation), -3),
        "methodology": f"Replacement cost ${cost_low}-{cost_high}/SF × {sf:,} SF, depreciated {depreciation*100:.0f}% (effective age from {(year_renovated or year_built)})."
    }


def estimate_equipment_value(sf: int, property_type: str, building_class: str,
                               listing_text: str = "") -> Dict[str, Any]:
    """Estimate equipment/FF&E value. For retail, primarily HVAC + electrical."""
    # Base equipment value per SF by property type
    equipment_rate = {
        "Retail": {"A": (15, 25), "B": (8, 15), "C": (3, 8)},
        "Office": {"A": (20, 35), "B": (10, 20), "C": (5, 10)},
        "Industrial": {"A": (10, 20), "B": (5, 10), "C": (2, 5)},
        "Multifamily": {"A": (10, 15), "B": (5, 10), "C": (3, 5)},
    }
    
    pt = equipment_rate.get(property_type, equipment_rate["Retail"])
    bc = pt.get(building_class, pt.get("C", (3, 8)))
    eq_low, eq_high = bc
    
    # Check for special equipment mentions
    special_equipment: List[Dict[str, Any]] = []
    text_lower = listing_text.lower()
    if "walk-in cooler" in text_lower or "walk-in freezer" in text_lower:
        special_equipment.append({"item": "Walk-in cooler/freezer", "value": 20000})
    if "kitchen" in text_lower or "restaurant equipment" in text_lower:
        special_equipment.append({"item": "Commercial kitchen", "value": 50000})
    if "hood" in text_lower or "exhaust" in text_lower:
        special_equipment.append({"item": "Exhaust hood system", "value": 15000})
    if "generator" in text_lower:
        special_equipment.append({"item": "Backup generator", "value": 25000})
    
    special_value = sum(e["value"] for e in special_equipment)
    
    return {
        "equipment_psf_low": eq_low,
        "equipment_psf_high": eq_high,
        "value_low": round(sf * eq_low, -3),
        "value_mid": round(sf * (eq_low + eq_high) / 2, -3),
        "value_high": round(sf * eq_high, -3),
        "special_equipment": special_equipment,
        "special_equipment_value": special_value,
        "total_equipment_low": round(sf * eq_low + special_value, -3),
        "total_equipment_mid": round(sf * (eq_low + eq_high) / 2 + special_value, -3),
        "total_equipment_high": round(sf * eq_high + special_value, -3),
    }


def detect_licenses(listing_text: str, state: Optional[str] = None) -> List[Dict[str, Any]]:
    """Detect transferable licenses from listing description text."""
    import re
    state = (state or "NJ").upper()
    text_lower = listing_text.lower()
    found = []
    
    for pattern in LICENSE_PATTERNS:
        # Use word-boundary matching to avoid false positives
        # (e.g., "ust" shouldn't match inside "investment" or "trust")
        matched = False
        for kw in pattern["keywords"]:
            # For short keywords (≤4 chars), require word boundaries
            if len(kw) <= 4:
                if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                    matched = True
                    break
            else:
                if kw in text_lower:
                    matched = True
                    break
        
        if matched:
            value_range = pattern["typical_value"].get(
                state, pattern["typical_value"].get("default", (10000, 50000))
            )
            found.append({
                "type": pattern["type"],
                "detected": True,
                "transferable": pattern["transferable_default"],
                "value_low": value_range[0],
                "value_high": value_range[1],
                "note": pattern["note"],
            })
    
    return found


def valuation_triangulation(deal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pillar 1: Full valuation triangulation.
    
    Combines land + building + equipment + licenses into a three-point estimate.
    Compares to ask price to determine asset coverage ratio.
    """
    prop = deal.get("property", {})
    listing_text = deal.get("description", prop.get("description", ""))
    
    # Extract fields with safe fallbacks
    sf = prop.get("sf", 0) or 0
    lot_acres = float(prop.get("lot_acres", 0) or 0)
    property_type = prop.get("property_type", "Retail")
    building_class = prop.get("building_class", "C")
    year_built = prop.get("year_built", 1970) or 1970
    year_renovated = prop.get("year_renovated") or None
    zoning = prop.get("zoning", "C2") or "C2"
    ask_price = prop.get("price", 0) or 0
    submarket = deal.get("market", {}).get("submarket", "") or deal.get("submarket", "") or ""
    
    # Description: check top-level, property, and raw listing text
    listing_text = (
        deal.get("description", "") or
        prop.get("description", "") or
        deal.get("raw_text_snippet", "")
    )
    
    # Extract state for license detection
    detected_state = prop.get("state", "NJ") or "NJ"
    
    # Run each component
    land = estimate_land_value(lot_acres, zoning, submarket, submarket)
    building = estimate_building_value(sf, property_type, building_class, 
                                        year_built, year_renovated)
    equipment = estimate_equipment_value(sf, property_type, building_class, listing_text or "")
    licenses = detect_licenses(listing_text or "", detected_state)
    
    license_total = sum(lv["value_high"] for lv in licenses)
    
    # Triangulation
    hard_low = land["value_low"] + building["depreciated_value_low"] + equipment["value_low"] + license_total
    hard_mid = land["value_mid"] + building["depreciated_value_mid"] + equipment["value_mid"] + license_total
    hard_high = land["value_high"] + building["depreciated_value_high"] + equipment["value_high"] + license_total
    
    # Asset coverage
    coverage_low = round(hard_low / ask_price * 100, 1) if ask_price else 0
    coverage_mid = round(hard_mid / ask_price * 100, 1) if ask_price else 0
    coverage_high = round(hard_high / ask_price * 100, 1) if ask_price else 0
    
    return {
        "land": land,
        "building": building,
        "equipment": equipment,
        "licenses_detected": licenses,
        "license_total_value": license_total,
        "hard_asset_value_low": round(hard_low, -3),
        "hard_asset_value_mid": round(hard_mid, -3),
        "hard_asset_value_high": round(hard_high, -3),
        "asset_coverage_low_pct": coverage_low,
        "asset_coverage_mid_pct": coverage_mid,
        "asset_coverage_high_pct": coverage_high,
        "verdict": (
            "STRONG COVERAGE" if coverage_mid >= 80 else
            "ADEQUATE COVERAGE" if coverage_mid >= 60 else
            "MODERATE COVERAGE" if coverage_mid >= 40 else
            "WEAK COVERAGE"
        ),
        "narrative": (
            f"Hard assets (land + depreciated building + equipment) valued at "
            f"${hard_low:,.0f}–${hard_high:,.0f} (mid: ${hard_mid:,.0f}). "
            f"This covers {coverage_mid:.0f}% of the ${ask_price:,.0f} ask price. "
            f"{'The downside is well-protected by physical assets.' if coverage_mid >= 70 else 'Hard asset coverage is below comfort — the premium is for income/intangibles.'}"
        )
    }


if __name__ == "__main__":
    # Test with Augusta Rd property
    test_deal = {
        "property": {
            "sf": 7500,
            "lot_acres": 1.40,
            "property_type": "Retail",
            "building_class": "C",
            "year_built": 1970,
            "year_renovated": 2017,
            "zoning": "C2",
            "state": "SC",
            "price": 825000,
        },
        "market": {"submarket": "Augusta Road Corridor — Greenville SC near I-85"},
        "description": "Value-add retail investment with four tenants, ample parking, pylon sign, dedicated turn lane."
    }
    result = valuation_triangulation(test_deal)
    print(json.dumps(result, indent=2, default=str))
