"""Regenerate exact source-gated constructions for the three selected cases.

This writes only the assignment's final textual bundle files. Native source
packets are intentionally supplied later by local reviewed source intake.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from delivery_audit import CASES
from native_observation import CAMERA_DIMENSIONS

ROOT = Path(__file__).resolve().parent
MODULES = (
    "runner.py", "analysis.py", "native_entry.py", "reviewed_site.py", "site_geometry.py",
    "native_observation.py", "native_route.py", "owned_capture.py",
    "carla_readback.py", "saved_camera_audit.py", "video_sources.py",
    "delivery_audit.py", "comparison_audit.py", "walker_pipeline_capture.py",
)
OFFLINE_TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class ExactCaseOffline(unittest.TestCase):
    def test_source_gated_static_bundle(self):
        root = Path(__file__).resolve().parents[1]
        selected = check(root)
        self.assertEqual(selected["case_id"], json.loads((root / "config.json").read_text())["selected_case_id"])
        self.assertEqual(selected["source_gate"], "reviewed original C111329 site required before Native")

if __name__ == "__main__":
    unittest.main()
'''


def _write(path: Path, value) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries = []
    case_ids = list(CASES)
    for case_id, (marked, operating) in CASES.items():
        short = case_id.split("__")[-1]
        folder = ROOT / "cases" / short
        camera = [{"name": name, "width": dimensions[0], "height": dimensions[1],
                   "fov_deg": 75, "pose_strategy": "reviewed original between-intersection crossing site"}
                  for name, dimensions in CAMERA_DIMENSIONS.items()]
        description = {"channels": [
            {"name": "walker_crossing_route", "unit": "m",
             "method": "original walker body centers and bank crossing order",
             "time_window": "all original frames", "sampling_rate_hz": 20,
             "reference_frame": "reviewed site world XY", "uncertainty": "physical realization pending"},
            {"name": "device_operation", "unit": "state",
             "method": "original two-device actor state and is_frozen health readback",
             "time_window": "all original frames", "sampling_rate_hz": 20,
             "reference_frame": "source device identities", "uncertainty": "legal official status unresolved"},
            {"name": "marking_and_junction_context", "unit": "source",
             "method": "reviewed original site and complete marking survey",
             "time_window": "all original frames", "sampling_rate_hz": 20,
             "reference_frame": "source junction and crossing station",
             "uncertainty": "legal adjacency and NRS 484B.290 exception unresolved"}],
            "context_inputs": [{"name": "highway_and_exception_review", "unit": "source",
                                "method": "separately reviewed original records"}],
            "limitations": ["Source record IDs are not legal conclusions."]}
        config = {"law_id": "NRS-484B-287-1c", "cell_id": "C111329",
                  "actor": "pedestrian", "selected_case_id": case_id,
                  "supported_case_ids": case_ids, "rate_hz": 20, "duration_s": 45,
                  "required_atoms": [], "source_packets": [], "cameras": camera,
                  "requested_speed_mps": 1.2,
                  "physical_completion": {"criterion": "travel_progress",
                      "minimum_progress_m": 6.0,
                      "completion_goal_method": "engineering route progress plus independent two-bank crossing audit; not legal cutoff"},
                  "case": {"case_id": case_id,
                      "physical_target": "source-grounded crossing between two device-controlled junctions",
                      "recording_description": description}}
        spec = {"case_id": case_id, "law_id": "NRS-484B-287-1c",
                "cell_id": "C111329", "actor": "pedestrian",
                "marked_crosswalk_present": marked,
                "both_devices_operating": operating,
                "source_status": "reviewed original site required before Native",
                "legal_adjacency": "undetermined",
                "legal_official_status": "undetermined",
                "nrs_484b_290_exception": "undetermined"}
        _write(folder / "config.json", config)
        _write(folder / "case-spec.json", spec)
        for candidate, speed in (("primary", 1.2), ("fallback1", 0.8)):
            controller = {"walker_speed_mps": speed,
                          "source": "predeclared engineering route-control alternative",
                          "physical_acceptance": False}
            _write(folder / ("controller-" + candidate + ".json"), controller)
            files = [{"path": name, "source": str((ROOT / name).relative_to(ROOT.parents[1])),
                      "content": (ROOT / name).read_text()} for name in MODULES]
            for name, value in (("config.json", config), ("case-spec.json", spec),
                                ("controller.json", controller)):
                files.append({"path": name, "source": str((folder / name).relative_to(ROOT.parents[1])),
                              "content": json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"})
            files.append({"path": "tests/test_offline.py", "source": "embedded exact offline contract",
                          "content": OFFLINE_TEST})
            construction = {"law_id": "NRS-484B-287-1c", "cell_id": "C111329",
                "actor": "pedestrian", "case_id": case_id, "entrypoint": "runner.py",
                "files": files, "recording_description": description,
                "measurement_plan": {"selected_requirement": "NRS 484B.287(1)(c)",
                    "original_source": "reviewed two-junction map, official-device and marking records",
                    "saved_method": "900 original walker/device frames joined to four full camera streams"},
                "static_checks": ["exact case and 20 Hz four-camera profile",
                    "source-gated Native review required before world mutation"],
                "termination_rules": {"duration_s": 45,
                    "early_termination": "retain failed attempt with original source hashes"}}
            name = "construction.json" if candidate == "primary" else candidate + "-construction.json"
            digest = _write(folder / name, construction)
            if candidate == "primary":
                entry = {"case_id": case_id,
                    "construction": str((folder / name).relative_to(ROOT)),
                    "construction_sha256": digest,
                    "kind": "delivery", "measurement_procedure": {"entrypoint": "analysis.py"},
                    "candidate_risk": {"status": "physical",
                        "reason": "Walker route and four-camera body visibility may fail in the reviewed two-junction Native site"},
                    "fixture_recipe": str((folder / "fixture-recipe.json").relative_to(ROOT.parents[1])),
                    "measurement_contract": str((folder / "measurement-contract.json").relative_to(ROOT)),
                    "acquisition": {name: {"entrypoint": "native_entry.py", "method": "run_native",
                        "evidence": ["original-site-observation.json", "trace.jsonl",
                                     "video_frames.jsonl", "effective-site-packet.json"]}
                        for name in ("walker_crossing_route", "device_operation",
                                     "marking_and_junction_context")},
                    "candidates": []}
            else:
                entry["candidates"].append({"id": "fallback1",
                    "construction": str((folder / name).relative_to(ROOT)),
                    "construction_sha256": digest,
                    "trigger": {"source": "original walker route and four-camera frame audit",
                        "metric": "walker waypoint overshoot or frame loss",
                        "failure_condition": "primary speed overshoots the same route or loses camera synchronization"},
                    "changed_knobs": ["walker requested speed 1.2 to 0.8 m/s on unchanged route"]})
        entries.append(entry)
    _write(ROOT / "execution-manifest.draft.json", {
        "format": "worker-execution-manifest-draft", "assignment_id": ROOT.name,
        "runtime_manifest_sha256": "5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3",
        "status": "original_reviewed_site_and_selected_proofs_pending",
        "cases": entries})
    return entries


if __name__ == "__main__":
    print(json.dumps({"cases": len(build()), "status": "source-gated draft"}))
