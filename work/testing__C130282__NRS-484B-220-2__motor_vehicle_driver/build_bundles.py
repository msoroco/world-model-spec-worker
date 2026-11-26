"""Build four exact source-gated island candidates and shared bounded fallback."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from island_source import CAMERAS, DIMENSIONS

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MODULES = ("runner.py", "analysis.py", "island_source.py", "island_measurements.py",
           "native_island.py", "native_island_entry.py", "capture_island.py",
           "carla_island_readback.py", "island_video_sources.py")
OFFLINE_TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class ExactIslandOffline(unittest.TestCase):
    def test_source_gated_static_bundle(self):
        root = Path(__file__).resolve().parents[1]
        selected = check(root)
        self.assertEqual(selected["case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])
        self.assertIn("reviewed original", selected["source_gate"])

if __name__ == "__main__":
    unittest.main()
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return sha(path)


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    entries = []
    case_ids = [case["case_id"] for case in plan["cases"]]
    for index, case in enumerate(plan["cases"]):
        cid = case["case_id"]
        tag = cid.split("__")[-1]
        lane, side = tag.split("_")
        folder = ROOT if index == 0 else ROOT / "cases" / tag
        description = {"channels": [
            {"name": name, "unit": "structured", "method": "SHA-verified original Native island readback",
             "sampling_rate_hz": 20, "time_window": "900 original frames",
             "reference_frame": "reviewed Native island map XY", "uncertainty": "physical and legal review pending"}
            for name in ("original_body_polygon", "original_heading", "observed_lane",
                         "island_side_and_overlap", "four_camera_frames")],
            "context_inputs": [{"name": "reviewed_island_source", "unit": "source",
                "method": "independently reviewed original island identity, physical polygon, Native map and routes"}],
            "limitations": ["Sampled geometry does not prove continuous between-frame island side or legal judgment."]}
        config = {"assignment_id": ROOT.name, "law_id": "NRS-484B-220-2", "cell_id": "C130282",
            "actor": "motor_vehicle_driver", "selected_case_id": cid,
            "supported_case_ids": case_ids, "circulation_lane_role": lane,
            "requested_island_side": side, "required_atoms": [], "source_packets": [],
            "plan_sha256": sha(ROOT / "case-plan.json"), "rate_hz": 20, "duration_s": 45,
            "physical_completion": {"criterion": "travel_progress", "motion_source": "trace.jsonl",
                "position_key": "position_m", "minimum_progress_m": 1.0, "minimum_samples": 3,
                "engineering_tolerances_not_legal": True,
                "completion_goal_method": "Original vehicle displacement is an engineering check; actual right-of-island passage, lane connection and legal status require source review"},
            "cameras": [{"name": name, "width": DIMENSIONS[name][0], "height": DIMENSIONS[name][1],
                         "fov_deg": 75, "pose_strategy": "reviewed fixed original island passage visibility"}
                        for name in CAMERAS],
            "case": {"case_id": cid, "recording_description": description}}
        for candidate, throttle in (("primary", .35), ("fallback1", .2)):
            candidate_folder = folder if candidate == "primary" else ROOT / "cases" / tag / "fallback1"
            controller = {"throttle": throttle, "source": "bounded predeclared route-control alternative",
                          "physical_acceptance": False}
            config_path, controller_path = candidate_folder / "config.json", candidate_folder / "controller.json"
            write(config_path, config)
            write(controller_path, controller)
            files = [{"path": name, "source": (ROOT / name).relative_to(REPO).as_posix(),
                      "content": (ROOT / name).read_text(encoding="utf-8")} for name in MODULES]
            for name, source in (("config.json", config_path), ("controller.json", controller_path)):
                files.append({"path": name, "source": source.relative_to(REPO).as_posix(),
                              "content": source.read_text(encoding="utf-8")})
            files.append({"path": "tests/test_offline.py", "content": OFFLINE_TEST})
            construction = {"law_id": "NRS-484B-220-2", "cell_id": "C130282",
                "actor": "motor_vehicle_driver", "case_id": cid, "entrypoint": "runner.py",
                "files": files, "recording_description": description,
                "measurement_plan": {"selected_requirement": "NRS 484B.220(2)",
                    "original_source": "reviewed rotary traffic island identity, physical polygon, connected inner/outer routes and motor driver",
                    "saved_method": "900 source-bound body, heading, lane and four-camera frames; sample local side and footprint overlap"},
                "static_checks": ["exact island source and plan hash", "source-selected connected lane role",
                                  "20 Hz four-camera original frame join"],
                "termination_rules": {"duration_s": 45,
                    "early_termination": "retain failed attempt; never publish as completed"}}
            construction_path = candidate_folder / "construction.json"
            digest = write(construction_path, construction)
            if candidate == "primary":
                entry = {"case_id": cid, "kind": "delivery",
                    "construction": construction_path.relative_to(ROOT).as_posix(),
                    "construction_sha256": digest,
                    "fixture_recipe": (ROOT / "cases" / tag / "fixture-recipe.json").relative_to(REPO).as_posix(),
                    "measurement_contract": (ROOT / "cases" / tag / "measurement-contract.json").relative_to(ROOT).as_posix(),
                    "measurement_procedure": {"entrypoint": "analysis.py"},
                    "native_handoff": {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
                                       "port_env_var": "CARLA_PORT", "source_env_var": "C130282_ISLAND_REVIEW"},
                    "acquisition": {name: {"entrypoint": "native_island_entry.py",
                        "method": "run_native", "evidence": ["original-map.json", "original-trace.jsonl",
                        "original-receipt.json", "trace.jsonl", "video_frames.jsonl"]}
                        for name in ("original_body_polygon", "original_heading", "observed_lane",
                                     "island_side_and_overlap", "four_camera_frames")},
                    "candidate_risk": {"status": "physical",
                        "reason": "Reviewed circulation route tracking or original camera synchronization can fail"},
                    "candidates": []}
                entry["acquisition"]["reviewed_island_source"] = {"entrypoint": "island_source.py",
                    "method": "load_reviewed", "evidence": ["original-map.json", "original-receipt.json"]}
            else:
                entry["candidates"].append({"id": "fallback1",
                    "construction": construction_path.relative_to(ROOT).as_posix(),
                    "construction_sha256": digest,
                    "trigger": {"source": "original route and four-camera frame audit",
                        "metric": "route cross-track deviation or missing synchronized original camera frame",
                        "failure_condition": "primary exceeds 4 m engineering route tracking bound or loses a camera frame"},
                    "changed_knobs": ["controller throttle 0.35 to 0.20 on unchanged reviewed route"]})
        entries.append(entry)
    write(ROOT / "execution-manifest.json", {"format": "worker-execution-manifest",
        "assignment_id": ROOT.name,
        "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
        "cases": entries, "comparisons": plan["comparisons"]})
    return len(entries)


if __name__ == "__main__":
    print(build())
