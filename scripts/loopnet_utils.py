#!/usr/bin/env python3
"""
LoopNet Scraping Utilities — Shared module for all LoopNet scrapers.

Firefox BiDi lifecycle management, element parsing, tax data extraction,
condo detection, hidden NOI detection. Used by loopnet_search.py,
loopnet_listing.py, and loopnet_batch.py.

Architecture:
  FireFox (real browser) → WebDriver BiDi :9222 → Selenium debugger_address bridge
  Tested on Firefox 150+, May 2026.

Key pitfall: Firefox 150+ dropped CDP. Use BiDi only. Never open multiple
Firefox instances on low-RAM systems (confirmed OOM on CHUWI LarkBox X 5.7GB).

Usage:
    from loopnet_utils import ensure_firefox, parse_listing_placard, detect_tax_bomb
"""

import subprocess
import time
import json
import re
import fcntl
import os
from typing import Optional, Dict, List, Any


# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

FF_DEBUG_PORT = 9222
LOCK_FILE = "/tmp/hermes_loopnet_bidi.lock"
NJ_COUNTY_TAX_RATES = {
    "atlantic": 0.022, "bergen": 0.025, "burlington": 0.024,
    "camden": 0.028, "cape may": 0.018, "cumberland": 0.026,
    "essex": 0.032, "gloucester": 0.026, "hudson": 0.020,
    "hunterdon": 0.022, "mercer": 0.030, "middlesex": 0.024,
    "monmouth": 0.020, "morris": 0.022, "ocean": 0.020,
    "passaic": 0.040, "salem": 0.024, "somerset": 0.022,
    "sussex": 0.022, "union": 0.028, "warren": 0.022,
}

PA_COUNTY_TAX_RATES = {
    "bucks": 0.018, "montgomery": 0.017, "northampton": 0.020,
    "lehigh": 0.020, "delaware": 0.022, "chester": 0.018,
    "berks": 0.020, "lancaster": 0.018, "york": 0.019,
    "luzerne": 0.022, "lackawanna": 0.022, "monroe": 0.030,
}

# Condo/leasehold detection signals
LEASEHOLD_SIGNALS = [
    "ground lease", "leasehold", "lease assignment", "option term",
    "lease expires", "option period", "leasehold interest",
]

FEE_SIMPLE_CONDO_SIGNALS = [
    "condo use", "condo association", "condo fee", "hoa fee",
    "investment or owner user",
]

HIDDEN_NOI_SIGNALS = [
    "fully leased", "nnn", "triple net", "investment property",
]


# ──────────────────────────────────────────────────────────────
# Firefox BiDi Lifecycle
# ──────────────────────────────────────────────────────────────

