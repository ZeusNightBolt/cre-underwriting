"""
FRED API client for CRE underwriting v4.

Provides live economic data for any US metro area:
  - Home Price Index (HPI)
  - Median household income
  - Unemployment rate
  - Population estimates

MSA mappings are curated for the CRE pipeline's target markets (NJ/PA/SC/NY).
"""

import os
import functools
from typing import Any, Dict, Optional

try:
    from fredapi import Fred
    HAS_FRED = True
except ImportError:
    HAS_FRED = False


@functools.lru_cache(maxsize=1)
def _get_fred():
    """Get cached FRED client. Reads FRED_API_KEY from environment."""
    if not HAS_FRED:
        raise ImportError("fredapi not installed. Run: uv pip install fredapi")
    key = os.environ.get("FRED_API_KEY", "")
    if not key:
        raise RuntimeError("FRED_API_KEY not set in environment")
    return Fred(api_key=key)


# --- MSA lookup table ---
# Maps city/state combos to FRED series IDs
# Series explanations:
#   ATNHPIUSXXXXXQ = All-Transactions HPI for MSA (quarterly)
#   MEHOINUSXXA672N = Median Household Income (annual)
#   XXUR = State Unemployment Rate (monthly)
#   XXPOP = State Population (annual)

MSA_MAP = {
    # NJ cities/municipalities -> NY-NJ MSA
    "succasunna_nj": "New York-Newark-Jersey City, NY-NJ-PA",
    "roxbury_township_nj": "New York-Newark-Jersey City, NY-NJ-PA",
    "fords_nj": "New York-Newark-Jersey City, NY-NJ-PA",
    "irvington_nj": "New York-Newark-Jersey City, NY-NJ-PA",
    "hoboken_nj": "New York-Newark-Jersey City, NY-NJ-PA",
    "short_hills_nj": "New York-Newark-Jersey City, NY-NJ-PA",
    "butler_nj": "New York-Newark-Jersey City, NY-NJ-PA",
    "passaic_nj": "New York-Newark-Jersey City, NY-NJ-PA",
    "west_deptford_nj": "Philadelphia-Camden-Wilmington, PA-NJ-DE-MD",
    "princeton_nj": "New York-Newark-Jersey City, NY-NJ-PA",
    "millburn_nj": "New York-Newark-Jersey City, NY-NJ-PA",
    "newark_nj": "New York-Newark-Jersey City, NY-NJ-PA",
    "jersey_city_nj": "New York-Newark-Jersey City, NY-NJ-PA",
    # SC
    "greenville_sc": "Greenville-Anderson, SC",
    # PA
    "philadelphia_pa": "Philadelphia-Camden-Wilmington, PA-NJ-DE-MD",
}

# Generic NJ fallback (any NJ city not in the map -> NY-NJ MSA)
_NJ_DEFAULT_MSA = "New York-Newark-Jersey City, NY-NJ-PA"
_SC_DEFAULT_MSA = "Greenville-Anderson, SC"
_STATE_DEFAULTS = {"NJ": _NJ_DEFAULT_MSA, "SC": _SC_DEFAULT_MSA}

# MSA → FRED series mapping
MSA_SERIES = {
    "New York-Newark-Jersey City, NY-NJ-PA": {
        "hpi": "ATNHPIUS35620Q",
        "income": "MEHOINUSNJA672N",
        "unemployment": "NJUR",
        "population": "NJPOP",
    },
    "Philadelphia-Camden-Wilmington, PA-NJ-DE-MD": {
        "hpi": "ATNHPIUS37980Q",
        "income": "MEHOINUSNJA672N",  # NJ state fallback
        "unemployment": "NJUR",
        "population": "NJPOP",
    },
    "Greenville-Anderson, SC": {
        "hpi": "ATNHPIUS24860Q",
        "income": "MEHOINUSSCA672N",
        "unemployment": "SCUR",
        "population": "SCPOP",
    },
}


def _normalize_city(city: str) -> str:
    """Normalize city name for MSA lookup."""
    return city.lower().replace(" ", "_").replace("-", "_")


def _lookup_msa(city: str, state: str) -> Optional[str]:
    """Find the MSA name for a city/state combo.

    Falls back to state-level default if city not found in map.
    """
    if not city and not state:
        return None
    key = "%s_%s" % (_normalize_city(city), state.lower())
    if key in MSA_MAP:
        return MSA_MAP[key]
    # Try state default
    return _STATE_DEFAULTS.get(state.upper())


def get_msa_economics(city: str, state: str) -> dict:
    """Fetch real economic indicators for a metro area.

    Returns:
        {
            "msa_name": str,
            "hpi_1yr_pct": float or None,
            "hpi_5yr_annualized_pct": float or None,
            "median_household_income": int or None,
            "unemployment_rate_pct": float or None,
            "population": int or None,
            "data_freshness": str,
            "source": str,
        }
    """
    if not HAS_FRED:
        return _empty_economics("fredapi not installed")

    try:
        fred = _get_fred()
    except (ImportError, RuntimeError) as e:
        return _empty_economics(str(e))

    msa = _lookup_msa(city, state)
    if not msa:
        return _empty_economics("MSA not found for %s, %s" % (city, state))

    series = MSA_SERIES.get(msa, {})
    result: Dict[str, Any] = {"msa_name": msa, "source": "FRED (St. Louis Fed)", "data_freshness": ""}
    data_dates = []

    # HPI
    if "hpi" in series:
        try:
            hpi = fred.get_series(series["hpi"])
            if len(hpi) >= 5:
                result["hpi_1yr_pct"] = round((hpi.iloc[-1] / hpi.iloc[-5] - 1) * 100, 1)
                data_dates.append("HPI %s" % hpi.index[-1].strftime("%Y-%m"))
            if len(hpi) >= 21:
                result["hpi_5yr_annualized_pct"] = round(
                    ((hpi.iloc[-1] / hpi.iloc[-21]) ** (1.0 / 5) - 1) * 100, 1
                )
        except Exception:
            pass

    # Income
    if "income" in series:
        try:
            income = fred.get_series(series["income"])
            if len(income) > 0:
                result["median_household_income"] = int(income.iloc[-1])
                data_dates.append("Income %s" % income.index[-1].strftime("%Y"))
        except Exception:
            pass

    # Unemployment
    if "unemployment" in series:
        try:
            unemp = fred.get_series(series["unemployment"])
            if len(unemp) > 0:
                result["unemployment_rate_pct"] = round(float(unemp.iloc[-1]), 1)
                data_dates.append("Unemp %s" % unemp.index[-1].strftime("%Y-%m"))
        except Exception:
            pass

    # Population
    if "population" in series:
        try:
            pop = fred.get_series(series["population"])
            if len(pop) > 0:
                result["population"] = int(pop.iloc[-1])
        except Exception:
            pass

    result["data_freshness"] = ", ".join(data_dates) if data_dates else "unknown"
    return result


def get_county_demographics(county: str, state: str) -> dict:
    """Get county-level demographics. Uses FRED state-level as fallback.

    Returns same structure as get_msa_economics, county-level where available.
    """
    # For now, use MSA-level data (county-level FRED series require more mapping)
    # This can be enhanced with Census ACS API in future
    return get_msa_economics("", state) if state else _empty_economics("no state")


def _empty_economics(reason: str = "") -> dict:
    return {
        "msa_name": "",
        "hpi_1yr_pct": None,
        "hpi_5yr_annualized_pct": None,
        "median_household_income": None,
        "unemployment_rate_pct": None,
        "population": None,
        "data_freshness": "",
        "source": reason,
    }
