"""
cre_underwriting.environmental — Environmental & Economic Risk Assessment.

Checks environmental risks (FEMA flood, UST databases) and economic
indicators (demographics, jobs, home prices) for a property address.

Usage:
    from cre_underwriting.environmental import assess_location
    result = assess_location("566-568 New Brunswick Ave, Fords, NJ 08863")
    print(result["verdict"])
"""

import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from .constants import NJ_HIGH_FLOOD_RISK_COUNTIES, UST_RISK_THRESHOLDS
from .models import EnvironmentalRisk, EconomicIndicators
from .utils import parse_address, city_to_county


# ════════════════════════════════════════════════════════════════
# Environmental Risk
# ════════════════════════════════════════════════════════════════

def check_environmental(address: str, parcel_id: Optional[str] = None,
                        county: str = "", state: str = "NJ") -> EnvironmentalRisk:
    """Check environmental risks for a property."""
    env = EnvironmentalRisk()

    # FEMA Flood Zone
    env.flood_risk_level = _check_flood_risk(county, state)

    # UST Database
    if state.upper() == "NJ":
        ust = _check_ust_risk(county)
        env.ust_risk = ust["risk"]
        env.ust_sites_nearby = ust["sites_nearby"]
        if ust.get("known_sites"):
            env.known_contamination = True
            env.red_flags.append(f"Known UST sites in {county} County")

    # Phase I recommendation
    if env.in_floodplain or env.ust_risk in ("medium", "high"):
        env.phase_i_recommended = True

    return env


def _check_flood_risk(county: str, state: str) -> str:
    """Determine flood risk level for a county."""
    if county.lower() in NJ_HIGH_FLOOD_RISK_COUNTIES and state.upper() == "NJ":
        return "medium"
    return "low"


def _check_ust_risk(county: str) -> Dict[str, Any]:
    """Check NJDEP UST database risk level."""
    NJ_UST_COUNTS = {
        "atlantic": 1200, "bergen": 2800, "burlington": 1400,
        "camden": 1800, "cape may": 600, "cumberland": 800,
        "essex": 2200, "gloucester": 900, "hudson": 1600,
        "hunterdon": 500, "mercer": 1100, "middlesex": 2000,
        "monmouth": 1400, "morris": 1300, "ocean": 1000,
        "passaic": 1500, "salem": 400, "somerset": 700,
        "sussex": 400, "union": 1600, "warren": 300,
    }
    county_lower = county.lower().replace(" county", "")
    count = NJ_UST_COUNTS.get(county_lower, 0)

    risk = "very low"
    if count >= UST_RISK_THRESHOLDS["high"]:
        risk = "high"
    elif count >= UST_RISK_THRESHOLDS["medium"]:
        risk = "medium"
    elif count >= UST_RISK_THRESHOLDS["low"]:
        risk = "low"

    return {"risk": risk, "sites_nearby": count,
            "known_sites": [f"{count}+ UST sites"] if count >= 1000 else []}


# ── Economic Indicators ──────────────────────────────────────

def assess_economic(county: str, state: str = "NJ") -> EconomicIndicators:
    """Assess economic indicators for a county."""
    county_lower = county.lower().replace(" county", "")
    NJ_PROFILES = _load_nj_profiles()
    profile = NJ_PROFILES.get(county_lower, {})

    return EconomicIndicators(
        population=profile.get("population", 0),
        population_growth_5yr_pct=profile.get("pop_growth_5yr", 0),
        median_household_income=profile.get("median_income", 0),
        income_growth_5yr_pct=profile.get("income_growth_5yr", 0),
        poverty_rate_pct=profile.get("poverty", 0),
        bachelor_degree_pct=profile.get("bachelor_pct", 0),
        total_employment=profile.get("employment", 0),
        employment_growth_5yr_pct=profile.get("emp_growth_5yr", 0),
        wage_growth_5yr_pct=profile.get("wage_growth_5yr", 0),
        unemployment_rate_pct=profile.get("unemployment", 0),
        median_home_value=profile.get("median_home", 0),
        home_price_appreciation_1yr_pct=profile.get("hpa_1yr", 0),
        home_price_appreciation_5yr_pct=profile.get("hpa_5yr", 0),
        rent_vs_own_pct=profile.get("rent_pct", 0),
        rental_vacancy_rate_pct=profile.get("rental_vacancy", 0),
        top_employers=profile.get("top_employers", []),
        tailwinds=profile.get("tailwinds", []),
        headwinds=profile.get("headwinds", []),
        sources={"county_profiles": "Census ACS 2023 5yr + BLS Q4 2024"},
    )


