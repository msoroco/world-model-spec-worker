"""Reopen saved originals and test the fixed-condition comparison guard."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from attention_measurement import measure
from comparison_audit import audit as audit_pair
from saved_delivery import audit_comparison


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steady", type=Path, required=True)
    parser.add_argument("--variation", type=Path, required=True)
    parser.add_argument("--mode", choices=("positive", "negative"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    for path in (args.steady, args.variation):
        if repo / ".runtime-work" not in path.resolve().parents:
            raise ValueError("Saved attempt must be under .runtime-work")
    steady = folder.name + "__steady_travel"
    variation = folder.name + "__steering_variation"
    roots = {steady: args.steady, variation: args.variation}
    if args.mode == "positive":
        if args.output is None or folder not in args.output.resolve().parents:
            raise ValueError("Comparison receipt belongs in owned assignment")
        result = audit_comparison(roots, require_delivery=False)
        if result.get("diagnostic_fixture") is not True or result.get("legal_judgment") != "unresolved":
            raise ValueError("Diagnostic or legal scope changed")
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"comparison_id": result["comparison_id"],
                          "fixed_conditions_verified": len(result["fixed_conditions_verified"]),
                          "diagnostic_fixture": True, "delivery_accepted": False}))
        return
    measurements = {case: measure(root / "operation.jsonl", case) for case, root in roots.items()}
    captures = {case: json.loads((root / "capture.json").read_text()) for case, root in roots.items()}
    changed = deepcopy(captures)
    changed[variation]["site_source_sha256"] = "0" * 64
    audit_pair(measurements, changed)
    raise ValueError("Altered fixed site source was accepted")


if __name__ == "__main__":
    main()
