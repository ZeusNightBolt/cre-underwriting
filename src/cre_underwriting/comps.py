"""
cre_underwriting.comps — Comparable Sales Analysis Engine.

Phase 1: Zillow sold listings (public data scraping).
Phase 2: LoopNet sold listings (Firefox BiDi, stubbed).
Phase 3: NJ county assessor records (njactb.org, stubbed).

Target markets: NJ/PA. Target: 3-5 comps.

Usage:
    from cre_underwriting.comps import find_comps, price_per_sf
    result = find_comps("123 Main St, Princeton, NJ 08540", property_type="Retail")
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from statistics import median, mean
from typing import Any, Optional
from urllib.parse import quote_plus

from .models import Comp
from .utils import parse_city_state, city_slug

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

logger = logging.getLogger("cre_comps")

# ── Zillow Scraping (Phase 1) ────────────────────────────────

ZILLOW_SOLD_URL = "https://www.zillow.com/{city}-{state}/sold/"
ZILLOW_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64; rv:150.0) "
                   "Gecko/20100101 Firefox/150.0"),
}


def _build_zillow_url(address: str) -> Optional[str]:
    city, state = parse_city_state(address)
    if not city or not state:
        return None
    return ZILLOW_SOLD_URL.format(city=city_slug(city), state=state.lower())


def _fetch_zillow_html(url: str, timeout: int = 15) -> Optional[str]:
    if not HAS_REQUESTS:
        return None
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=1.0, status_forcelist=[429, 503])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(ZILLOW_HEADERS)
    try:
        resp = session.get(url, timeout=timeout)
        if resp.status_code == 403:
            logger.warning("Zillow 403 — blocked. Try Firefox BiDi or proxy.")
            return None
        if resp.status_code != 200:
            return None
        return resp.text
    except requests.RequestException:
        return None
    finally:
        session.close()


def _extract_next_data(html: str) -> Optional[dict]:
    if not HAS_BS4:
        return None
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if script is None:
        return None
    try:
        return json.loads(script.string)
    except json.JSONDecodeError:
        return None


def _parse_zillow_comps(data: dict) -> list[Comp]:
    comps = []
    try:
        search_state = (data.get("props", {}).get("pageProps", {})
                       .get("searchPageState", {}))
    except (AttributeError, KeyError):
        return comps
    cat = search_state.get("cat1", {})
    listings = cat.get("searchResults", {}).get("listResults", [])
    if not listings:
        return comps
    for item in listings:
        try:
            comps.append(Comp(
                source="zillow",
                address=item.get("address", ""),
                sale_price=_clean_price(item.get("price")),
                sf=_clean_sf(item),
                property_type=item.get("propertyType", ""),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return comps


def _clean_price(raw: Any) -> Optional[float]:
    if raw is None: return None
    if isinstance(raw, (int, float)): return float(raw)
    cleaned = str(raw).replace("$", "").replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*([KM]?)", cleaned, re.IGNORECASE)
    if not m: return None
    value = float(m.group(1))
    suffix = m.group(2).upper()
    if suffix == "K": value *= 1_000
    elif suffix == "M": value *= 1_000_000
    return value


def _clean_sf(item: dict) -> Optional[float]:
    sf = item.get("area")
    if sf is not None:
        try: return float(str(sf).replace(",", ""))
        except (ValueError, TypeError): pass
    vd = item.get("variableData", {}).get("text", "")
    m = re.search(r"([\d,]+)\s*sq", vd, re.IGNORECASE)
    if m:
        try: return float(m.group(1).replace(",", ""))
        except ValueError: pass
    return None


def _zillow_comps(address: str, property_type: Optional[str] = None,
                  proxy: str = None) -> list[Comp]:
    """Fetch comps from Zillow. Pass proxy='http://host:port' to bypass 403."""
    url = _build_zillow_url(address)
    if url is None: return []

    # Try proxy first if available
    if proxy:
        html = _fetch_with_proxy(url, proxy)
        if html:
            data = _extract_next_data(html)
            if data:
                return _tag_comps(_parse_zillow_comps(data), property_type)

    html = _fetch_zillow_html(url)
    if html is None: return []
    data = _extract_next_data(html)
    if data is None: return []
    comps = _parse_zillow_comps(data)
    if property_type:
        for c in comps:
            if not c.property_type:
                c.property_type = property_type
    return comps


def _tag_comps(comps: list[Comp], property_type: Optional[str] = None) -> list[Comp]:
    """Tag comps with property_type if not already set."""
    if property_type:
        for c in comps:
            if not c.property_type:
                c.property_type = property_type
    return comps


def _fetch_with_proxy(url: str, proxy: str, timeout: int = 15) -> Optional[str]:
    """Fetch URL through a proxy."""
    if not HAS_REQUESTS: return None
    try:
        r = requests.get(url, headers=ZILLOW_HEADERS,
                        proxies={"http": proxy, "https": proxy}, timeout=timeout)
        return r.text if r.status_code == 200 else None
    except Exception:
        return None


# ── Stubs ────────────────────────────────────────────────────

def _loopnet_comps(address: str, property_type: Optional[str] = None) -> list[Comp]:
    """
    Fetch comparable sales from LoopNet via Firefox BiDi.

    Uses the hardened BidiSession from scraping.py with retry and
    exponential backoff. Falls back gracefully if BiDi is unavailable.

    Scrapes LoopNet's sold listings search for the property's city/state
    and parses sold comparables from the search results.
    """
    city, state = parse_city_state(address)
    if not city or not state:
        return []

    # Build LoopNet sold search URL
    city_slug = city.lower().replace(" ", "-")
    state_lower = state.lower()
    sold_url = (
        f"https://www.loopnet.com/search/commercial-real-estate/"
        f"{city_slug}-{state_lower}/for-sale/"
    )

    try:
        from .scraping import BidiSession
    except ImportError:
        return []  # BiDi not available

    try:
        with BidiSession(port=9222, max_retries=1) as session:
            html = session.navigate_and_extract(sold_url, dwell_min=5, dwell_max=10)
    except Exception:
        return []

    if not html:
        return []

    # Parse LoopNet sold listings
    return _parse_loopnet_sold_listings(html, property_type)


def _parse_loopnet_sold_listings(html: str,
                                  property_type: Optional[str] = None) -> list[Comp]:
    """Parse sold listing data from LoopNet search results HTML."""
    comps = []
    if not HAS_BS4:
        return comps

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    # LoopNet listing cards have data-gtm-* attributes
    placards = soup.find_all("article", class_="placard")
    if not placards:
        placards = soup.find_all("div", attrs={"data-gtm-listing-id": True})

    for card in placards[:10]:
        try:
            # Extract listing ID
            listing_id = card.get("data-gtm-listing-id", "")
            if not listing_id:
                listing_id = card.get("data-propertyid", "")

            # Extract address
            addr_el = card.find("a", class_="profile-grid-header")
            if not addr_el:
                addr_el = card.find("a", href=lambda h: h and "/listing/" in h)
            address_text = addr_el.get_text(strip=True) if addr_el else ""

            # Extract price
            price_el = card.find("span", class_="price")
            if not price_el:
                price_el = card.find(string=lambda t: "$" in t if t else False)
            price = _clean_price(price_el.get_text() if hasattr(price_el, 'get_text') else str(price_el)) if price_el else None

            # Extract SF
            sf_el = card.find("span", string=lambda t: "SF" in t if t else False)
            sf = _clean_sf({"variableData": {"text": sf_el.strip()}}) if sf_el else None

            comps.append(Comp(
                source="loopnet",
                address=address_text,
                sale_price=price,
                sf=sf,
                property_type=property_type,
            ))
        except Exception:
            continue

    return comps


def _njactb_comps(address: str, property_type: Optional[str] = None) -> list[Comp]:
    """NJ ACTB assessor records — stubbed for v1.0.0."""
    return []


# ── Main API ─────────────────────────────────────────────────

def find_comps(address: str, property_type: Optional[str] = None,
               radius_miles: float = 2.0) -> dict:
    """Find comparable sales for a CRE property.

    Returns dict with 'comps' (list[Comp]) and 'summary' (aggregated stats).
    """
    all_comps: list[Comp] = []

    # Phase 1: Zillow
    try:
        all_comps.extend(_zillow_comps(address, property_type))
    except Exception as exc:
        logger.warning("Zillow comps failed: %s", exc)

    # Phase 2: LoopNet (stub)
    try:
        all_comps.extend(_loopnet_comps(address, property_type))
    except Exception as exc:
        logger.warning("LoopNet comps failed: %s", exc)

    # Phase 3: NJ ACTB (stub)
    try:
        all_comps.extend(_njactb_comps(address, property_type))
    except Exception as exc:
        logger.warning("NJ ACTB comps failed: %s", exc)

    # Compute summary
    prices = [c.sale_price for c in all_comps if c.sale_price]
    psf_vals = [c.price_per_sf for c in all_comps if c.price_per_sf]
    source_statuses = {"zillow": False, "loopnet": False, "njactb": False}

    # Track which sources actually contributed results
    for c in all_comps:
        if c.source in source_statuses:
            source_statuses[c.source] = True

    failed_sources = [s for s, ok in source_statuses.items() if not ok]
    data_quality_warning = None
    if not all_comps:
        if len(failed_sources) == 3:
            data_quality_warning = (
                "ALL comp sources returned 0 results. Zillow likely blocked (403). "
                "LoopNet and NJ ACTB are stubs (not yet implemented). "
                "Consider manual comp research or Firefox BiDi for LoopNet."
            )
        else:
            data_quality_warning = (
                f"No comps found. Failed sources: {', '.join(failed_sources)}. "
                f"Zillow may be blocking automated requests."
            )

    summary = {
        "count": len(all_comps),
        "median_price": median(prices) if prices else None,
        "price_range": (min(prices), max(prices)) if prices else None,
        "price_per_sf_range": (min(psf_vals), max(psf_vals)) if psf_vals else None,
        "median_price_per_sf": median(psf_vals) if psf_vals else None,
        "mean_price_per_sf": mean(psf_vals) if psf_vals else None,
        "source_status": source_statuses,
        "data_quality_warning": data_quality_warning,
    }

    return {"comps": [asdict(c) for c in all_comps], "summary": summary}


def price_per_sf(comps: list[Comp]) -> dict:
    """Compute price-per-SF statistics from a list of comps."""
    vals = [c.price_per_sf for c in comps if c.price_per_sf]
    if not vals:
        return {"median": None, "mean": None, "min": None, "max": None}
    return {"median": median(vals), "mean": mean(vals),
            "min": min(vals), "max": max(vals)}