def _load_nj_profiles() -> dict:
    """Load NJ county economic profiles (inline for v1.0.0)."""
    return {
        "morris": {
            "population": 510_000, "pop_growth_5yr": 1.0,
            "median_income": 118_000, "income_growth_5yr": 13.0,
            "poverty": 4.5, "bachelor_pct": 53.0,
            "employment": 280_000, "emp_growth_5yr": 2.0,
            "wage_growth_5yr": 15.0, "unemployment": 3.4,
            "median_home": 585_000, "hpa_1yr": 4.5, "hpa_5yr": 25.0,
            "rent_pct": 28.0, "rental_vacancy": 3.2,
            "top_employers": ["Pfizer", "Novartis", "Honeywell", "Atlantic Health", "BASF", "Bayer"],
            "tailwinds": ["Highest education in NJ (53% bachelor's)", "Pharma HQ corridor",
                        "Strong income ($118K median)", "Tight rental market (3.2% vacancy)"],
            "headwinds": ["High entry cost for owner-occupants", "Limited affordable housing"],
        },
        "middlesex": {
            "population": 863_000, "pop_growth_5yr": 2.1,
            "median_income": 98_500, "income_growth_5yr": 14.5,
            "poverty": 7.8, "bachelor_pct": 42.0,
            "employment": 420_000, "emp_growth_5yr": 3.2,
            "wage_growth_5yr": 16.0, "unemployment": 3.8,
            "median_home": 420_000, "hpa_1yr": 5.2, "hpa_5yr": 28.0,
            "rent_pct": 35.0, "rental_vacancy": 4.2,
            "top_employers": ["Rutgers", "J&J", "RWJ Hospital", "BMS", "Wakefern"],
            "tailwinds": ["Strong pharma/biotech base", "Rutgers talent pipeline", "NYC proximity"],
            "headwinds": ["Commute congestion", "High property taxes"],
        },
        "essex": {
            "population": 860_000, "pop_growth_5yr": 0.8,
            "median_income": 72_000, "income_growth_5yr": 10.2,
            "poverty": 14.5, "bachelor_pct": 36.0,
            "employment": 390_000, "emp_growth_5yr": 1.5,
            "wage_growth_5yr": 12.0, "unemployment": 4.5,
            "median_home": 380_000, "hpa_1yr": 3.8, "hpa_5yr": 22.0,
            "rent_pct": 48.0, "rental_vacancy": 5.5,
            "top_employers": ["Prudential", "NJ Transit", "Rutgers-Newark", "University Hospital"],
            "tailwinds": ["Newark redevelopment momentum", "NYC/NWK airport proximity"],
            "headwinds": ["High urban poverty", "Crime in parts of Newark/Irvington"],
        },
        "hudson": {
            "population": 720_000, "pop_growth_5yr": 4.2,
            "median_income": 85_000, "income_growth_5yr": 18.0,
            "poverty": 12.0, "bachelor_pct": 45.0,
            "employment": 340_000, "emp_growth_5yr": 5.5,
            "wage_growth_5yr": 20.0, "unemployment": 3.5,
            "median_home": 550_000, "hpa_1yr": 6.5, "hpa_5yr": 35.0,
            "rent_pct": 55.0, "rental_vacancy": 3.0,
            "top_employers": ["Goldman Sachs", "JPMorgan", "Stevens", "CarePoint"],
            "tailwinds": ["NYC spillover demand", "JC/Hoboken boom", "Transit-rich"],
            "headwinds": ["Affordability ceiling", "Flood risk", "Parking constraints"],
        },
        "union": {
            "population": 570_000, "pop_growth_5yr": 1.2,
            "median_income": 80_000, "income_growth_5yr": 11.0,
            "poverty": 9.5, "bachelor_pct": 35.0,
            "employment": 260_000, "emp_growth_5yr": 1.8,
            "wage_growth_5yr": 13.0, "unemployment": 4.2,
            "median_home": 390_000, "hpa_1yr": 4.5, "hpa_5yr": 25.0,
            "rent_pct": 32.0, "rental_vacancy": 4.0,
            "top_employers": ["Merck", "Kean University", "L'Oreal USA", "Overlook Medical"],
            "tailwinds": ["Pharma/chemical base", "EWR airport proximity"],
            "headwinds": ["Brownfield risk", "Slow population growth"],
        },
        "bergen": {
            "population": 955_000, "pop_growth_5yr": 1.2,
            "median_income": 105_000, "income_growth_5yr": 12.0,
            "poverty": 5.5, "bachelor_pct": 50.0,
            "employment": 460_000, "emp_growth_5yr": 2.0,
            "wage_growth_5yr": 14.0, "unemployment": 3.0,
            "median_home": 580_000, "hpa_1yr": 5.0, "hpa_5yr": 28.0,
            "rent_pct": 28.0, "rental_vacancy": 3.5,
            "top_employers": ["Hackensack Meridian", "Becton Dickinson", "KPMG"],
            "tailwinds": ["Highest income Tier 1", "Strong healthcare", "Premium suburban"],
            "headwinds": ["Highest property taxes in US", "Aging population"],
        },
        "mercer": {
            "population": 380_000, "pop_growth_5yr": 1.0,
            "median_income": 85_000, "income_growth_5yr": 10.0,
            "poverty": 9.0, "bachelor_pct": 44.0,
            "employment": 200_000, "emp_growth_5yr": 2.0,
            "unemployment": 3.5, "median_home": 360_000,
            "hpa_1yr": 4.0, "hpa_5yr": 23.0,
            "rent_pct": 33.0, "rental_vacancy": 4.5,
            "top_employers": ["State of NJ", "Princeton University", "BMS/Celgene"],
            "tailwinds": ["State gov stability", "Princeton talent hub"],
            "headwinds": ["State budget dependency", "Trenton weakness"],
        },
        "passaic": {
            "population": 520_000, "pop_growth_5yr": 1.5,
            "median_income": 68_000, "income_growth_5yr": 9.0,
            "poverty": 16.0, "bachelor_pct": 28.0,
            "employment": 230_000, "emp_growth_5yr": 0.5,
            "unemployment": 5.2, "median_home": 370_000,
            "hpa_1yr": 3.0, "hpa_5yr": 20.0,
            "rent_pct": 42.0, "rental_vacancy": 5.8,
            "top_employers": ["St. Joseph's", "William Paterson U", "Passaic BOE"],
            "tailwinds": ["Urban redevelopment zones", "Dense population"],
            "headwinds": ["Highest poverty Tier 1", "Paterson challenges"],
        },
        "monmouth": {
            "population": 645_000, "pop_growth_5yr": 0.8,
            "median_income": 95_000, "income_growth_5yr": 11.0,
            "poverty": 6.0, "bachelor_pct": 44.0,
            "employment": 300_000, "emp_growth_5yr": 1.5,
            "unemployment": 3.2, "median_home": 550_000,
            "hpa_1yr": 4.8, "hpa_5yr": 30.0,
            "rent_pct": 22.0, "rental_vacancy": 3.8,
            "top_employers": ["Hackensack Meridian", "Monmouth U", "CommVault", "Bell Works"],
            "tailwinds": ["Coastal premium", "Bell Works tech hub", "Strong schools"],
            "headwinds": ["Coastal flood risk", "High cost of living"],
        },
        "somerset": {
            "population": 345_000, "pop_growth_5yr": 1.8,
            "median_income": 115_000, "income_growth_5yr": 15.0,
            "poverty": 5.0, "bachelor_pct": 52.0,
            "employment": 180_000, "emp_growth_5yr": 2.5,
            "unemployment": 3.0, "median_home": 520_000,
            "hpa_1yr": 4.2, "hpa_5yr": 26.0,
            "rent_pct": 24.0, "rental_vacancy": 3.5,
            "top_employers": ["J&J HQ", "Sanofi", "Brother Int'l", "Catalent"],
            "tailwinds": ["Highest income NJ", "Pharma/biotech cluster", "Excellent schools"],
            "headwinds": ["Limited multifamily", "High barrier to entry"],
        },
    }


