"""Exercise physical and lifecycle checks for all accepted diagnostic cases."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

from physical_completion import assess
from prove_physical_preparation import EVENTS, capture, lifecycle


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove() -> dict:
    manifest_path = HERE / "execution-manifest.diagnostic.json"
    manifest = json.loads(manifest_path.read_text())
    scratch_root = ROOT / ".runtime-work" / "c158208-all-physical-diagnostic"
    scratch_root.mkdir(parents=True, exist_ok=True)
    cases = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        kind = case_id.rsplit("__", 1)[-1]
        outcomes = {}
        with tempfile.TemporaryDirectory(prefix=kind + "-", dir=scratch_root) as temp:
            for fixture, expected in (("complete_motion", "met"),
                                      ("incomplete_motion", "not_met"),
                                      ("missing_evidence", "unverified")):
                attempt = Path(temp) / fixture
                attempt.mkdir()
                if fixture != "missing_evidence":
                    capture(attempt, incomplete=fixture == "incomplete_motion")
                result = assess(attempt, case_id, entry["construction_sha256"],
                                diagnostic_fixture=True)
                status = result["physical_checks"]["maneuver"]["status"]
                if status != expected or result["provenance_kind"] != "synthetic_fixture":
                    raise ValueError("physical fixture outcome differs: " + kind + " " + fixture)
                if fixture == "missing_evidence":
                    if "reason" not in result["physical_checks"]["maneuver"]:
                        raise ValueError("missing sealed source has no failure reason")
                    result["physical_checks"]["maneuver"]["reason"] = "sealed source absent"
                outcomes[fixture] = result
        lifecycle(EVENTS)
        try:
            lifecycle([event for event in EVENTS if event != "owner_released"])
        except ValueError:
            pass
        else:
            raise ValueError("saved stage without Native owner release was accepted")
        receipt = {"format": "c158208-diagnostic-physical-receipt-v1",
                   "case_id": case_id,
                   "construction_sha256": entry["construction_sha256"],
                   "provenance_kind": "synthetic_fixture",
                   "fixture_outcomes": outcomes,
                   "owner_release_order_checked": True,
                   "missing_owner_release_rejected": True,
                   "physical_acceptance_claimed": False}
        target = HERE / ("diagnostic-physical-" + kind + ".json")
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        cases.append({"case_id": case_id, "construction_sha256": entry["construction_sha256"],
                      "receipt": target.name, "receipt_sha256": sha(target)})
    index = {"format": "c158208-diagnostic-physical-index-v1",
             "assignment_id": HERE.name,
             "manifest_sha256": sha(manifest_path),
             "diagnostic_only": True,
             "case_proofs": cases,
             "physical_acceptance_claimed": False,
             "legal_acceptance_claimed": False}
    target = HERE / "diagnostic-physical-index-all.json"
    target.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    print(f"{len(cases)} exact synthetic physical triads and lifecycle negatives passed")
    return index


if __name__ == "__main__":
    prove()
