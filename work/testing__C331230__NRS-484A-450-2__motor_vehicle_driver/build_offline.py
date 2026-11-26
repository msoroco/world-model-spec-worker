"""Build exact C331230 source-gated near-side crosswalk delivery bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
CASES = ("marked_crosswalk_halt", "marked_crosswalk_rolling",
         "unmarked_crosswalk_halt", "unmarked_crosswalk_rolling")
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
BUNDLE_TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner

class BundleTests(unittest.TestCase):
    def test_exact_case(self):
        self.assertEqual(runner.check()[0], json.loads((runner.HERE / "config.json").read_text())["selected_case_id"])

    def test_reviewed_sources_required_before_carla(self):
        with patch("sys.argv", ["runner.py", "--host", "localhost", "--port", "2000", "--output-dir", "attempt"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(ValueError, "source-hashed reviewed crosswalk site"):
                    runner.main()

if __name__ == "__main__":
    unittest.main()
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(plan_bytes)
    exact = {row["case_id"] for row in plan["cases"]}
    if exact != {AID + "__" + name for name in CASES}:
        raise ValueError("exact frozen near-side crosswalk case plan changed")
    source_files = ("runner.py", "native_capture.py", "native_output_bridge.py",
                    "near_crosswalk.py", "analysis.py", "case-plan.json")
    content = {name: (HERE / name).read_text() for name in source_files}
    (HERE / "tests/test_bundle.py").write_text(BUNDLE_TEST)
    entries = []
    for name in CASES:
        case = AID + "__" + name
        planned = next(row for row in plan["cases"] if row["case_id"] == case)
        channels = [{"name": source, "unit": "structured", "sampling_rate_hz": 20,
                     "method": "source-sealed original Native readback", "time_window": "all 900 ticks",
                     "reference_frame": "original CARLA map and world",
                     "uncertainty": "physical cessation, geometry and camera realization pending"}
                    for source in ("original_front_position", "physical_cessation",
                                   "governing_stop_sign", "near_side_crosswalk_boundary",
                                   "original_four_camera_pixels")]
        description = {"channels": channels,
                       "context_inputs": [{"name": "reviewed_crosswalk_site", "unit": "source",
                                           "method": "source-hashed intersection, sign and opposing sidewalk geometry"}],
                       "limitations": ["A cessation sample does not establish a minimum legal stop duration."]}
        config = {"assignment_id": AID, "law_id": "NRS-484A-450-2", "cell_id": "C331230",
                  "actor": "motor_vehicle_driver", "selected_case_id": case,
                  "supported_case_ids": sorted(exact),
                  "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
                  "rate_hz": 20, "duration_s": 45, "required_atoms": [], "source_packets": [],
                  "cameras": [{"name": view, "width": width, "height": height, "fov_deg": 80,
                              "pose_strategy": "source reviewed sign, near-side boundary and actor front"}
                              for view, width, height in CAMERAS],
                  "case": {"case_id": case, "recording_description": description}}
        for candidate, distance in (("primary", 12.0), ("fallback1", 18.0)):
            config["brake_distance_m"] = distance
            files = dict(content)
            files["config.json"] = json.dumps(config, sort_keys=True, indent=2) + "\n"
            files["tests/test_bundle.py"] = BUNDLE_TEST
            construction = {"law_id": "NRS-484A-450-2", "cell_id": "C331230",
                            "actor": "motor_vehicle_driver", "case_id": case,
                            "entrypoint": "runner.py", "recording_description": description,
                            "measurement_plan": {"case_id": case,
                                                 "source_packets": ["site", "history", "frame_map"],
                                                 "procedure": "analysis.py", "legal_judgment": "unresolved"},
                            "static_checks": ["reviewed map, sign, near-side sidewalk and controller source hashes",
                                              "900 original 20 Hz front/speed and four-view camera frames"],
                            "termination_rules": ["900 original Native ticks", "near-side crosswalk passage"],
                            "mechanisms": ["reviewed two-way intersection and stop sign",
                                           "source-hashed Native operator", "bounded brake-distance controller",
                                           "four synchronized RGB cameras"],
                            "files": [{"path": path, "content": data} for path, data in files.items()]}
            relative = Path("cases") / name / ("construction.json" if candidate == "primary"
                                               else "fallback1/construction.json")
            path = HERE / relative
            write(path, construction)
            if name == CASES[0] and candidate == "primary":
                write(HERE / "config.json", config)
                write(HERE / "construction.json", construction)
            if candidate == "primary":
                entries.append({"case_id": case, "kind": "delivery",
                                "construction": str(relative), "construction_sha256": sha(path),
                                "candidate_risk": {"status": "physical",
                                                   "reason": "Native braking may miss pre-entry cessation or camera visibility of the near-side boundary."},
                                "measurement_procedure": {"entrypoint": "analysis.py",
                                                          "method": "saved original front and cessation measurement"},
                                "acquisition": {channel["name"]: {
                                    "entrypoint": "analysis.py",
                                    "method": "Source-hashed original Native front, sign and crosswalk projection",
                                    "evidence": "channels/" + channel["name"] + ".jsonl"}
                                    for channel in channels},
                                "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                                "candidates": []})
            else:
                entries[-1]["candidates"].append({"id": "fallback1",
                    "construction": str(relative), "construction_sha256": sha(path),
                    "changed_knobs": ["brake approach distance 18 m instead of 12 m for all linked near-side cases"],
                    "trigger": {"source": "original 20 Hz front position and velocity history",
                                "metric": "front distance to near-side crosswalk at first measured cessation",
                                "failure_condition": "primary halt misses pre-entry cessation or rolling case stops before entry"}})
    write(HERE / "execution-manifest.json", {
        "format": "worker-execution-manifest", "assignment_id": AID,
        "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
        "cases": entries})
    return len(entries)


if __name__ == "__main__":
    print(build())
