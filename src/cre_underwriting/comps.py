"""
cre_underwriting.comps — Comparable Sales Analysis Engine.

Primary: LoopNet Firefox BiDi scraping (live search results).
Fallback: NJ county assessor records (stubbed).

Target markets: NJ/PA. Target: 3-5 comps.

Usage:
    from cre_underwriting.comps import find_comps, price_per_sf
    result = find_comps("123 Main St, Princeton, NJ 08540", property_type="Retail")
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict
from statistics import median, mean
from typing import Any, Optional

from .models import Comp
from .utils import parse_city_state, city_slug

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

logger = logging.getLogger("cre_comps")


# ── LoopNet Firefox BiDi Scraping (Primary) ──────────────────

LOOPNET_SEARCH_URL = (
    "https://www.loopnet.com/search/commercial-real-estate/"
    "{city_slug}-{state}/for-sale/"
)

# Firefox BiDi port (shared with loopnet_utils.py)
FF_BIDI_PORT = 9222


def _ensure_firefox_bidi(port: int = FF_BIDI_PORT) -> bool:
    """Ensure Firefox is running with remote debugging on the given port."""
    import subprocess
    try:
        # Check if port is already alive
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(('127.0.0.1', port))
        s.close()
        if result == 0:
            return True
    except Exception:
        pass

    # Try to start Firefox
    try:
        subprocess.Popen(
            ['/usr/lib/firefox/firefox', '--remote-debugging-port', str(port),
             '--no-remote', '--new-instance', '--headless'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # Wait for port to come alive
        for _ in range(15):
            time.sleep(1)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    s.close()
                    return True
                s.close()
            except Exception:
                pass
    except Exception:
        pass
    return False


def _loopnet_comps(address: str, property_type: Optional[str] = None,
                   target_price: float = 0) -> list[Comp]:
    """
    Fetch comparable properties from LoopNet via Firefox BiDi.

    Searches LoopNet for-sale listings in the property's city/state,
    then extracts placard data (price, SF, property type) from results.

    Falls back gracefully if BiDi is unavailable or fails.
    """
    city, state = parse_city_state(address)
    if not city or not state:
        return []

    city_s = city.lower().replace(" ", "-")
    state_s = state.lower()
    search_url = LOOPNET_SEARCH_URL.format(city_slug=city_s, state=state_s)

    # Try Selenium BiDi connection
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.firefox.options import Options
    except ImportError:
        logger.warning("Selenium not available for LoopNet comps")
        return []

    if not _ensure_firefox_bidi():
        logger.warning("Firefox BiDi not available for LoopNet comps")
        return []

    driver = None
    try:
        opts = Options()
        opts.debugger_address = f"127.0.0.1:{FF_BIDI_PORT}"
        opts.add_argument("--headless")
        driver = webdriver.Firefox(options=opts)
        driver.set_page_load_timeout(30)

        driver.get(search_url)
        time.sleep(5)  # Let page load

        # Apply property-type filter if specified
        if property_type:
            try:
                _apply_property_type_filter(driver, property_type)
                time.sleep(3)
            except Exception:
                pass  # Filter optional — continue with unfiltered results

        # Extract placards
        return _extract_loopnet_placards(driver, property_type, city, target_price)

    except Exception as exc:
        logger.warning("LoopNet BiDi comps failed: %s", exc)
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def _apply_property_type_filter(driver, property_type: str):
    """Click the property-type filter on LoopNet search results."""
    from selenium.webdriver.common.by import By

    ptype_lower = property_type.lower()
    type_map = {
        "retail": "Retail",
        "office": "Office",
        "industrial": "Industrial",
        "multifamily": "Multifamily",
        "land": "Land",
    }
    target = type_map.get(ptype_lower, property_type)

    # Find and click the property type filter button
    try:
        buttons = driver.find_elements(By.CSS_SELECTOR, '[data-testid="property-type-filter"] button, .filter-group button')
        for btn in buttons:
            if target.lower() in btn.text.lower():
                btn.click()
                return
    except Exception:
        pass


def _extract_loopnet_placards(driver, property_type: Optional[str] = None,
                              target_city: str = "", target_price: float = 0) -> list[Comp]:
    """Extract listing data from a LoopNet search results page.

    Falls back to text-pattern extraction when HTML selectors fail
    (LoopNet changes their DOM structure frequently).
    """
    from selenium.webdriver.common.by import By

    comps = []
    
    # Method 1: Try standard placard selectors
    try:
        articles = driver.find_elements(By.CSS_SELECTOR, "article[data-listingid]")
        if not articles:
            articles = driver.find_elements(By.CSS_SELECTOR, "[data-listingid]")
        if not articles:
            articles = driver.find_elements(By.CSS_SELECTOR, "a[data-listingid]")
        
        if articles:
            for article in articles[:10]:
                try:
                    comp = _parse_placard_selenium(article, property_type)
                    if comp:
                        comps.append(comp)
                except Exception:
                    continue
            if comps:
                return comps
    except Exception:
        pass
    
    # Method 2: Text-based extraction (reliable fallback)
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        comps = _extract_comps_from_text(body_text, property_type, target_city, target_price)
    except Exception:
        pass
    
    return comps


def _extract_comps_from_text(page_text: str, property_type: Optional[str] = None,
                             target_city: str = "", target_price: float = 0) -> list[Comp]:
    """Extract listing data from LoopNet page text using regex patterns.

    Each LoopNet listing card in the page text typically follows this pattern:
      Title / Address line
      SF + Property Type line (e.g., "21,780 SF Retail")
      Price line (e.g., "$6,000,000")
    """
    comps = []
    
    # Split page into listing blocks using price patterns as boundaries
    # Each listing has a $ price on its own line or inline
    price_lines = list(re.finditer(r'\$([\d,]+)([KM]?)', page_text))
    if len(price_lines) < 2:
        return comps
    
    for i, pm in enumerate(price_lines):
        try:
            # Get the text block around this price
            start = max(0, pm.start() - 300)
            end = min(len(page_text), pm.end() + 100)
            # Don't overlap with next price
            if i + 1 < len(price_lines):
                end = min(end, price_lines[i+1].start())
            block = page_text[start:end]
            
            price_str = pm.group(1).replace(',', '')
            price = float(price_str)
            if pm.group(2) == 'K':
                price *= 1000
            elif pm.group(2) == 'M':
                price *= 1_000_000
            
            # Extract SF from nearby text
            sf_match = re.search(r'([\d,]+)\s*SF', block)
            sf = float(sf_match.group(1).replace(',', '')) if sf_match else None
            
            # Skip obviously wrong prices
            if price < 50000 or price > 100_000_000:
                continue
            
            # Extract address/title - look for text before the price
            before = page_text[max(0, start-200):pm.start()]
            lines = [l.strip() for l in before.split('\n') if l.strip() and len(l.strip()) > 3]
            # Skip SF lines, cap rate lines, filter headers
            skip_patterns = ['SF ', 'Cap Rate', 'For Sale', 'For Lease', 'Property Types',
                           'Price', 'Size', 'All Filters', 'Results', 'Sort', 'Sign In']
            address = ""
            for line in reversed(lines):
                if not any(s in line for s in skip_patterns) and not re.match(r'[\d,]+ SF', line):
                    address = line[:80]
                    break
            
            # Detect property type
            detected_type = property_type or _detect_property_type(block)
            
            comps.append(Comp(
                source="loopnet",
                address=address or "LoopNet Listing",
                sale_price=price,
                sf=sf,
                property_type=detected_type,
            ))
        except Exception:
            continue
    
    # Filter by target price range if provided (±50%)
    if target_price > 0 and len(comps) > 5:
        lo, hi = target_price * 0.5, target_price * 1.5
        filtered = [c for c in comps if c.sale_price and lo <= c.sale_price <= hi]
        if len(filtered) >= 3:
            comps = filtered
    
    # Filter by city if provided
    if target_city and len(comps) > 5:
        city_lower = target_city.lower()
        city_filtered = [c for c in comps if c.address and city_lower in c.address.lower()]
        if len(city_filtered) >= 3:
            comps = city_filtered
    
    return comps[:10]


def _parse_placard_selenium(article_element, property_type: Optional[str] = None) -> Optional[Comp]:
    """Parse a single LoopNet placard using live Selenium element access."""
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import NoSuchElementException

    try:
        listing_id = article_element.get_attribute("data-listingid") or ""

        # Price — look for elements starting with $
        price = None
        try:
            for el in article_element.find_elements(By.CSS_SELECTOR, "span, div"):
                text = el.text.strip()
                if text.startswith("$"):
                    price = _parse_price(text)
                    break
        except Exception:
            pass

        # Address/Title from first link
        address = ""
        try:
            link = article_element.find_element(By.TAG_NAME, "a")
            address = link.text.strip()
        except NoSuchElementException:
            pass

        # Square footage from article text
        sf = None
        full_text = ""
        try:
            full_text = article_element.text
        except Exception:
            pass
        sf = _extract_sf_from_text(full_text)

        # Cap rate from text
        cap_rate = _extract_cap_rate_from_text(full_text)

        # Property type detection from text
        detected_type = property_type
        if not detected_type:
            detected_type = _detect_property_type(full_text)

        if not price and not sf:
            return None  # Nothing useful extracted

        return Comp(
            source="loopnet",
            address=address or f"Listing #{listing_id}",
            sale_price=price,
            sf=sf,
            property_type=detected_type,
        )
    except Exception:
        return None


def _parse_price(text: str) -> Optional[float]:
    """Parse a price string like '$1,200,000' or '$450K' to float."""
    if not text:
        return None
    cleaned = text.replace("$", "").replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*([KM]?)$", cleaned, re.IGNORECASE)
    if not m:
        return None
    value = float(m.group(1))
    suffix = m.group(2).upper()
    if suffix == "K":
        value *= 1_000
    elif suffix == "M":
        value *= 1_000_000
    return value


def _extract_sf_from_text(text: str) -> Optional[float]:
    """Extract square footage from listing text."""
    if not text:
        return None
    m = re.search(r"(\d{1,3}(?:,\d{3})*)\s*SF", text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _extract_cap_rate_from_text(text: str) -> Optional[float]:
    """Extract cap rate percentage from listing text."""
    if not text:
        return None
    m = re.search(r"(\d+\.?\d*)%\s*Cap", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def _detect_property_type(text: str) -> str:
    """Detect property type from text content."""
    if not text:
        return ""
    t = text.lower()
    if "retail" in t:
        return "Retail"
    if "office" in t:
        return "Office"
    if "industrial" in t or "warehouse" in t:
        return "Industrial"
    if "multifamily" in t or "apartment" in t:
        return "Multifamily"
    if "land" in t:
        return "Land"
    return ""


# ── NJ ACTB (Stub) ──────────────────────────────────────────

def _njactb_comps(address: str, property_type: Optional[str] = None) -> list[Comp]:
    """NJ ACTB assessor records — stubbed for v1.0.0."""
    return []


# ── Main API ─────────────────────────────────────────────────

def find_comps(address: str, property_type: Optional[str] = None,
               radius_miles: float = 2.0) -> dict:
    """Find comparable sales for a CRE property.

    Primary source: LoopNet via Firefox BiDi (scrapes active for-sale listings
    in the same city to establish market price/SF benchmarks).

    Returns dict with 'comps' (list[Comp]) and 'summary' (aggregated stats).
    """
    all_comps: list[Comp] = []

    # Primary: LoopNet Firefox BiDi
    try:
        all_comps.extend(_loopnet_comps(address, property_type))
    except Exception as exc:
        logger.warning("LoopNet comps failed: %s", exc)

    # Fallback: NJ ACTB
    try:
        all_comps.extend(_njactb_comps(address, property_type))
    except Exception as exc:
        logger.warning("NJ ACTB comps failed: %s", exc)

    # Compute summary
    prices = [c.sale_price for c in all_comps if c.sale_price]
    psf_vals = [c.price_per_sf for c in all_comps if c.price_per_sf]
    source_statuses = {"loopnet": False, "njactb": False}

    # Track which sources actually contributed results
    for c in all_comps:
        if c.source in source_statuses:
            source_statuses[c.source] = True

    failed_sources = [s for s, ok in source_statuses.items() if not ok]
    data_quality_warning = None
    if not all_comps:
        if len(failed_sources) == len(source_statuses):
            data_quality_warning = (
                "No comps found from any source. LoopNet search returned no results. "
                "Consider manual comp research or widening search radius."
            )
        else:
            data_quality_warning = (
                f"No comps found. Failed sources: {', '.join(failed_sources)}."
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
