"""Exercise both selected sealed diagnostic pairs and a wrong-pair rejection."""
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path

from comparison_audit import audit_delivery_pair

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PAIRS = {"roadway_vs_sidewalk": ("roadway_walk", "sidewalk_walk"),
         "roadway_vs_shoulder": ("roadway_walk", "shoulder_walk")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", choices=PAIRS, required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((HERE/"execution-manifest.json").read_text())
    def source(suffix):
        entry = next(e for e in manifest["cases"] if e["case_id"].endswith("__"+suffix))
        tokens = shlex.split(entry["delivery_acceptance"]["command"])
        root = (REPO/tokens[tokens.index("--output")+1]).resolve()
        if not root.is_relative_to(REPO/".runtime-work"):
            raise ValueError("diagnostic pair source outside .runtime-work")
        return root
    first, second = (source(suffix) for suffix in PAIRS[args.pair])
    if args.negative:
        second = first
    receipt = audit_delivery_pair(first, second, diagnostic_test=True)
    if (not receipt["diagnostic_audit_test_passed"] or
            receipt["physical_acceptance_claimed"] or
            receipt["actual_pixel_visibility_verified"]):
        raise AssertionError("paired diagnostic audit made a physical or pixel claim")
    if not args.negative:
        path = HERE/("paired-delivery-"+args.pair+".json")
        path.write_text(json.dumps(receipt, indent=2)+"\n")
    print(json.dumps({"pair": args.pair, "diagnostic_pair_passed": True,
                      "frame_count": receipt["frame_count"],
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
