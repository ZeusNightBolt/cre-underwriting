#!/usr/bin/env python3
"""
LoopNet Batch Scraper — Search + detail-scrape all matching listings.

Pipeline:
  1. Run loopnet_search.py to get all NJ listings under max_price
  2. Read search results and filter to promising listings
     (skip leaseholds, skip >max_price, skip missing listing_id)
  3. Scrape each filtered listing's detail page via loopnet_listing.py
  4. Merge all results into a single output JSON

Rate limiting: max 5 listings per session by default, with delays
between detail-page fetches to avoid triggering LoopNet rate limits.

Usage:
    python loopnet_batch.py
    python loopnet_batch.py --max-price 1500000 --max-listings 10
    python loopnet_batch.py --max-price 2000000 --max-listings 5 --output ~/cre/incoming/batch.json
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────

SCRIPTS_DIR = Path(__file__).resolve().parent
SEARCH_SCRIPT = SCRIPTS_DIR / "loopnet_search.py"
LISTING_SCRIPT = SCRIPTS_DIR / "loopnet_listing.py"

DEFAULT_MAX_PRICE = 1_500_000
DEFAULT_MAX_LISTINGS = 5
DEFAULT_OUTPUT = os.path.expanduser("~/cre/incoming/loopnet_batch_results.json")
DEFAULT_SEARCH_OUTPUT = os.path.expanduser("~/cre/incoming/loopnet_search_results.json")

DELAY_BETWEEN_LISTINGS = 4  # seconds — be gentle to LoopNet


# ──────────────────────────────────────────────────────────────
# Core
# ──────────────────────────────────────────────────────────────

def run_search(max_price: int, search_output: str) -> list[dict]:
    """Run loopnet_search.py and return its parsed listings."""
    print(f"\n{'='*60}")
    print(f"PHASE 1: Search (max price: ${max_price:,})")
    print(f"{'='*60}")

    result = subprocess.run(
        [sys.executable, str(SEARCH_SCRIPT),
         "--max-price", str(max_price),
         "--output", search_output],
        capture_output=True, text=True, timeout=120,
        cwd=str(SCRIPTS_DIR),
    )

    print(result.stdout)
    if result.returncode != 0:
        print(f"[loopnet_batch] Search failed:\n{result.stderr}", file=sys.stderr)
        return []

    # Read the search results file
    try:
        with open(search_output) as f:
            data = json.load(f)
        listings = data.get("listings", [])
        print(f"[loopnet_batch] Search returned {len(listings)} listings")
        return listings
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[loopnet_batch] Could not read search results: {e}", file=sys.stderr)
        return []


def filter_listings(listings: list[dict], max_price: int) -> list[dict]:
    """Filter search results to promising CRE investments."""
    filtered = []
    skipped_leasehold = 0
    skipped_price = 0
    skipped_noid = 0

    for listing in listings:
        lid = listing.get("listing_id")
        if not lid:
            skipped_noid += 1
            continue

        price = listing.get("price")
        if price and (isinstance(price, int) or isinstance(price, float)):
            if price > max_price:
                skipped_price += 1
                continue

        # Skip leasehold signals in title (basic check before detail scrape)
        title = (listing.get("title", "") or "").lower()
        if any(sig in title for sig in ["ground lease", "leasehold", "lease assignment"]):
            skipped_leasehold += 1
            continue

        filtered.append(listing)

    print(f"[loopnet_batch] Filter results:")
    print(f"  Total search results:  {len(listings)}")
    print(f"  → Kept for detail:     {len(filtered)}")
    print(f"  → Skipped (leasehold): {skipped_leasehold}")
    print(f"  → Skipped (price):     {skipped_price}")
    print(f"  → Skipped (no ID):     {skipped_noid}")
    return filtered


def scrape_details(listings: list[dict], max_listings: int) -> list[dict]:
    """Scrape detail pages for each listing via loopnet_listing.py subprocess."""
    to_scrape = listings[:max_listings]
    results = []

    print(f"\n{'='*60}")
    print(f"PHASE 2: Detail Scrape ({len(to_scrape)} listings, max {max_listings})")
    print(f"{'='*60}")

    for i, listing in enumerate(to_scrape):
        lid = listing.get("listing_id")
        title = listing.get("title", "Unknown")
        print(f"\n[{i+1}/{len(to_scrape)}] Scraping: {title} (ID: {lid})")

        detail_output = os.path.expanduser(f"~/cre/incoming/listing_{lid}.json")

        result = subprocess.run(
            [sys.executable, str(LISTING_SCRIPT),
             str(lid),
             "--output", detail_output],
            capture_output=True, text=True, timeout=90,
            cwd=str(SCRIPTS_DIR),
        )

        print(result.stdout.strip())

        if result.returncode == 0 and os.path.exists(detail_output):
            try:
                with open(detail_output) as f:
                    detail = json.load(f)
                results.append(detail)
                print(f"  ✓ Extracted: ask={detail.get('ask_price', '?')}, "
                      f"cap={detail.get('cap_rate', '?')}, "
                      f"sf={detail.get('sf', '?')}")
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"  ✗ Could not read detail output: {e}")
        else:
            print(f"  ✗ Detail scrape failed (exit code {result.returncode})")
            if result.stderr.strip():
                print(f"    stderr: {result.stderr.strip()[:200]}")

        # Rate-limit delay (don't wait after the last one)
        if i < len(to_scrape) - 1:
            print(f"  (waiting {DELAY_BETWEEN_LISTINGS}s...)")
            time.sleep(DELAY_BETWEEN_LISTINGS)

    return results


def merge_and_save(search_listings: list[dict], detail_results: list[dict],
                   output_path: str) -> str:
    """Merge search + detail data and save to output JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Build a merged result keyed by listing_id
    merged = {}
    for listing in search_listings:
        lid = listing.get("listing_id")
        if lid:
            merged[lid] = {"search_data": listing}

    for detail in detail_results:
        lid = detail.get("listing_id")
        if lid:
            if lid in merged:
                merged[lid]["detail_data"] = detail
            else:
                merged[lid] = {"detail_data": detail}

    # Count complete entries
    complete = sum(1 for v in merged.values() if "detail_data" in v)

    payload = {
        "batch_info": {
            "total_search_results": len(search_listings),
            "detail_scraped": len(detail_results),
            "complete_entries": complete,
        },
        "listings": merged,
    }

    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"\n[loopnet_batch] Merged results saved to: {output_path}")
    print(f"  Complete listings: {complete}/{len(merged)}")
    return output_path


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Batch LoopNet search + detail scrape for NJ properties"
    )
    parser.add_argument(
        "--max-price", type=int, default=DEFAULT_MAX_PRICE,
        help=f"Maximum asking price (default: {DEFAULT_MAX_PRICE:,})"
    )
    parser.add_argument(
        "--max-listings", type=int, default=DEFAULT_MAX_LISTINGS,
        help=f"Max listings to detail-scrape (default: {DEFAULT_MAX_LISTINGS})"
    )
    parser.add_argument(
        "--output", type=str, default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--search-only", action="store_true",
        help="Only run the search phase (skip detail scraping)"
    )
    parser.add_argument(
        "--search-output", type=str, default=DEFAULT_SEARCH_OUTPUT,
        help=f"Search results JSON path (default: {DEFAULT_SEARCH_OUTPUT})"
    )
    parser.add_argument(
        "--from-search", type=str, default=None,
        help="Skip search, read listings from existing JSON file"
    )
    args = parser.parse_args()

    output_path = os.path.expanduser(args.output)
    search_output = os.path.expanduser(args.search_output)

    # ── Phase 1: Get listings ────────────────────────────
    if args.from_search:
        print(f"[loopnet_batch] Loading listings from: {args.from_search}")
        with open(args.from_search) as f:
            data = json.load(f)
        all_listings = data.get("listings", [])
        print(f"[loopnet_batch] Loaded {len(all_listings)} listings")
    else:
        all_listings = run_search(args.max_price, search_output)

    if not all_listings:
        print("[loopnet_batch] No listings found. Exiting.", file=sys.stderr)
        sys.exit(1)

    # ── Phase 2: Filter ──────────────────────────────────
    filtered = filter_listings(all_listings, args.max_price)

    if not filtered:
        print("[loopnet_batch] No listings passed filter. Exiting.")
        sys.exit(0)

    # ── Phase 3: Detail scrape (or skip) ─────────────────
    if args.search_only:
        print("\n[loopnet_batch] --search-only: skipping detail scrape")
        detail_results = []
    else:
        detail_results = scrape_details(filtered, args.max_listings)

    # ── Phase 4: Merge & save ────────────────────────────
    merge_and_save(all_listings, detail_results, output_path)

    print("\n[loopnet_batch] Done.")


if __name__ == "__main__":
    main()