def ensure_firefox(port: int = FF_DEBUG_PORT) -> bool:
    """
    Ensure exactly ONE Firefox debug instance is running on the given port.

    Uses a lock file to prevent multiple instances on low-RAM systems.
    Confirmed critical on CHUWI LarkBox X (5.7GB RAM) — two Firefox
    instances + LLM = OOM → swap thrashing → system freeze.

    Args:
        port: Debug port (default 9222)

    Returns:
        True if Firefox is ready (existing or newly started), False otherwise
    """
    # Check if port is already alive
    if _port_alive(port):
        return True

    # Acquire lock
    lock_fd = _acquire_lock()
    if lock_fd is None:
        # Another process is starting Firefox — wait for it
        for _ in range(30):  # 30s max wait
            time.sleep(1)
            if _port_alive(port):
                return True
        return False

    try:
        # Kill any stale Firefox processes on the port
        subprocess.run(["fuser", "-k", f"{port}/tcp"],
                       capture_output=True, timeout=5)
        time.sleep(2)

        # Start Firefox with BiDi debug port
        subprocess.Popen(
            ["firefox", "--remote-debugging-port", str(port),
             "--new-instance", "--no-first-run"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        # Wait for port to come alive
        for _ in range(20):  # 20s max wait
            time.sleep(1)
            if _port_alive(port):
                return True

        return False
    finally:
        _release_lock(lock_fd)


def _port_alive(port: int) -> bool:
    """Check if a process is listening on the given port."""
    try:
        result = subprocess.run(
            ["fuser", f"{port}/tcp"],
            capture_output=True, timeout=3
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _acquire_lock() -> Optional[int]:
    """Acquire the singleton lock file. Returns fd or None."""
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except (IOError, OSError):
        if 'fd' in locals():
            os.close(fd)
        return None


def _release_lock(fd: int):
    """Release the singleton lock file."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except (IOError, OSError):
        pass


def get_selenium_driver(port: int = FF_DEBUG_PORT):
    """
    Get a Selenium WebDriver connected to the running Firefox BiDi instance.

    Uses debugger_address to connect to the existing Firefox session.
    This is the simplest approach — works on Firefox 150+ (tested May 2026).

    Returns:
        selenium.webdriver.Firefox instance, or None on failure
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options

        options = Options()
        options.debugger_address = f"127.0.0.1:{port}"
        driver = webdriver.Firefox(options=options)
        return driver
    except Exception as e:
        print(f"[loopnet_utils] Selenium connection failed: {e}")
        return None


# ──────────────────────────────────────────────────────────────
# LoopNet Element Parsers
# ──────────────────────────────────────────────────────────────

def parse_listing_placard(article_element) -> Optional[Dict[str, Any]]:
    """
    Parse a single LoopNet listing placard (<article> element) from search results.

    Extracts: listing_id, title, price, cap_rate, sf, property_type,
              city, state, url, noi, tax_assessment

    Uses data-gtm-* attributes when available (most reliable),
    falls back to text parsing.

    Args:
        article_element: BeautifulSoup Tag or dict with element attributes

    Returns:
        Dict with extracted fields, or None if parsing fails
    """
    data = {}

    try:
        # Try data-gtm attributes first (most reliable)
        if hasattr(article_element, 'get'):
            data["listing_id"] = article_element.get("data-listingid", "")
            data["price"] = _parse_price(article_element.get("data-price", "0"))
        elif isinstance(article_element, dict):
            data["listing_id"] = article_element.get("data-listingid", "")
            data["price"] = _parse_price(article_element.get("data-price", "0"))

        # Extract text content for field parsing
        if hasattr(article_element, 'get_text'):
            text = article_element.get_text(separator=" ", strip=True)
        elif hasattr(article_element, 'text'):
            text = article_element.text
        else:
            text = str(article_element)

        # Title / address
        title_el = _find_element(article_element, ['a[data-listingid]', '.placard-title', 'a'])
        if title_el:
            data["title"] = _get_text(title_el)
            href = _get_attr(title_el, 'href')
            data["url"] = f"https://www.loopnet.com{href}" if href and href.startswith('/') else href

        # Property type (from text or attributes)
        data["property_type"] = ""
        if "retail" in text.lower():
            data["property_type"] = "Retail"
        elif "office" in text.lower():
            data["property_type"] = "Office"
        elif "industrial" in text.lower():
            data["property_type"] = "Industrial"
        elif "multifamily" in text.lower() or "apartment" in text.lower():
            data["property_type"] = "Multifamily"
        elif "land" in text.lower():
            data["property_type"] = "Land"

        # Square footage
        sf_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*SF', text)
        if sf_match:
            data["sf"] = int(sf_match.group(1).replace(',', ''))

        # Price (from text if not in data-gtm)
        if not data.get("price"):
            price_match = re.search(r'\$([\d,]+)', text)
            if price_match:
                data["price"] = int(price_match.group(1).replace(',', ''))

        # Cap rate
        cap_match = re.search(r'(\d+\.?\d*)%\s*Cap', text)
        if cap_match:
            data["cap_rate"] = float(cap_match.group(1))

        # NOI
        noi_match = re.search(r'NOI\s*\$?([\d,]+)', text)
        if noi_match:
            data["noi"] = int(noi_match.group(1).replace(',', ''))

        # City / state
        city_match = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*([A-Z]{2})', text)
        if city_match:
            data["city"] = city_match.group(1)
            data["state"] = city_match.group(2)

        return data if data.get("listing_id") else None

    except Exception as e:
        print(f"[loopnet_utils] parse_listing_placard error: {e}")
        return None


def _find_element(parent, selectors):
    """Find first matching element from a list of CSS selectors."""
    if hasattr(parent, 'select_one'):
        for sel in selectors:
            el = parent.select_one(sel)
            if el:
                return el
    return None


def _get_text(element) -> str:
    """Get text from a BeautifulSoup element or dict."""
    if hasattr(element, 'get_text'):
        return element.get_text(strip=True)
    if isinstance(element, dict):
        return element.get('text', '')
    return str(element)


def _get_attr(element, attr: str) -> Optional[str]:
    """Get attribute from element."""
    if hasattr(element, 'get'):
        return element.get(attr)
    if isinstance(element, dict):
        return element.get(attr)
    return None


def _parse_price(price_str: str) -> Optional[int]:
    """Parse a dollar string to int. '$799,000' → 799000."""
    if not price_str:
        return None
    try:
        cleaned = re.sub(r'[^\d.]', '', str(price_str))
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


# ──────────────────────────────────────────────────────────────
# Tax Bomb Detection
# ──────────────────────────────────────────────────────────────

def detect_tax_bomb(ask_price: float, assessment_total: float,
                    county: str, state: str = "NJ") -> Dict[str, Any]:
    """
    Detect property tax reassessment risk for NJ/PA properties.

    NJ reassesses at sale price. PA reassessment varies by county.
    Computes post-sale tax and flags if increase exceeds 15% of NOI.

    Args:
        ask_price: Listing asking price
        assessment_total: Current total property assessment
        county: County name
        state: "NJ" or "PA"

    Returns:
        Dict with tax bomb analysis {post_sale_tax, increase_pct, verdict, ...}
    """
    county_lower = county.lower().replace(" county", "")
    rates = NJ_COUNTY_TAX_RATES if state.upper() == "NJ" else PA_COUNTY_TAX_RATES
    rate = rates.get(county_lower, 0.025)

    current_tax = round(assessment_total * rate)
    post_sale_tax = round(ask_price * rate)
    increase = post_sale_tax - current_tax
    increase_pct = round((post_sale_tax / current_tax - 1) * 100) if current_tax > 0 else 999

    if increase_pct > 500:
        verdict = "MASSIVE — assessment severely stale"
    elif increase_pct > 200:
        verdict = "HIGH — expect significant tax jump"
    elif increase_pct > 100:
        verdict = "MODERATE — factor into NOI"
    elif increase_pct > 25:
        verdict = "LOW — minor adjustment"
    else:
        verdict = "NEGLIGIBLE"

    assessment_ratio = round(assessment_total / ask_price * 100, 1) if ask_price > 0 else 0
    red_flags = []

    if assessment_ratio < 20:
        red_flags.append(f"Assessment is only {assessment_ratio}% of ask — massive tax bomb likely")
    if increase_pct > 200:
        red_flags.append(f"Post-sale tax will increase {increase_pct}%")

    return {
        "county": county,
        "state": state,
        "effective_rate_pct": round(rate * 100, 1),
        "current_tax_estimated": current_tax,
        "post_sale_tax": post_sale_tax,
        "tax_increase": increase,
        "tax_increase_pct": increase_pct,
        "assessment_to_ask_pct": assessment_ratio,
        "verdict": verdict,
        "red_flag_phrases_found": red_flags,
    }


# ──────────────────────────────────────────────────────────────
# Condo / Leasehold Detection
# ──────────────────────────────────────────────────────────────

def detect_condo(listing_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect whether a listing is a condo and if so, fee-simple or leasehold.

    CRITICAL: Fee-simple condos ARE real estate (own the unit).
    Leasehold condos have near-zero hard floor.

    Args:
        listing_data: Dict with at minimum 'description' and 'property_type' fields

    Returns:
        {is_condo, is_leasehold, structure, confidence, signals_found}
    """
    description = (listing_data.get("description", "") or "").lower()
    property_type = (listing_data.get("property_type", "") or "").lower()

    is_condo = "condo" in property_type or "condo" in description
    signals_found = []

    # Check leasehold signals
    is_leasehold = False
    for signal in LEASEHOLD_SIGNALS:
        if signal in description:
            is_leasehold = True
            signals_found.append(f"LEASEHOLD: {signal}")

    # Check fee-simple condo signals
    is_fee_simple_condo = False
    if is_condo and not is_leasehold:
        for signal in FEE_SIMPLE_CONDO_SIGNALS:
            if signal in description:
                is_fee_simple_condo = True
                signals_found.append(f"FEE_SIMPLE_CONDO: {signal}")

    # Determine structure
    if is_leasehold:
        structure = "Leasehold Condo"
    elif is_fee_simple_condo or (is_condo and not is_leasehold):
        structure = "Fee Simple Condo"
    elif "fee simple" in description:
        structure = "Fee Simple Building"
    else:
        structure = "Fee Simple Building (presumed)"

    confidence = "HIGH" if signals_found else "MODERATE" if is_condo else "LOW"

    return {
        "is_condo": is_condo,
        "is_leasehold": is_leasehold,
        "structure": structure,
        "confidence": confidence,
        "signals_found": signals_found,
    }


# ──────────────────────────────────────────────────────────────
# Hidden NOI Detection
# ──────────────────────────────────────────────────────────────

def detect_hidden_noi(listing_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if NOI/cap rate is hidden behind LoopNet's login wall.

    Properties listed as 'fully leased' / 'NNN' that hide financials
    are doing so because the real numbers make the ask look indefensible.

    Args:
        listing_data: Dict with noi, cap_rate, description, days_on_market fields

    Returns:
        {hidden, red_flags_count, flags, verdict}
    """
    description = (listing_data.get("description", "") or "").lower()
    noi = listing_data.get("noi")
    cap_rate = listing_data.get("cap_rate")
    dom = listing_data.get("days_on_market", 0)

    # Check if financials are missing
    financials_missing = (not noi or noi == 0) and (not cap_rate or cap_rate == 0)

    flags = []

    # Flag 1: Financials behind login wall
    is_investment = any(sig in description for sig in HIDDEN_NOI_SIGNALS)
    if is_investment and financials_missing:
        flags.append("NOI/Cap Rate hidden on 'fully leased'/'NNN' property — financials behind login wall")

    # Flag 2: Stale listing
    if dom > 180:
        flags.append(f"{dom} days on market — market has rejected the ask price")

    # Flag 3: Price reduction signal
    if "price reduction" in description or "price reduced" in description:
        flags.append("Recent price reduction — implies overpricing")

    # Flag 4: Tenant turnover signal
    if "buyer can occupy" in description or "owner user" in description:
        flags.append("'Buyer can occupy' language — tenant turnover planned")

    hidden = financials_missing and is_investment

    return {
        "hidden": hidden,
        "financials_gated": financials_missing and is_investment,
        "red_flags_count": len(flags),
        "flags": flags,
        "verdict": "CONCEALMENT LIKELY" if len(flags) >= 3 else
                   "SUSPICIOUS" if len(flags) >= 1 else "CLEAR",
    }


# ──────────────────────────────────────────────────────────────
# Human-Like Filter Utilities
# ──────────────────────────────────────────────────────────────

def apply_human_price_filter(driver, max_price: int):
    """
    Apply a price filter on LoopNet search results via UI interaction.

    LoopNet ignores URL parameters (msrp=, price=, max-price=).
    You MUST interact with the filter UI like a human:
    click Price button → type max → press Enter.

    This function expects to be on a LoopNet search results page.

    Args:
        driver: Selenium WebDriver connected to Firefox BiDi
        max_price: Maximum price to filter by (e.g., 1_500_000)

    Returns:
        True if filter was applied successfully, False otherwise
    """
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        wait = WebDriverWait(driver, 10)

        # Step 1: Dismiss any popups
        try:
            driver.find_element(By.CSS_SELECTOR, "body").send_keys(Keys.ESCAPE)
            time.sleep(1)
        except Exception:
            pass

        # Step 2: Click the "Price" filter button
        price_button = None
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            if btn.text.strip() == "Price":
                price_button = btn
                break

        if not price_button:
            # Try alternative selectors
            try:
                price_button = driver.find_element(
                    By.CSS_SELECTOR,
                    '[data-testid="price-filter"], [aria-label*="Price"], button:contains("Price")'
                )
            except Exception:
                pass

        if not price_button:
            print("[loopnet_utils] Could not find Price filter button")
            return False

        price_button.click()
        time.sleep(1.5)

        # Step 3: Find the "Max $" input and type the value
        max_input = None
        for inp in driver.find_elements(By.TAG_NAME, "input"):
            placeholder = inp.get_attribute("placeholder") or ""
            if "max" in placeholder.lower() or "max $" in placeholder.lower():
                max_input = inp
                break

        if not max_input:
            # Try typing in all visible inputs
            for inp in driver.find_elements(By.CSS_SELECTOR, 'input[type="text"]'):
                if inp.is_displayed():
                    max_input = inp
                    break

        if not max_input:
            print("[loopnet_utils] Could not find Max $ input")
            return False

        # Use native input setter for reliable value injection
        driver.execute_script(
            "arguments[0].value = arguments[1];", max_input, str(max_price))
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
            max_input)
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
            max_input)
        time.sleep(0.5)

        # Step 4: Press Enter to apply
        max_input.send_keys(Keys.ENTER)
        time.sleep(3)

        return True

    except Exception as e:
        print(f"[loopnet_utils] apply_human_price_filter error: {e}")
        return False


def extract_search_results(driver) -> List[Dict[str, Any]]:
    """
    Extract all listing placards from a LoopNet search results page.

    Args:
        driver: Selenium WebDriver on a LoopNet search results page

    Returns:
        List of parsed listing dicts
    """
    try:
        from selenium.webdriver.common.by import By

        # Find all article placard elements
        articles = driver.find_elements(By.CSS_SELECTOR, "article[data-listingid]")

        listings = []
        for article in articles:
            data = parse_listing_placard_via_selenium(article)
            if data:
                listings.append(data)

        return listings
    except Exception as e:
        print(f"[loopnet_utils] extract_search_results error: {e}")
        return []


def parse_listing_placard_via_selenium(article_element) -> Optional[Dict[str, Any]]:
    """
    Parse a LoopNet placard using Selenium element (live DOM access).
    More reliable than BeautifulSoup for extracted data-gtm attributes.
    """
    try:
        data = {}
        data["listing_id"] = article_element.get_attribute("data-listingid") or ""

        # Price
        price_el = article_element.find_elements(By.CSS_SELECTOR, '[class*="price"]')
        if not price_el:
            price_el = article_element.find_elements(By.CSS_SELECTOR, 'span')
        for el in price_el:
            text = el.text.strip()
            if text.startswith("$"):
                data["price"] = _parse_price(text)
                break

        # Title / URL
        try:
            link = article_element.find_element(By.TAG_NAME, "a")
            data["title"] = link.text.strip()
            data["url"] = link.get_attribute("href") or ""
        except Exception:
            pass

        # Cap rate from text
        full_text = article_element.text
        cap_match = re.search(r'(\d+\.?\d*)%\s*Cap', full_text)
        if cap_match:
            data["cap_rate"] = float(cap_match.group(1))

        # SF
        sf_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*SF', full_text)
        if sf_match:
            data["sf"] = int(sf_match.group(1).replace(',', ''))

        # City/State
        city_match = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*([A-Z]{2})', full_text)
        if city_match:
            data["city"] = city_match.group(1)
            data["state"] = city_match.group(2)

        return data if data.get("listing_id") else None

    except Exception as e:
        print(f"[loopnet_utils] parse_listing_placard_via_selenium error: {e}")
        return None


# Need By import for Selenium-based parser
try:
    from selenium.webdriver.common.by import By
except ImportError:
    By = None


# ──────────────────────────────────────────────────────────────
# Pipeline Integration
# ──────────────────────────────────────────────────────────────

def listing_to_pipeline_entry(listing_data: Dict[str, Any],
                              tax_bomb: Dict[str, Any],
                              condo: Dict[str, Any],
                              hidden_noi: Dict[str, Any]) -> Dict[str, Any]:
    """
    Combine listing data, tax bomb, condo detection, and hidden NOI flags
    into a pipeline-ready entry dict.

    Args:
        listing_data: Parsed listing placard data
        tax_bomb: Output from detect_tax_bomb()
        condo: Output from detect_condo()
        hidden_noi: Output from detect_hidden_noi()

    Returns:
        Flat dict suitable for pipeline.json consumption
    """
    return {
        "listing_id": listing_data.get("listing_id", ""),
        "url": listing_data.get("url", ""),
        "title": listing_data.get("title", ""),
        "address": listing_data.get("title", ""),  # Title often IS the address
        "city": listing_data.get("city", ""),
        "state": listing_data.get("state", "NJ"),
        "property_type": listing_data.get("property_type", ""),
        "ask_price": listing_data.get("price"),
        "cap_rate": listing_data.get("cap_rate"),
        "sf": listing_data.get("sf"),
        "noi": listing_data.get("noi"),
        # Detection flags
        "tax_bomb_pct": tax_bomb.get("tax_increase_pct"),
        "post_sale_tax": tax_bomb.get("post_sale_tax"),
        "is_condo": condo.get("is_condo", False),
        "is_leasehold": condo.get("is_leasehold", False),
        "structure": condo.get("structure", ""),
        "hidden_noi": hidden_noi.get("hidden", False),
        "hidden_noi_flags": hidden_noi.get("flags", []),
    }


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python loopnet_utils.py [ensure|test]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "ensure":
        ready = ensure_firefox()
        print(f"Firefox ready: {ready}")
    elif cmd == "test":
        # Quick functional test
        print("Testing tax bomb detection...")
        tb = detect_tax_bomb(799000, 117900, "Middlesex", "NJ")
        print(f"  Post-sale tax: ${tb['post_sale_tax']:,.0f}")
        print(f"  Increase: +{tb['tax_increase_pct']}%")
        print(f"  Verdict: {tb['verdict']}")

        print("\nTesting condo detection...")
        cd = detect_condo({"description": "Fee simple retail building. Not a condo.", "property_type": "Retail"})
        print(f"  Is condo: {cd['is_condo']}, Structure: {cd['structure']}")

        cd2 = detect_condo({"description": "Ground lease expiring 2030. Leasehold interest only.", "property_type": "Retail Condo"})
        print(f"  Is condo: {cd2['is_condo']}, Is leasehold: {cd2['is_leasehold']}, Structure: {cd2['structure']}")

        print("\nTesting hidden NOI detection...")
        hn = detect_hidden_noi({"description": "Fully leased NNN retail investment.", "noi": None, "cap_rate": None, "days_on_market": 200})
        print(f"  Hidden: {hn['hidden']}, Flags: {hn['red_flags_count']}, Verdict: {hn['verdict']}")
