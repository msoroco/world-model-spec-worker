"""Independently check selected diagnostic pair isolation and rejection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_bundles import HERE, AID
from stand import SourceError, audit_comparison

SCRATCH = HERE.parents[1] / ".runtime-work" / "c135087-selected-analysis-v5"
MODES = ("loading_mode", "entrant_mode", "access_mode")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    plan = json.loads((HERE / "case-plan.json").read_text())
    cases = {case["case_id"]: case for case in plan["cases"]}
    receipts = []
    for comparison in plan["comparisons"]:
        left_id, right_id = comparison["case_ids"]
        left, right = cases[left_id], cases[right_id]
        difference = comparison["deliberate_differences"]
        if len(difference) != 1 or difference[0] not in MODES:
            raise ValueError("comparison needs exactly one declared source mode")
        fixed = [key for key in MODES if key not in difference]
        audit_comparison(left, right, fixed, difference)
        roots = [SCRATCH / cid.removeprefix(AID + "__") / "positive" for cid in (left_id, right_id)]
        if any(not root.is_dir() for root in roots):
            raise ValueError("selected saved source missing")
        source_names = ("site-original.json", "vehicle-original.json", "overview.mkv", "approach.mkv",
                        "reference_corner.mkv", "driver_reference.mkv")
        source_hashes = {name: [sha(root / name) for root in roots] for name in source_names}
        if any(pair[0] != pair[1] for pair in source_hashes.values()):
            raise ValueError("comparison changed fixed original source")
        measured = [json.loads((root / "analysis-report.json").read_text())["measurements"] for root in roots]
        output = {"access_mode": "access_effect", "loading_mode": "passenger_loading",
                  "entrant_mode": "taxicab_entrant"}[difference[0]]
        if measured[0][output]["value"] == measured[1][output]["value"]:
            raise ValueError("declared comparison difference absent from measured diagnostic")
        broken = dict(right, case_id=right_id + "_tampered", **{fixed[0]: "unreviewed_override"})
        try:
            audit_comparison(left, broken, fixed, difference)
        except SourceError as error:
            if "fixed condition changed" not in str(error):
                raise
        else:
            raise ValueError("fixed-condition negative did not reject")
        receipts.append({"comparison_id": comparison["comparison_id"], "case_ids": [left_id, right_id],
                         "fixed_modes": fixed, "deliberate_difference": difference[0],
                         "measurement_key": output, "source_hashes": {name: pair[0] for name, pair in source_hashes.items()},
                         "diagnostic_fixture": True, "physical_acceptance_claimed": False,
                         "legal_verdict_claimed": False})
    target = HERE / "comparison-audit-receipt.json"
    target.write_text(json.dumps({"format": "c135087-synthetic-comparison-audit",
                                  "comparisons": receipts, "count": len(receipts)}, indent=2) + "\n")
    print("seven selected synthetic comparisons source-bound; original physical and legal review pending")


if __name__ == "__main__":
    audit()
