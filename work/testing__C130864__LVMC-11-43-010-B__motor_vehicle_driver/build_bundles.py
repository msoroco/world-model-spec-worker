"""Regenerate six exact source-gated roundabout construction candidates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from capture_roundabout import CAMERA_DIMENSIONS

ROOT = Path(__file__).resolve().parent
MODULES = ("runner.py", "analysis.py", "native_entry.py", "reviewed_roundabout.py",
           "native_roundabout.py", "capture_roundabout.py",
           "carla_roundabout_readback.py", "roundabout_measurements.py",
           "saved_roundabout_camera_audit.py", "roundabout_delivery_audit.py",
           "roundabout_video_sources.py")
OFFLINE_TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class ExactCaseOffline(unittest.TestCase):
    def test_source_gated_static_bundle(self):
        root = Path(__file__).resolve().parents[1]
        selected = check(root)
        self.assertEqual(selected["case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])
        self.assertIn("reviewed original", selected["source_gate"])

if __name__ == "__main__":
    unittest.main()
'''


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    case_ids = [case["case_id"] for case in plan["cases"]]
    entries = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        folder = ROOT / "cases" / case_id.split("__")[-1]
        cameras = [{"name": name, "width": size[0], "height": size[1],
                    "fov_deg": 75,
                    "pose_strategy": "reviewed original roundabout entry and circulating path"}
                   for name, size in CAMERA_DIMENSIONS.items()]
        description = {"channels": [
            {"name": "ego_roundabout_entry", "unit": "frame",
             "method": "original ego body vertices and ring occupancy at 20 Hz",
             "sampling_rate_hz": 20, "time_window": "900 original frames",
             "reference_frame": "reviewed Native map XY", "uncertainty": "physical realization pending"},
            {"name": "circulating_vehicle_presence", "unit": "state",
             "method": "original opponent route lane and ring occupancy",
             "sampling_rate_hz": 20, "time_window": "900 original frames",
             "reference_frame": "reviewed Native map XY", "uncertainty": "physical realization pending"},
            {"name": "entry_conflict_motion", "unit": "m",
             "method": "original eight-vertex body separation and conflict occupancy",
             "sampling_rate_hz": 20, "time_window": "900 original frames",
             "reference_frame": "reviewed Native map XY", "uncertainty": "legal right-of-way unresolved"},
            {"name": "observed_preentry_gap", "unit": "s",
             "method": "original synchronized body and speed histories before entry",
             "sampling_rate_hz": 20, "time_window": "900 original frames",
             "reference_frame": "reviewed Native map XY", "uncertainty": "no legal numeric gap threshold"}],
            "context_inputs": [{"name": "reviewed_roundabout_source", "unit": "source",
                                "method": "source-hashed jurisdiction, map, lanes and routes"}],
            "limitations": ["Source-backed motion is not a legal gap judgment."]}
        config = {"law_id": "LVMC-11-43-010-B", "cell_id": "C130864",
                  "actor": "motor_vehicle_driver", "selected_case_id": case_id,
                  "supported_case_ids": case_ids, "required_atoms": [], "source_packets": [],
                  "rate_hz": 20, "duration_s": 45, "cameras": cameras,
                  "physical_completion": {"criterion": "travel_progress",
                      "motion_source": "trace.jsonl", "position_key": "position_m",
                      "minimum_progress_m": 1.0, "minimum_samples": 3,
                      "engineering_tolerances_not_legal": True,
                      "completion_goal_method": "Original ego displacement is an engineering motion check; roundabout entry, observed waiting, circulating right-of-way and legal gap require independent source-bound review"},
                  "case": {"case_id": case_id,
                      "physical_target": "source-grounded multilane entry and already-present circulating vehicle",
                      "recording_description": description}}
        spec = {"case_id": case_id, "law_id": "LVMC-11-43-010-B",
                "cell_id": "C130864", "actor": "motor_vehicle_driver",
                "opponent_lane_relation": case["opponent_lane_relation"],
                "planned_gap_condition": case["planned_gap_condition"],
                "ego_entry_request": case["ego_entry_request"],
                "source_status": "reviewed original map, routes, jurisdiction and camera placement required",
                "legal_gap_judgment": "unresolved"}
        _write(folder / "config.json", config)
        _write(folder / "case-spec.json", spec)
        for candidate, throttle in (("primary", .35), ("fallback1", .2)):
            controller = {"throttle": throttle,
                "source": "predeclared bounded route-control alternative",
                "physical_acceptance": False}
            source_name = "controller-" + candidate + ".json"
            _write(folder / source_name, controller)
            files = [{"path": name, "source": str((ROOT / name).relative_to(ROOT.parents[1])),
                      "content": (ROOT / name).read_text()} for name in MODULES]
            for name, value, source in (("config.json", config, folder / "config.json"),
                                        ("case-spec.json", spec, folder / "case-spec.json"),
                                        ("controller.json", controller, folder / source_name)):
                files.append({"path": name, "source": str(source.relative_to(ROOT.parents[1])),
                              "content": json.dumps(value, indent=2, sort_keys=True) + "\n"})
            files.append({"path": "tests/test_offline.py", "content": OFFLINE_TEST})
            construction = {"law_id": "LVMC-11-43-010-B", "cell_id": "C130864",
                "actor": "motor_vehicle_driver", "case_id": case_id,
                "entrypoint": "runner.py", "files": files,
                "recording_description": description,
                "measurement_plan": {"selected_requirement": "LVMC 11.43.010(B)",
                    "original_source": "reviewed multilane roundabout, entry and circulating routes",
                    "saved_method": "900 source-bound vehicle frames joined to 3600 decoded camera images"},
                "static_checks": ["exact case and 20 Hz four-camera profile",
                    "reviewed Native source required before world mutation"],
                "termination_rules": {"duration_s": 45,
                    "early_termination": "retain failed original attempt; do not publish as completed"}}
            name = "construction.json" if candidate == "primary" else "fallback1-construction.json"
            digest = _write(folder / name, construction)
            if candidate == "primary":
                entry = {"case_id": case_id,
                    "construction": str((folder / name).relative_to(ROOT)),
                    "construction_sha256": digest, "kind": "delivery",
                    "measurement_procedure": {"entrypoint": "analysis.py"},
                    "fixture_recipe": str((folder / "fixture-recipe.json").relative_to(ROOT.parents[1])),
                    "measurement_contract": str((folder / "measurement-contract.json").relative_to(ROOT)),
                    "acquisition": {name: {"entrypoint": "native_entry.py",
                        "method": "run_native", "evidence": ["original-map.json",
                            "original-trace.jsonl", "original-receipt.json",
                            "trace.jsonl", "video_frames.jsonl"]}
                        for name in ("ego_roundabout_entry", "circulating_vehicle_presence",
                                     "entry_conflict_motion", "observed_preentry_gap")},
                    "candidate_risk": {"status": "physical",
                        "reason": "Vehicle route tracking can overshoot the reviewed entry and lose camera synchronization"},
                    "candidates": []}
            else:
                entry["candidates"].append({"id": "fallback1",
                    "construction": str((folder / name).relative_to(ROOT)),
                    "construction_sha256": digest,
                    "trigger": {"source": "original route and four-camera frame audit",
                        "metric": "cross-track deviation or missing synchronized camera frame",
                        "failure_condition": "primary exceeds four-meter route tracking bound or loses a camera frame"},
                    "changed_knobs": ["controller throttle 0.35 to 0.20 on unchanged source route"]})
        entries.append(entry)
    _write(ROOT / "execution-manifest.draft.json", {
        "format": "worker-execution-manifest-draft", "assignment_id": ROOT.name,
        "runtime_manifest_sha256": "5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3",
        "status": "reviewed_original_roundabout_sources_and_proofs_pending",
        "cases": entries})
    return entries


if __name__ == "__main__":
    print(json.dumps({"cases": len(build()), "status": "source-gated draft"}))