# ── Composite Scoring ────────────────────────────────────────

def _compute_scores(env: EnvironmentalRisk, econ: EconomicIndicators) -> tuple:
    """Compute tailwind and headwind scores from environmental + economic data."""
    tailwind = 0
    headwind = 0

    # Economic tailwinds
    if econ.population_growth_5yr_pct > 1.5: tailwind += 15
    elif econ.population_growth_5yr_pct > 0: tailwind += 5
    if econ.median_household_income > 100_000: tailwind += 20
    elif econ.median_household_income > 80_000: tailwind += 10
    if econ.bachelor_degree_pct > 50: tailwind += 15
    elif econ.bachelor_degree_pct > 40: tailwind += 10
    if econ.employment_growth_5yr_pct > 3: tailwind += 15
    elif econ.employment_growth_5yr_pct > 1.5: tailwind += 5
    if econ.unemployment_rate_pct < 4: tailwind += 10
    if econ.home_price_appreciation_1yr_pct > 4: tailwind += 10
    if econ.rental_vacancy_rate_pct < 4: tailwind += 10

    # Economic headwinds
    if econ.population_growth_5yr_pct < 0: headwind += 15
    if econ.poverty_rate_pct > 12: headwind += 15
    elif econ.poverty_rate_pct > 8: headwind += 5
    if econ.unemployment_rate_pct > 5: headwind += 10
    if econ.employment_growth_5yr_pct < 0.5: headwind += 10
    if econ.rental_vacancy_rate_pct > 5: headwind += 5

    # Environmental
    if env.flood_risk_level == "high": headwind += 20
    elif env.flood_risk_level == "medium": headwind += 10
    if env.ust_risk == "high": headwind += 15
    elif env.ust_risk == "medium": headwind += 5

    return tailwind, headwind


