#!/usr/bin/env python3
"""
LoopNet Search — Search for NJ commercial properties under a max price.

Uses Firefox BiDi (real browser) via loopnet_utils to:
  1. Navigate to the NJ for-sale search page
  2. Apply a human-like price filter (LoopNet ignores URL price params)
  3. Extract all listing placards from the results page

Outputs a JSON file with all parsed listing placards.

Usage:
    python loopnet_search.py
    python loopnet_search.py --max-price 2000000
    python loopnet_search.py --max-price 1500000 --output ~/cre/incoming/my_search.json
"""

import argparse
import json
import os
import sys
import time

from loopnet_utils import (
    ensure_firefox,
    get_selenium_driver,
    apply_human_price_filter,
    extract_search_results,
)

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

SEARCH_URL = "https://www.loopnet.com/search/commercial-real-estate/nj/for-sale/"
DEFAULT_MAX_PRICE = 1_500_000
DEFAULT_OUTPUT = os.path.expanduser("~/cre/incoming/loopnet_search_results.json")


# ──────────────────────────────────────────────────────────────
# Core
# ──────────────────────────────────────────────────────────────

def run_search(max_price: int = DEFAULT_MAX_PRICE) -> list[dict]:
    """
    Run a LoopNet search for NJ properties under max_price.

    Returns a list of parsed listing placard dicts.
    """
    print(f"[loopnet_search] Ensuring Firefox BiDi is running...")
    if not ensure_firefox():
        print("[loopnet_search] ERROR: Could not start Firefox", file=sys.stderr)
        return []

    driver = get_selenium_driver()
    if not driver:
        print("[loopnet_search] ERROR: Could not connect Selenium to Firefox", file=sys.stderr)
        return []

    try:
        print(f"[loopnet_search] Navigating to: {SEARCH_URL}")
        driver.get(SEARCH_URL)
        time.sleep(4)

        print(f"[loopnet_search] Applying price filter (max ${max_price:,})...")
        ok = apply_human_price_filter(driver, max_price)
        if not ok:
            print("[loopnet_search] WARNING: Price filter may not have applied — "
                  "results may include properties above the max price")

        time.sleep(2)

        print("[loopnet_search] Extracting listing placards...")
        listings = extract_search_results(driver)
        print(f"[loopnet_search] Found {len(listings)} listings")

        return listings

    finally:
        driver.quit()


def save_results(listings: list[dict], output_path: str) -> str:
    """Save listings to a JSON file. Returns the resolved output path."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    payload = {
        "search_url": SEARCH_URL,
        "total_listings": len(listings),
        "listings": listings,
    }

    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"[loopnet_search] Saved {len(listings)} listings to {output_path}")
    return output_path


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Search LoopNet for NJ commercial properties under a max price"
    )
    parser.add_argument(
        "--max-price", type=int, default=DEFAULT_MAX_PRICE,
        help=f"Maximum asking price (default: {DEFAULT_MAX_PRICE:,})"
    )
    parser.add_argument(
        "--output", type=str, default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})"
    )
    args = parser.parse_args()

    listings = run_search(max_price=args.max_price)

    if not listings:
        print("[loopnet_search] No listings found — check Firefox/LoopNet access", file=sys.stderr)
        sys.exit(1)

    output_path = os.path.expanduser(args.output)
    save_results(listings, output_path)

    # Quick summary
    priced = [l for l in listings if l.get("price")]
    print(f"\nSummary:")
    print(f"  Total listings:  {len(listings)}")
    print(f"  With prices:     {len(priced)}")
    if priced:
        prices = [l["price"] for l in priced]
        print(f"  Price range:     ${min(prices):,} – ${max(prices):,}")
    print(f"  Output:          {output_path}")


if __name__ == "__main__":
    main()
