"""Materialize exact C135087 Native bundles for current-hash CPU offline proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
CASES = ("cargo_active", "cargo_inactive", "passenger_active",
         "passenger_inactive", "opposite_side_control")
CAMERAS = [("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]
BUNDLE_TEST = '''import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner
from native_capture import validate_survey

class BundleTests(unittest.TestCase):
    def test_exact_identity(self):
        self.assertEqual(runner.check(), json.loads(Path("config.json").read_text())["selected_case_id"])

    def test_native_source_gate_precedes_carla_import(self):
        with patch("sys.argv", ["runner.py", "--host", "localhost", "--port", "2000", "--output-dir", "attempt"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(ValueError, "source-hashed reviewed site"):
                    runner.main()

    def test_unreviewed_site_rejected(self):
        with self.assertRaisesRegex(ValueError, "reviewed C135087"):
            validate_survey({}, json.loads(Path("config.json").read_text())["selected_case_id"])

if __name__ == "__main__":
    unittest.main()
'''


def dump(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(plan_bytes)
    exact = {row["case_id"] for row in plan["cases"]}
    entries = []
    for kind in CASES:
        case = AID + "__" + kind
        if case not in exact:
            raise ValueError("exact plan case absent")
        config = {
            "assignment_id": AID, "law_id": "NRS-484B-153-3", "cell_id": "C135087",
            "actor": "motor_vehicle_driver", "selected_case_id": case,
            "supported_case_ids": sorted(exact), "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
            "rate_hz": 20, "duration_s": 45, "required_atoms": [], "source_packets": [],
            "cameras": [{"name": name, "width": width, "height": height,
                         "fov_deg": 80, "pose_strategy": "original door, loading actor and passing body"}
                        for name, width, height in CAMERAS],
            "case": {"case_id": case}, "door_open_tick": 120}
        channels = [{"name": item["name"], "unit": "structured", "sampling_rate_hz": 20,
                     "method": "source-sealed original Native readback", "time_window": "all 900 ticks",
                     "reference_frame": "original CARLA world", "uncertainty": "physical visibility pending"}
                    for item in plan["observations"]]
        description = {"channels": channels, "context_inputs": [{"name": "reviewed_narrow_road_site",
                         "unit": "source", "method": "source-hashed original map, loading position and passing route"}],
                       "limitations": ["Necessity and immediacy remain legal judgments; diagnostic fixtures are not physical evidence."]}
        config["case"]["recording_description"] = description
        for candidate, open_tick in (("primary", 120), ("fallback1", 100)):
            config["door_open_tick"] = open_tick
            content = {"runner.py": (HERE / "runner.py").read_text(),
                       "native_capture.py": (HERE / "native_capture.py").read_text(),
                       "door_measurement.py": (HERE / "door_measurement.py").read_text(),
                       "analysis.py": (HERE / "analysis.py").read_text(),
                       "case-plan.json": plan_bytes.decode(),
                       "config.json": json.dumps(config, sort_keys=True, indent=2) + "\n",
                       "tests/test_bundle.py": BUNDLE_TEST}
            construction = {
                "law_id": "NRS-484B-153-3", "cell_id": "C135087", "actor": "motor_vehicle_driver",
                "case_id": case, "entrypoint": "runner.py", "recording_description": description,
                "measurement_plan": {"case_id": case, "source_packets": ["frame_map", "door", "activity", "passing_vehicle", "geometry"],
                                     "procedure": "door_measurement.py", "legal_judgment": "unresolved"},
                "static_checks": ["exact source hashes", "case identity", "20 Hz clock", "door articulation and loading actor readback"],
                "termination_rules": ["900 original 20 Hz ticks", "door closure readback after loading"],
                "mechanisms": ["reviewed narrow-road survey", "source-hashed Native operator", "independent original door and loading observation", "four synchronized original RGB cameras"],
                "files": [{"path": path, "content": data} for path, data in content.items()]}
            path = HERE / "cases" / kind / ("construction.json" if candidate == "primary" else "fallback1/construction.json")
            dump(path, construction)
            if kind == CASES[0] and candidate == "primary":
                dump(HERE / "config.json", config)
                dump(HERE / "construction.json", construction)
            if candidate == "primary":
                entry = {"case_id": case, "kind": "delivery", "construction": str(path.relative_to(HERE)),
                         "construction_sha256": sha(path), "candidate_risk": {"status": "physical",
                         "reason": "Native door articulation or loading actor motion may not complete during the reviewed open window."},
                         "measurement_procedure": {"entrypoint": "analysis.py", "method": "saved original source measurement"},
                         "native_handoff": {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                         "candidates": []}
                entries.append(entry)
            else:
                entries[-1]["candidates"].append({"id": "fallback1", "construction": str(path.relative_to(HERE)),
                    "construction_sha256": sha(path), "changed_knobs": ["request reviewed door opening at tick 100 instead of tick 120; all comparison members share the same fallback"],
                    "trigger": {"source": "original door articulation frame map", "metric": "observed open readback by tick 120",
                                "failure_condition": "primary door does not articulate before tick 120"}})
    import hashlib as _hashlib
    runtime_sha = sha(HERE.parents[1] / "runtime" / "SOURCE-MANIFEST.json")
    dump(HERE / "execution-manifest.json", {"format": "worker-execution-manifest", "assignment_id": AID,
                                              "runtime_manifest_sha256": runtime_sha, "cases": entries})
    return len(entries)


if __name__ == "__main__":
    print(build())