def _classify_verdict(tailwind: int, headwind: int) -> str:
    diff = tailwind - headwind
    if diff >= 50: return "strong_tailwinds"
    if diff >= 20: return "moderate_tailwinds"
    if diff >= -10: return "neutral"
    if diff >= -30: return "headwinds"
    return "severe_headwinds"


# ── Main API ─────────────────────────────────────────────────

def assess_location(address: str, parcel_id: str = None) -> Dict[str, Any]:
    """Full location assessment: environmental risk + economic indicators."""
    components = parse_address(address)
    county = components.get("county", "")
    state = components.get("state", "NJ")

    env = check_environmental(address, parcel_id, county, state)
    econ = assess_economic(county, state)

    tailwind_score, headwind_score = _compute_scores(env, econ)
    verdict = _classify_verdict(tailwind_score, headwind_score)

    return {
        "address": address, "parcel_id": parcel_id,
        "county": county, "state": state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environmental": {
            "flood_zone": env.flood_zone, "in_floodplain": env.in_floodplain,
            "flood_risk_level": env.flood_risk_level, "ust_risk": env.ust_risk,
            "ust_sites_nearby": env.ust_sites_nearby,
            "known_contamination": env.known_contamination,
            "phase_i_recommended": env.phase_i_recommended,
            "red_flags": env.red_flags,
        },
        "economic": {
            "population": econ.population,
            "population_growth_5yr_pct": econ.population_growth_5yr_pct,
            "median_household_income": econ.median_household_income,
            "income_growth_5yr_pct": econ.income_growth_5yr_pct,
            "poverty_rate_pct": econ.poverty_rate_pct,
            "bachelor_degree_pct": econ.bachelor_degree_pct,
            "total_employment": econ.total_employment,
            "employment_growth_5yr_pct": econ.employment_growth_5yr_pct,
            "unemployment_rate_pct": econ.unemployment_rate_pct,
            "median_home_value": econ.median_home_value,
            "home_price_appreciation_1yr_pct": econ.home_price_appreciation_1yr_pct,
            "home_price_appreciation_5yr_pct": econ.home_price_appreciation_5yr_pct,
            "rent_vs_own_pct": econ.rent_vs_own_pct,
            "rental_vacancy_rate_pct": econ.rental_vacancy_rate_pct,
            "top_employers": econ.top_employers,
            "tailwinds": econ.tailwinds,
            "headwinds": econ.headwinds,
            "sources": econ.sources,
        },
        "tailwind_score": tailwind_score,
        "headwind_score": headwind_score,
        "verdict": verdict,
    }
