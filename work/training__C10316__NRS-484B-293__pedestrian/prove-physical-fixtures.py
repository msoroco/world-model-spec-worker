"""Prove complete, wrong-half and missing-source diagnostic branches."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

from physical_fixture_audit import evaluate
from physical_outcome_audit import sha


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + "__reference"


def run() -> dict:
    attempt = ROOT / ".runtime-work/c10316-current-reference-primary-compat"
    complete = evaluate(attempt, CASE, test_shape=True)
    incomplete = evaluate(attempt, CASE, test_shape=True, expected_half="left")
    with tempfile.TemporaryDirectory() as folder:
        missing = evaluate(Path(folder), CASE, test_shape=True)
    branches = {"complete_motion": complete, "incomplete_motion": incomplete,
                "missing_evidence": missing}
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}
    for name, result in branches.items():
        check = result["physical_checks"]["maneuver"]
        if (check["status"] != "unverified" or
                check["source_shaped_status"] != expected[name] or
                check["maneuver_completed"] or
                result["provenance_kind"] != "source_shaped_unit_test" or
                result["realized_observables"] is not None):
            raise AssertionError("Diagnostic fixture promoted: " + name)
    try:
        evaluate(attempt, CASE)
    except ValueError as error:
        if "Synthetic or unsealed" not in str(error):
            raise
    else:
        raise AssertionError("Synthetic source accepted in production")
    report = {"format": "c10316-physical-fixture-cpu-proof-v1",
              "auditor_sha256": sha(HERE / "physical_fixture_audit.py"),
              "source_attempt": str(attempt.relative_to(ROOT)),
              "branches": branches,
              "synthetic_production_rejected": True,
              "original_native_motion_proven": False,
              "manifest_binding": False}
    path = HERE / "update023-physical-fixture-cpu-proof.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"branches": {name: value["physical_checks"]["maneuver"]["source_shaped_status"]
                                   for name, value in branches.items()},
                      "native_statuses": [value["physical_checks"]["maneuver"]["status"]
                                          for value in branches.values()],
                      "proof_sha256": sha(path)}))
    return report


if __name__ == "__main__":
    run()
