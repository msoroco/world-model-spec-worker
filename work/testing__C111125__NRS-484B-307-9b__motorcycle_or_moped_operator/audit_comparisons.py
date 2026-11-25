"""Check selected diagnostic contrasts from independent compatibility receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


FOLDER = Path(__file__).resolve().parent


def read(path: Path):
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value(proof, key):
    return proof["measurement_examples"][key]["value"]


def main() -> None:
    selected = sys.argv[1] if len(sys.argv) > 1 else None
    manifest = read(FOLDER / "execution-manifest.json")
    plan = read(FOLDER / "case-plan.json")
    entries = {item["case_id"]: item for item in manifest["cases"]}
    proofs = {}
    for case, entry in entries.items():
        path = FOLDER / entry["compatibility"]["receipt"]
        assert sha(path) == entry["compatibility"]["sha256"]
        proof = read(path)
        assert proof["case_id"] == case and proof["passed"] is True
        proofs[case] = (path, proof)
    expected = {
        "complete_cycle_count": (2, 1),
        "complete_cycle_count_above": (2, 3),
        "stopping_event": (0, None),
        "causal_record": (True, False),
        "crosswalk_yield": ([], ["adjacent_crosswalk"]),
        "intersection_yield": ([], ["intersection"]),
    }
    results = []
    for comparison in plan["comparisons"]:
        ident = comparison["comparison_id"]
        if selected is not None and ident != selected:
            continue
        first, second = comparison["case_ids"]
        left, right = proofs[first][1], proofs[second][1]
        if ident.startswith("complete_cycle_count"):
            observed = (value(left, "complete_cycles")["full_cycles_after_stop"],
                        value(right, "complete_cycles")["full_cycles_after_stop"])
        elif ident == "stopping_event":
            observed = (value(left, "source_ranked_stop")["stopped_frame"],
                        value(right, "source_ranked_stop")["stopped_frame"])
        elif ident == "causal_record":
            observed = (value(left, "unchanged_signal_cause")["source_established"],
                        value(right, "unchanged_signal_cause")["source_established"])
        else:
            observed = (value(left, "participant_yield_context")["regions"],
                        value(right, "participant_yield_context")["regions"])
        assert observed == expected[ident], (ident, observed)
        assert all(value(proof, "synchronized_four_view_media")["same_frame_history"] == 900
                   for proof in (left, right))
        assert all(value(proof, "motorcycle_actor")["blueprint_id"] == "vehicle.motorcycle"
                   for proof in (left, right))
        assert all(value(proof, "official_composite_head")["official_head_id"] == "head-17"
                   for proof in (left, right))
        assert all(value(proof, "participant_yield_context")["lawful_status"] == "unresolved"
                   for proof in (left, right))
        results.append({"comparison_id": ident, "case_ids": [first, second],
                        "observed_difference": observed, "expected_difference": expected[ident],
                        "fixed_diagnostic_conditions": ["900 same-frame four-view frames",
                                                        "motorcycle blueprint", "official head"],
                        "receipt_sha256": {case: sha(proofs[case][0]) for case in (first, second)},
                        "physical_acceptance_claimed": False,
                        "legal_acceptance_claimed": False})
    if selected is not None and len(results) != 1:
        raise ValueError("Unknown exact comparison")
    if selected is None:
        out = FOLDER / "comparison-audit-diagnostic.json"
        out.write_text(json.dumps({"format": "worker-diagnostic-comparison-audit",
                                   "assignment_id": FOLDER.name, "comparisons": results,
                                   "scope": "synthetic software contrast only; source-gated lawful-status sweeps remain unresolved"},
                                  indent=2, sort_keys=True) + "\n")
    print("passed", len(results), "diagnostic comparisons")


if __name__ == "__main__":
    main()
