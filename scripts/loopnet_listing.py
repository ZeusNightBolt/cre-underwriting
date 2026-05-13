#!/usr/bin/env python3
"""
LoopNet Listing Detail Scraper — Scrape a single listing's full detail page.

Connects to the running Firefox BiDi instance via loopnet_utils, navigates
to the listing page, and extracts:

  • Full description        • Dollar amounts          • Year built
  • Property facts          • Tax assessment          • Zoning
  • Building details        • Cap rate / NOI          • Parking
  • Lot size                • Condo / leasehold flags • Tax bomb risk
  • Hidden NOI detection

Usage:
    python loopnet_listing.py <listing_id>
    python loopnet_listing.py 40306150
    python loopnet_listing.py 40306150 --output ~/cre/incoming/my_listing.json
    python loopnet_listing.py https://www.loopnet.com/Listing/.../40306150/
"""

import argparse
import json
import os
import re
import sys
import time

from loopnet_utils import (
    ensure_firefox,
    get_selenium_driver,
    detect_condo,
    detect_tax_bomb,
    detect_hidden_noi,
    listing_to_pipeline_entry,
)

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

DEFAULT_OUTPUT_DIR = os.path.expanduser("~/cre/incoming")
LISTING_URL_TEMPLATE = "https://www.loopnet.com/Listing/{listing_id}/"


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def parse_listing_id(raw: str) -> str:
    """Extract an 8+ digit listing ID from a URL or raw string."""
    m = re.search(r"/(\d{8,})/", raw)
    if m:
        return m.group(1)
    return raw.strip().replace("/", "")


def _parse_price(price_str: str) -> int | None:
    """Parse dollar string → int. '$799,000' → 799000."""
    if not price_str:
        return None
    try:
        return int(float(re.sub(r"[^\d.]", "", str(price_str))))
    except (ValueError, TypeError):
        return None


def _safe_int(raw: str) -> int | None:
    """Parse string → int, returning None on failure."""
    try:
        return int(float(re.sub(r"[^\d.]", "", str(raw))))
    except (ValueError, TypeError):
        return None


# ──────────────────────────────────────────────────────────────
# Core
# ──────────────────────────────────────────────────────────────

