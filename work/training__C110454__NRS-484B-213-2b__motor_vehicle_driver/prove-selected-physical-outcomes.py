"""Current-manifest CPU proof of physical outcomes and closure ordering."""
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from physical_outcome import check_lifecycle, classify
from physical_motion_audit import EXPECTED


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def rejects(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError("Invalid lifecycle accepted")


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    index = json.loads((HERE / "update025-selected-six-index.json").read_text())
    require(index["manifest_sha256"] == digest and len(index["results"]) == 24,
            "Current selected matrix missing")
    outcomes = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        row = next(item for item in index["results"] if item["case_id"] == case
                   and item["candidate_id"] == "primary")
        proof_path = HERE / row["proof"]
        require(hashlib.sha256(proof_path.read_bytes()).hexdigest() == row["sha256"],
                "Current chain proof changed")
        attempt = ROOT / ".runtime-work/c110454-update025-six-selected" / suffix / "primary/compatibility"
        samples = [json.loads(line) for line in (attempt / "native_samples.jsonl").read_text().splitlines()]
        survey = json.loads((attempt / "road_geometry.json").read_text())
        context_name = "context.json" if suffix.startswith("traversal_") else "statutory_context.json"
        context = json.loads((attempt / context_name).read_text())
        # Strip fixture markers only in this in-memory branch model. The retained
        # source files and their speed provenance remain explicitly synthetic.
        mock_native = copy.deepcopy(samples)
        for sample in mock_native:
            sample.pop("synthetic_diagnostic", None)
            sample.pop("speed_provenance", None)
        completed = classify(mock_native, survey, suffix, context,
                             provenance_kind="native", diagnostic_fixture=False)
        require(completed["physical_checks"]["maneuver"]["status"] == "met" and
                completed["maneuver_completed"] and
                completed["source_shaped_motion"]["observed_relation"] == EXPECTED[suffix],
                "Mock complete branch failed")
        changed = copy.deepcopy(mock_native)
        changed[-1]["speed_m_s"] = 1.0
        incomplete = classify(changed, survey, suffix, context,
                              provenance_kind="native", diagnostic_fixture=False)
        require(incomplete["physical_checks"]["maneuver"]["status"] == "not_met" and
                not incomplete["maneuver_completed"], "Incomplete branch failed")
        missing = classify(mock_native[:-1], survey, suffix, context,
                           provenance_kind="native", diagnostic_fixture=False)
        require(missing["physical_checks"]["maneuver"]["status"] == "unverified" and
                not missing["maneuver_completed"], "Missing-evidence branch failed")
        diagnostic = classify(samples, survey, suffix, context,
                              provenance_kind="synthetic_local_diagnostic",
                              diagnostic_fixture=True)
        require(diagnostic["physical_checks"]["maneuver"]["status"] == "unverified" and
                not diagnostic["maneuver_completed"], "Synthetic motion promoted")
        spoofed = classify(samples, survey, suffix, context,
                           provenance_kind="native", diagnostic_fixture=False)
        require(spoofed["physical_checks"]["maneuver"]["status"] == "unverified",
                "Synthetic markers accepted as Native")
        outcomes.append({"case_id": case, "construction_sha256": entry["construction_sha256"],
                         "mocked_complete": "met", "mocked_incomplete": "not_met",
                         "mocked_missing_evidence": "unverified",
                         "retained_diagnostic": "unverified", "spoofed_native": "unverified",
                         "source_sha256": {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                                           for name in ("native_samples.jsonl", "road_geometry.json", context_name)}})
    events = ["capture_finished", "encoders_closed", "restoration_verified",
              "native_exit", "owner_released", "saved_processing_started"]
    require(check_lifecycle(events, native_exit_code=0)["exit_code"] == 0,
            "Ordered closure rejected")
    rejects(lambda: check_lifecycle(events[:-2] + events[-1:] + events[-2:-1],
                                    native_exit_code=0))
    rejects(lambda: check_lifecycle(events, native_exit_code=1))
    proof = {"format": "c110454-selected-physical-outcomes-cpu-v1",
             "manifest_sha256": digest, "selected_cases": len(outcomes),
             "outcomes": outcomes, "lifecycle_order_tested": True,
             "lifecycle_rejections": ["saved_processing_before_release", "native_exit_failure"],
             "retained_sources_are_synthetic": True,
             "mocked_native_branch_only": True,
             "original_native_motion_verified": 0,
             "original_recordings_or_comparisons_accepted": 0,
             "physical_or_legal_acceptance_claimed": False}
    path = HERE / "update027-physical-outcomes-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"selected_cases": len(outcomes), "outcomes_per_case": 5,
                      "lifecycle_rejections": proof["lifecycle_rejections"],
                      "original_native_motion_verified": 0}))


if __name__ == "__main__":
    main()
