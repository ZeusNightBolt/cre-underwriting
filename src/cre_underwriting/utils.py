"""
cre_underwriting.utils — Shared utilities for address parsing and data loading.

Consolidates address parsing logic that was duplicated across comps.py
and environmental.py. Single regex, single city-to-county mapping.
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict


# ── Address Parsing ──────────────────────────────────────────

_CITY_STATE_RE = re.compile(
    r"^.*?([A-Za-z\s.]+),\s*([A-Z]{2})\b", re.IGNORECASE)


def parse_city_state(address: str) -> tuple[Optional[str], Optional[str]]:
    """Extract (city, state) from an address string. Returns (None, None) on failure."""
    m = _CITY_STATE_RE.search(address)
    if m:
        return m.group(1).strip(), m.group(2).upper()
    # Fallback: look for ", ST" pattern anywhere
    m = re.search(r',\s*([A-Z]{2})\b', address)
    if m:
        state = m.group(1).upper()
        # Try to find city before the state
        city_m = re.search(r',\s*([^,]+),\s*' + state, address)
        if city_m:
            return city_m.group(1).strip(), state
    return None, None


def parse_address(address: str) -> Dict[str, str]:
    """Parse full address into {city, state, county} dict."""
    result = {"city": "", "state": "", "county": ""}
    city, state = parse_city_state(address)
    if city:
        result["city"] = city
    if state:
        result["state"] = state
    result["county"] = city_to_county(city or "", state or "NJ")
    return result


def city_to_county(city: str, state: str) -> str:
    """Map city name to county using known NJ/PA municipal data."""
    NJ_CITIES = {
        "newark": "Essex", "jersey city": "Hudson", "paterson": "Passaic",
        "elizabeth": "Union", "edison": "Middlesex", "woodbridge": "Middlesex",
        "fords": "Middlesex", "trenton": "Mercer", "camden": "Camden",
        "clifton": "Passaic", "passaic": "Passaic", "hoboken": "Hudson",
        "union city": "Hudson", "bayonne": "Hudson", "east orange": "Essex",
        "irvington": "Essex", "vineland": "Cumberland", "new brunswick": "Middlesex",
        "perth amboy": "Middlesex", "plainfield": "Union", "bloomfield": "Essex",
        "hackensack": "Bergen", "linden": "Union", "kearny": "Hudson",
        "atlantic city": "Atlantic", "gallowy": "Atlantic",
        "succasunna": "Morris", "roxbury": "Morris", "denville": "Morris",
        "parsippany": "Morris", "mount olive": "Morris", "randolph": "Morris",
        "morristown": "Morris", "flanders": "Morris",
    }
    PA_CITIES = {
        "philadelphia": "Philadelphia", "pittsburgh": "Allegheny",
        "allentown": "Lehigh", "easton": "Northampton", "bethlehem": "Northampton",
        "reading": "Berks", "scranton": "Lackawanna", "erie": "Erie",
        "stroudsburg": "Monroe", "doylestown": "Bucks", "norristown": "Montgomery",
    }
    city_lower = city.lower().strip()
    if state.upper() == "NJ":
        return NJ_CITIES.get(city_lower, "")
    elif state.upper() == "PA":
        return PA_CITIES.get(city_lower, "")
    return ""


def city_slug(city: str) -> str:
    """Convert city name to URL-friendly slug (e.g., 'New York' → 'new-york')."""
    return re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")


# ── Data Loading ─────────────────────────────────────────────

def load_json(path: str) -> dict:
    """Load a JSON file, returning empty dict on failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def resolve_fixture_path(filename: str) -> Path:
    """Resolve a test fixture path relative to the package."""
    return Path(__file__).parent.parent.parent / "tests" / "fixtures" / filename
