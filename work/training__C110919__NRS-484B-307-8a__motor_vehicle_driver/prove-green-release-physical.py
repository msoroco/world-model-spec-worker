"""CPU branch proof for the green-release physical-outcome checker."""
import copy
import hashlib
import json
from pathlib import Path

from green_release_physical import classify

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNS = ROOT / ".runtime-work/c110919-update027-green-matrix"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def status(result):
    return result["physical_checks"]["green_release_right_turn"]["status"]


def main():
    receipts = []
    for suffix in ("green_release_wait", "green_release_red_turn"):
        attempt = RUNS / suffix / "primary/compatibility"
        raw = attempt / "native_samples.jsonl"
        road = attempt / "road_geometry.json"
        synthetic = [json.loads(line) for line in raw.read_text().splitlines()]
        geometry = json.loads(road.read_text())
        if not all(row.get("synthetic_diagnostic") is True and
                   row.get("speed_provenance") == "synthetic_native_sample"
                   for row in synthetic) or geometry.get("synthetic_diagnostic") is not True:
            raise ValueError("Diagnostic source provenance changed")
        native_shaped = copy.deepcopy(synthetic)
        for row in native_shaped:
            row.pop("synthetic_diagnostic")
            row.pop("speed_provenance")
        native_geometry = copy.deepcopy(geometry)
        native_geometry.pop("synthetic_diagnostic")
        checks = {}
        checks["complete_mock"] = classify(native_shaped, native_geometry, suffix,
                                            provenance_kind="native", diagnostic_fixture=False)
        incomplete = copy.deepcopy(native_shaped)
        incomplete[-1]["native_center_xy_m"] = [8.0, -7.0]
        checks["incomplete_mock"] = classify(incomplete, native_geometry, suffix,
                                              provenance_kind="native", diagnostic_fixture=False)
        checks["missing_frame_mock"] = classify(native_shaped[:-1], native_geometry, suffix,
                                                 provenance_kind="native", diagnostic_fixture=False)
        changed = copy.deepcopy(native_shaped)
        changed[159]["signal_state_observed"] = "Green"
        checks["wrong_signal_mock"] = classify(changed, native_geometry, suffix,
                                                provenance_kind="native", diagnostic_fixture=False)
        checks["synthetic_diagnostic"] = classify(synthetic, geometry, suffix,
                                                   provenance_kind="synthetic_local_diagnostic",
                                                   diagnostic_fixture=True)
        checks["synthetic_spoofed_native"] = classify(synthetic, geometry, suffix,
                                                       provenance_kind="native", diagnostic_fixture=False)
        if suffix == "green_release_wait":
            changed = copy.deepcopy(native_shaped)
            changed[145]["speed_mps"] = .5
            checks["rolled_before_green_mock"] = classify(
                changed, native_geometry, suffix,
                provenance_kind="native", diagnostic_fixture=False)
        expected = {"complete_mock": "met", "incomplete_mock": "not_met",
                    "missing_frame_mock": "unverified", "wrong_signal_mock": "unverified",
                    "synthetic_diagnostic": "unverified",
                    "synthetic_spoofed_native": "unverified"}
        if suffix == "green_release_wait":
            expected["rolled_before_green_mock"] = "not_met"
        for name, outcome in checks.items():
            if status(outcome) != expected[name] or outcome["accepted"] is not False:
                raise AssertionError(suffix + " " + name + " physical branch differs")
        receipts.append({"case_id": HERE.name + "__" + suffix,
                         "source_sha256": {"native_samples.jsonl": sha(raw),
                                           "road_geometry.json": sha(road)},
                         "outcomes": {name: status(outcome) for name, outcome in checks.items()},
                         "cpu_fixture_mock": True,
                         "original_native_motion_verified": False})
    proof = {"format": "c110919-green-release-physical-cpu-proof-v1",
             "checker_sha256": sha(HERE / "green_release_physical.py"),
             "manifest_sha256": sha(HERE / "draft-green-release-execution-manifest.json"),
             "cases": receipts, "original_native_motion_verified": False,
             "accepted_recordings": 0}
    path = HERE / "update028-green-physical-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"cases": len(receipts), "cpu_branches": sum(len(x["outcomes"]) for x in receipts),
                      "proof_sha256": sha(path), "original_native_motion_verified": False}))


if __name__ == "__main__":
    main()
