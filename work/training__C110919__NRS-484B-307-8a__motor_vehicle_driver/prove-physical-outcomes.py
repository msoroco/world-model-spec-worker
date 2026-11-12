"""Exercise physical branch outcomes for the selected-pair probe, without acceptance."""
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from physical_outcome import EVENTS, check_lifecycle, classify


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def must_reject(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError("Invalid lifecycle was accepted")


def main():
    manifest_path = HERE / "update017-selected-pair-probe-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if len(manifest["cases"]) != 2:
        raise ValueError("Two-case selected probe changed")
    output = HERE / "update018-physical-outcomes"
    receipts = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        if suffix not in ("reference", "contrast"):
            raise ValueError("Unexpected right-turn case")
        attempt = ROOT / ".runtime-work/c110919-update017-selected-pair-probe" / suffix / "primary/compatibility"
        raw = attempt / "native_samples.jsonl"
        road = attempt / "road_geometry.json"
        samples = [json.loads(line) for line in raw.read_text().splitlines()]
        geometry = json.loads(road.read_text())
        if not all(s.get("synthetic_diagnostic") is True and
                   s.get("speed_provenance") == "synthetic_native_sample" for s in samples):
            raise ValueError("Diagnostic source provenance changed")
        if geometry.get("synthetic_diagnostic") is not True:
            raise ValueError("Diagnostic road provenance changed")
        original_marked = copy.deepcopy(samples)
        for row in original_marked:
            row.pop("synthetic_diagnostic")
            row.pop("speed_provenance")
        original_road = copy.deepcopy(geometry)
        original_road.pop("synthetic_diagnostic")
        incomplete = copy.deepcopy(original_marked)
        incomplete[-1]["native_center_xy_m"] = [8.0, -7.0]
        outcomes = {
            "complete_motion": classify(original_marked, original_road,
                                        provenance_kind="native", diagnostic_fixture=False),
            "incomplete_motion": classify(incomplete, original_road,
                                          provenance_kind="native", diagnostic_fixture=False),
            "missing_evidence": classify(original_marked[:-1], original_road,
                                         provenance_kind="native", diagnostic_fixture=False),
        }
        for kind, expected in (("complete_motion", "met"),
                               ("incomplete_motion", "not_met"),
                               ("missing_evidence", "unverified")):
            result = outcomes[kind]
            if result["physical_checks"]["maneuver"]["status"] != expected or \
               result["maneuver_completed"] != (expected == "met"):
                raise AssertionError(f"{suffix} {kind} physical branch failed")
            result.update({"cpu_fixture_mock": True,
                           "mock_input_provenance": "synthetic_native_sample",
                           "original_native_motion_verified": False,
                           "construction_sha256": entry["construction_sha256"],
                           "retained_source_sha256": {"native_samples.jsonl": sha(raw),
                                                      "road_geometry.json": sha(road)}})
            path = output / suffix / (kind + ".json")
            save(path, result)
        diagnostic = classify(samples, geometry, provenance_kind="synthetic_local_diagnostic",
                              diagnostic_fixture=True)
        if diagnostic["physical_checks"]["maneuver"]["status"] != "unverified":
            raise AssertionError("Synthetic motion was promoted to physical")
        spoofed = classify(samples, geometry, provenance_kind="native", diagnostic_fixture=False)
        if spoofed["physical_checks"]["maneuver"]["status"] != "unverified":
            raise AssertionError("Source markers were ignored")
        life = check_lifecycle(EVENTS, 0)
        must_reject(lambda: check_lifecycle(EVENTS[-1:] + EVENTS[:-1], 0))
        must_reject(lambda: check_lifecycle(EVENTS, 1))
        save(output / suffix / "lifecycle.json", {**life, "cpu_fixture_mock": True,
                                                    "original_owner_release_verified": False})
        receipts.append({"case_id": entry["case_id"],
                         "construction_sha256": entry["construction_sha256"],
                         "source_sha256": {"native_samples.jsonl": sha(raw),
                                           "road_geometry.json": sha(road)},
                         "outcomes": {kind: {"path": str((output / suffix / (kind + ".json")).relative_to(HERE)),
                                              "sha256": sha(output / suffix / (kind + ".json"))}
                                      for kind in outcomes},
                         "lifecycle": {"path": str((output / suffix / "lifecycle.json").relative_to(HERE)),
                                       "sha256": sha(output / suffix / "lifecycle.json")},
                         "diagnostic_promoted": False, "original_native_motion_verified": False})
    proof = {"format": "c110919-selected-pair-physical-outcome-cpu-probe-v1",
             "manifest": manifest_path.name, "manifest_sha256": sha(manifest_path),
             "cases": receipts, "cpu_fixture_mock": True,
             "original_native_motion_verified": False,
             "accepted_recordings": 0}
    save(HERE / "update018-physical-outcome-proof.json", proof)
    print(json.dumps({"cases": len(receipts), "outcomes": 3 * len(receipts),
                      "proof_sha256": sha(HERE / "update018-physical-outcome-proof.json"),
                      "original_native_motion_verified": False}))


if __name__ == "__main__":
    main()
