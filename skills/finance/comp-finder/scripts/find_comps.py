#!/usr/bin/env python3
"""Wrapper for cre_underwriting.comps — finds comparable properties."""
import argparse, json, os, sys

# Ensure package is importable
PKG_DIR = os.path.expanduser("~/cre-underwriting")
if PKG_DIR not in sys.path:
    sys.path.insert(0, PKG_DIR)

from cre_underwriting.comps import find_comps

def main():
    parser = argparse.ArgumentParser(description="Find CRE comparable properties")
    parser.add_argument("--input", required=True, help="Path to property JSON")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    with open(os.path.expanduser(args.input)) as f:
        prop = json.load(f)

    result = find_comps(
        address=prop.get("address", ""),
        property_type=prop.get("property_type", ""),
        sf=prop.get("sf", 0),
        price=prop.get("price", 0),
    )

    outpath = os.path.expanduser(args.output)
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, "w") as f:
        json.dump(result, f, indent=2)

    print(f"✓ Comps saved: {outpath}")
    print(f"  Sources: {result.get('source_status', {})}")
    print(f"  Count: {result.get('summary', {}).get('count', 0)}")

if __name__ == "__main__":
    main()
