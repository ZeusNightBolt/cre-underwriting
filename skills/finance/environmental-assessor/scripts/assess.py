#!/usr/bin/env python3
"""Wrapper for cre_underwriting.environmental — assess location risks."""
import argparse, json, os, sys

PKG_DIR = os.path.expanduser("~/cre-underwriting")
if PKG_DIR not in sys.path:
    sys.path.insert(0, PKG_DIR)

from cre_underwriting.environmental import assess_location

def main():
    parser = argparse.ArgumentParser(description="Assess CRE location risks")
    parser.add_argument("--input", required=True, help="Path to property JSON")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    with open(os.path.expanduser(args.input)) as f:
        prop = json.load(f)

    result = assess_location(
        address=prop.get("address", ""),
        city=prop.get("city", ""),
        state=prop.get("state", "NJ"),
        lot_size_sf=prop.get("lot_size_sf"),
        year_built=prop.get("year_built"),
    )

    outpath = os.path.expanduser(args.output)
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"✓ Environmental saved: {outpath}")
    flood = result.get("flood_zone", {})
    print(f"  Flood zone: {flood.get('zone', 'N/A')}")
    print(f"  UST risk: {result.get('ust_risk', 'N/A')}")

if __name__ == "__main__":
    main()