def scrape_listing(listing_id: str) -> dict | None:
    """
    Scrape a single LoopNet listing detail page.

    Returns a structured dict with all extracted data, or None on failure.
    """
    url = LISTING_URL_TEMPLATE.format(listing_id=listing_id)
    print(f"[loopnet_listing] Fetching: {url}")

    if not ensure_firefox():
        print("[loopnet_listing] ERROR: Could not start Firefox", file=sys.stderr)
        return None

    driver = get_selenium_driver()
    if not driver:
        print("[loopnet_listing] ERROR: Could not connect Selenium to Firefox", file=sys.stderr)
        return None

    try:
        from selenium.webdriver.common.by import By

        driver.get(url)
        time.sleep(5)  # Let JS fully render

        html = driver.page_source
        full_text = driver.find_element(By.TAG_NAME, "body").text
    finally:
        driver.quit()

    # ── Access check ─────────────────────────────────────
    if "Access Denied" in full_text:
        print("[loopnet_listing] ACCESS DENIED — Akamai blocked. "
              "Ensure Firefox is logged into LoopNet.", file=sys.stderr)
        return None

    # ── Build data dict ──────────────────────────────────
    data: dict = {
        "listing_id": listing_id,
        "url": url,
    }

    # Title
    title_m = re.search(r"(.+?)(?:\s{2,}|\n)", full_text)
    data["title"] = title_m.group(1).strip() if title_m else ""

    # All dollar amounts found on the page (first 20, deduped)
    dollar_amounts = list(dict.fromkeys(re.findall(r"\$[\d,]+(?:\.\d{2})?", full_text)))[:20]
    data["dollar_amounts"] = dollar_amounts

    # Ask price — first large dollar amount
    for amt in dollar_amounts:
        val = _parse_price(amt)
        if val and val > 10_000:
            data["ask_price"] = val
            break

    # ── Regex field extraction ───────────────────────────
    patterns: dict[str, str] = {
        "cap_rate":       r"Cap\s*Rate[:\s]*([\d.]+%)",
        "noi":            r"(?:NOI|Net\s*Operating\s*Income)[^\$]*(\$[\d,]+)",
        "gross_income":   r"(?:Gross\s*(?:Annual\s*)?(?:Rent|Income))[^\$]*(\$[\d,]+)",
        "grm":            r"Gross\s*Rent\s*Multiplier[:\s]*([\d.]+)",
        "year_built":     r"(?:Year\s*Built|Built)[:\s]*(\d{4})",
        "building_class": r"Building\s*Class[:\s]*([A-C])",
        "zoning":         r"Zon(?:ing|ed)[:\s]*([A-Z0-9\-]+)",
        "parking":        r"Parking[:\s]*([^\n]+?)(?:\s{2,}|\n|$)",
        "lot_size":       r"Lot\s*Size[:\s]*([^\n]+?)(?:\s{2,}|\n|$)",
        "floors":         r"(?:Floors|Stories)[:\s]*(\d+)",
        "property_type":  r"Property\s*Type[:\s]*([^\n]+?)(?:\s{2,}|\n|$)",
        "property_subtype": r"Property\s*Sub(?:-?)type[:\s]*([^\n]+?)(?:\s{2,}|\n|$)",
        "tenancy":        r"(?:Tenancy|Occupancy)[:\s]*([^\n]+?)(?:\s{2,}|\n|$)",
        "sale_type":      r"S(?:ale|AL)\s*Type[:\s]*([^\n]+?)(?:\s{2,}|\n|$)",
        "date_on_market": r"Date\s*(?:on\s*Market|Listed)[:\s]*([^\n]+?)(?:\s{2,}|\n|$)",
        "price_per_sf":   r"\$([\d.]+)\s*(?:per|/)\s*(?:SF|Sq\s*Ft)",
    }

    for key, pat in patterns.items():
        m = re.search(pat, full_text, re.IGNORECASE)
        if m:
            data[key] = m.group(1).strip()[:120]

    # ── Multi-value extraction ───────────────────────────
    # Square footage values
    sf_vals = re.findall(r"([\d,]+)\s*(?:sq\.?\s*ft|SF|Sq\s*Ft|Square\s*Feet)",
                         full_text, re.IGNORECASE)
    if sf_vals:
        data["sqft_values"] = sf_vals[:5]
        data["sf"] = int(sf_vals[0].replace(",", ""))

    # Acre values
    acre_vals = re.findall(r"([\d.,]+)\s*(?:Acres?|AC)", full_text, re.IGNORECASE)
    if acre_vals:
        data["acre_values"] = acre_vals[:3]

    # Unit counts
    unit_vals = re.findall(r"(\d+)\s*(?:Units?|Apartments?|Suites?)", full_text)
    if unit_vals:
        data["unit_values"] = [u for u in unit_vals
                               if u not in ("1", "2", "3") or len(unit_vals) > 3][:5]

    # ── Description ──────────────────────────────────────
    # Grab the <article> or the largest text block after the title
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        for sel in ['[class*="description"]', '[class*="Description"]',
                     'article', '[data-testid*="desc"]']:
            els = soup.select(sel)
            for el in els:
                t = el.get_text(separator="\n", strip=True)
                if len(t) > 100:
                    data["description"] = t[:3000]
                    break
            if "description" in data:
                break
    except ImportError:
        pass  # BeautifulSoup not available — skip description

    # ── Tax assessment ───────────────────────────────────
    tax_match = re.search(r"(?:Tax\s*Assessment|Assessed\s*Value|Assessment)[:\s]*\$?([\d,]+)",
                          full_text, re.IGNORECASE)
    if tax_match:
        data["tax_assessment"] = int(tax_match.group(1).replace(",", ""))

    # Current taxes
    tax_amt = re.search(r"(?:Annual\s*)?(?:Property\s*)?Tax(?:es)?[:\s]*\$?([\d,]+)",
                        full_text, re.IGNORECASE)
    if tax_amt:
        data["annual_taxes"] = int(tax_amt.group(1).replace(",", ""))

    # ── Address ──────────────────────────────────────────
    addr_m = re.search(
        r"(\d+[-\d]*\s+[A-Za-z\s]+(?:Ave|Street|St|Road|Rd|Blvd|Drive|Dr|Ln|Pl|Way|Ct)"
        r"[,.]?\s*(?:[A-Za-z\s]+,)?\s*[A-Z]{2}\s*\d{5})",
        full_text
    )
    if addr_m:
        data["address"] = addr_m.group(1)

    # City / state
    city_m = re.search(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*([A-Z]{2})", full_text)
    if city_m:
        data["city"] = city_m.group(1)
        data["state"] = city_m.group(2)

    # ── Days on market ───────────────────────────────────
    dom_match = re.search(r"(\d+)\s*(?:Days|Day)\s*(?:on\s*(?:Market|LoopNet))",
                          full_text, re.IGNORECASE)
    if dom_match:
        data["days_on_market"] = int(dom_match.group(1))

    # ── Raw text snippet (for manual analysis) ───────────
    data["raw_text_snippet"] = full_text[:6000]

    # ── Detection flags ──────────────────────────────────
    # Condo / leasehold
    condo_result = detect_condo(data)
    data["condo_analysis"] = condo_result

    # Tax bomb
    ask_price = data.get("ask_price", 0) or 0
    tax_assessment = data.get("tax_assessment", 0) or 0
    county = data.get("city", "") or ""
    state = data.get("state", "NJ")
    if ask_price and tax_assessment:
        tax_bomb_result = detect_tax_bomb(ask_price, tax_assessment, county, state)
    else:
        tax_bomb_result = {
            "verdict": "INSUFFICIENT_DATA",
            "note": "Missing ask_price or tax_assessment"
        }
    data["tax_bomb_analysis"] = tax_bomb_result

    # Hidden NOI
    hidden_noi_result = detect_hidden_noi(data)
    data["hidden_noi_analysis"] = hidden_noi_result

    # ── Pipeline entry ───────────────────────────────────
    data["pipeline_entry"] = listing_to_pipeline_entry(
        data, tax_bomb_result, condo_result, hidden_noi_result
    )

    return data


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scrape a single LoopNet listing detail page"
    )
    parser.add_argument(
        "listing", type=str,
        help="Listing ID (e.g. 40306150) or full LoopNet URL"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output JSON path (default: ~/cre/incoming/listing_{id}.json)"
    )
    args = parser.parse_args()

    listing_id = parse_listing_id(args.listing)
    print(f"[loopnet_listing] Listing ID: {listing_id}")

    result = scrape_listing(listing_id)
    if result is None:
        print("[loopnet_listing] Scraping failed", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = os.path.expanduser(args.output)
    else:
        output_path = os.path.join(DEFAULT_OUTPUT_DIR, f"listing_{listing_id}.json")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"\n[loopnet_listing] Saved to: {output_path}")

    # Quick summary
    print(f"  Title:         {result.get('title', 'N/A')}")
    print(f"  Ask:           ${result.get('ask_price', '?'):,}" if result.get('ask_price') else "  Ask:           N/A")
    print(f"  Cap Rate:      {result.get('cap_rate', 'N/A')}")
    print(f"  NOI:           {result.get('noi', 'N/A')}")
    print(f"  SF:            {result.get('sf', 'N/A'):,}" if result.get('sf') else "  SF:            N/A")
    print(f"  Year Built:    {result.get('year_built', 'N/A')}")
    print(f"  Zoning:        {result.get('zoning', 'N/A')}")
    print(f"  Condo:         {result.get('condo_analysis', {}).get('structure', 'N/A')}")
    print(f"  Tax Bomb:      {result.get('tax_bomb_analysis', {}).get('verdict', 'N/A')}")
    print(f"  Hidden NOI:    {result.get('hidden_noi_analysis', {}).get('verdict', 'N/A')}")


if __name__ == "__main__":
    main()
