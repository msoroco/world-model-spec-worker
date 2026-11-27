"""Bind selected comparison source bytes into exact inline Native constructions."""

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSIGNMENT = ROOT.name
CONDITIONS = {"a": "distance_triggered_slow_request", "b": "maintain_request"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base = json.loads((HERE / "draft-primary/config.json").read_text())
    runner = (HERE / "selected_runner.py").read_text()
    test = (HERE / "selected_offline_test.py").read_text()
    finalizer = (HERE / "finalize.py").read_text()
    saved = (HERE / "saved_due_care.py").read_text()
    meter = (HERE / "due_care_meter.py").read_text()
    cases = []
    channel_names = ("ru.pedestrian", "drv.time_to_conflict", "rel.contact",
                     "rel.surface_gap", "kin.speed", "drv.hard_deceleration",
                     "drv.vulnerable_road_user", "native_source_join")
    description = {"channels": [{"name": name, "unit": "structured",
                                  "sampling_rate_hz": 20,
                                  "method": "Original Native pose, collision event, survey and camera frame join",
                                  "time_window": "all 600 frames / 30 seconds",
                                  "reference_frame": "original Native frame and elapsed time",
                                  "uncertainty": "diagnostic value and actual pixels require independent review"}
                                 for name in channel_names],
                   "context_inputs": [{"name": "pedestrian_path_survey", "unit": "structured",
                                       "method": "copied original road and independent walking path survey"}],
                   "limitations": ["No diagnostic value defines legal due care",
                                   "CPU fixtures cannot establish original motion or physical completion"]}
    for condition, controller in CONDITIONS.items():
        case_id = ASSIGNMENT + "__selected_90e3f1aa__condition_" + condition
        config = copy.deepcopy(base)
        config.update(case_id=case_id, selected_case_id=case_id,
                      status="selected_cpu_construction_unverified",
                      controller=controller)
        config["comparison_variable"] = "pedestrian_conflict_response"
        config["comparison_condition"] = condition
        config["recording_description"] = description
        for camera, name in zip(config["cameras"],
                                ("overview", "approach", "reference_corner", "driver_reference")):
            camera["name"] = name
        construction = {
            "format": "worker-inline-construction", "case_id": case_id,
            "law_id": "NRS-484B-280-1a", "cell_id": "C230266",
            "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
            "files": [{"path": "runner.py", "content": runner},
                      {"path": "config.json", "content": json.dumps(config, indent=2) + "\n"},
                      {"path": "tests/test_offline.py", "content": test},
                      {"path": "finalize.py", "content": finalizer},
                      {"path": "saved_due_care.py", "content": saved},
                      {"path": "due_care_meter.py", "content": meter}],
            "recording_description": description,
            "status": "selected_cpu_construction_unverified"}
        path = HERE / ("selected-" + condition + "-construction.json")
        path.write_text(json.dumps(construction, indent=2) + "\n")
        cases.append({"case_id": case_id,
                      "construction": "native/selected-" + condition + "-construction.json",
                      "construction_sha256": sha(path), "candidates": [],
                      "candidate_risk": {"status": "physical",
                                         "reason": "Original pedestrian crossing, vehicle response and camera framing need Native review."}})
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": ASSIGNMENT, "status": "selected_offline_only",
                "cases": cases, "original_native_observed": False,
                "delivery_ready": False}
    manifest_path = ROOT / "selected-road-pedestrian-draft-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": [{"case_id": c["case_id"],
                                 "construction_sha256": c["construction_sha256"]} for c in cases],
                      "manifest_sha256": sha(manifest_path)}))


if __name__ == "__main__":
    main()
