#!/usr/bin/env python3
"""Wrapper for cre_underwriting.dashboard — generate CRE dashboard HTML."""
import argparse, json, os, sys

PKG_DIR = os.path.expanduser("~/cre-underwriting")
if PKG_DIR not in sys.path:
    sys.path.insert(0, PKG_DIR)

from cre_underwriting.dashboard import generate_dashboard

def main():
    parser = argparse.ArgumentParser(description="Generate CRE dashboard")
    parser.add_argument("--input", required=True, help="Path to analysis JSON (from deal-underwriter)")
    parser.add_argument("--output", required=True, help="Output HTML path")
    args = parser.parse_args()

    with open(os.path.expanduser(args.input)) as f:
        analysis = json.load(f)

    html = generate_dashboard(analysis)

    outpath = os.path.expanduser(args.output)
    os.makedirs(os.path.dirname(outpath) or ".", exist_ok=True)
    with open(outpath, "w") as f:
        f.write(html)

    size_kb = os.path.getsize(outpath) / 1024
    print(f"✓ Dashboard saved: {outpath} ({size_kb:.1f} KB)")

if __name__ == "__main__":
    main()
