#!/usr/bin/env python3
"""Wrapper for cre_underwriting.pipeline — full deal underwriting."""
import argparse, json, os, sys

PKG_DIR = os.path.expanduser("~/cre-underwriting")
if PKG_DIR not in sys.path:
    sys.path.insert(0, PKG_DIR)

from cre_underwriting.pipeline import PipelineOrchestrator

def main():
    parser = argparse.ArgumentParser(description="Underwrite a CRE deal")
    parser.add_argument("--input", required=True, help="Path to structured deal JSON (from listing-parser)")
    parser.add_argument("--output", required=True, help="Output analysis JSON path")
    parser.add_argument("--env", help="Optional environmental assessment JSON")
    parser.add_argument("--comps", help="Optional comps JSON")
    args = parser.parse_args()

    orch = PipelineOrchestrator()
    result = orch.run(
        deal_path=os.path.expanduser(args.input),
        env_path=os.path.expanduser(args.env) if args.env else None,
        comps_path=os.path.expanduser(args.comps) if args.comps else None,
    )

    outpath = os.path.expanduser(args.output)
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, "w") as f:
        json.dump(result, f, indent=2, default=str)

    # Summary
    cvx = result.get("convexity", {})
    enh = result.get("enhanced", {})
    verdict = cvx.get("verdict", enh.get("verdict", "N/A"))
    print(f"✓ Analysis saved: {outpath}")
    print(f"  Verdict: {verdict}")
    print(f"  Convexity ratio: {cvx.get('convexity_ratio', 'N/A')}")
    print(f"  Moats: {enh.get('moat_score', 'N/A')}")
    print(f"  Offers: {len(enh.get('offers', []))} rungs")

if __name__ == "__main__":
    main()
