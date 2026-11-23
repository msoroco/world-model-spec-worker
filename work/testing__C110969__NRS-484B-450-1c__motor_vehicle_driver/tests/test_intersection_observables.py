import importlib.util
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("intersection_observables", ROOT / "intersection_observables.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from comparison_audit import audit


BOUNDARY = {"map_id": "reviewed-map", "highway_status": "reviewed_highway",
            "joining_roadways": True, "boundary_method": "reviewed extension of roadway lateral lines",
            "intersection_polygon": [[0, 0], [10, 0], [10, 10], [0, 10]],
            "source_refs": [{"path": "original-map-packet", "sha256": "map-seal"}]}
ACTIVITY = {"activity_source": "original-observation", "activity_observation": "intentional stop",
            "traffic_conflict_observation": "none observed", "law_direction_observation": "none observed",
            "officer_direction_observation": "none observed", "device_direction_observation": "none observed",
            "source_refs": [{"path": "original-activity-packet", "sha256": "activity-seal"}]}


def square(x, y, half=1):
    return [[x-half, y-half], [x+half, y-half], [x+half, y+half], [x-half, y+half]]


def history(points):
    return {"map_id": "reviewed-map", "fps": 20,
            "source_refs": [{"path": "original-trace", "sha256": "trace-seal"}],
            "samples": [{"frame": i, "body_footprint": square(x, y), "speed_mps": speed}
                        for i, (x, y, speed) in enumerate(points)]}


class GeometryTests(unittest.TestCase):
    def test_body_contact_and_outside_control(self):
        result = module.measure(BOUNDARY, history([(5, 5, 0), (11, 5, 0), (14, 5, 0)]), ACTIVITY)
        self.assertEqual([x["within_or_touching_boundary"] for x in result["frames"]], [True, True, False])
        self.assertIsNone(result["legal_conclusion"])

    def test_crossing_body_without_inside_vertices(self):
        self.assertTrue(module.footprint_intersects_boundary(
            [[-5, 4], [15, 4], [15, 6], [-5, 6]], BOUNDARY["intersection_polygon"]))

    def test_nonjoining_or_unreviewed_boundary_rejected(self):
        unreviewed = dict(BOUNDARY, joining_roadways=False)
        with self.assertRaisesRegex(module.SourceError, "basis unreviewed"):
            module.measure(unreviewed, history([(5, 5, 0), (5, 5, 0)]), ACTIVITY)

    def test_mismatched_map_rejected(self):
        with self.assertRaisesRegex(module.SourceError, "map identity differs"):
            module.measure(BOUNDARY, dict(history([(5, 5, 0), (5, 5, 0)]), map_id="other"), ACTIVITY)

    def test_missing_activity_source_rejected(self):
        with self.assertRaisesRegex(module.SourceError, "independent activity source"):
            module.measure(BOUNDARY, history([(5, 5, 0), (5, 5, 0)]), dict(ACTIVITY, source_refs=[]))

    def test_nonmonotonic_trace_rejected(self):
        trace = history([(5, 5, 0), (5, 5, 0)])
        trace["samples"][1]["frame"] = 0
        with self.assertRaisesRegex(module.SourceError, "nonmonotonic"):
            module.measure(BOUNDARY, trace, ACTIVITY)

    def test_original_source_manifest_finalizer_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = {"boundary": BOUNDARY, "trace": history([(5, 5, 0), (14, 5, 0)]),
                      "activity": ACTIVITY}
            manifest = {"case_id": "exact-test-case"}
            for name, value in inputs.items():
                path = root / (name + ".json")
                path.write_text(json.dumps(value))
                manifest[name] = {"path": path.name,
                                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            (root / "manifest.json").write_text(json.dumps(manifest))
            command = [sys.executable, str(ROOT / "finalize_observables.py"),
                       str(root / "manifest.json"), str(root / "result.json")]
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            passed = subprocess.run(command, capture_output=True, text=True, env=environment)
            self.assertEqual(passed.returncode, 0, passed.stderr)
            result = json.loads((root / "result.json").read_text())
            self.assertEqual(result["case_id"], "exact-test-case")
            self.assertEqual([x["within_or_touching_boundary"] for x in result["frames"]],
                             [True, False])
            (root / "trace.json").write_text("{}")
            rejected = subprocess.run(command, capture_output=True, text=True, env=environment)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("source seal differs", rejected.stderr)

    def test_comparison_isolation_and_missing_source_rejection(self):
        contract = {"comparison_id": "boundary_contact", "case_ids": ["outside", "inside"],
                    "fixed_condition_keys": ["vehicle", "camera_plan", "approach"],
                    "difference_keys": ["destination"]}
        left = {"case_id": "outside", "source_seals": {"boundary": "same", "trace": "l", "activity": "a"},
                "source_refs": [{"path": "original", "sha256": "x"}], "frames": [{"frame": 0}],
                "map_id": "map", "condition_receipt": {"vehicle": "car", "camera_plan": "four", "approach": "east", "destination": "outside"}}
        right = {**left, "case_id": "inside", "source_seals": {"boundary": "same", "trace": "r", "activity": "b"},
                 "condition_receipt": {**left["condition_receipt"], "destination": "inside"}}
        self.assertEqual(audit(contract, left, right)["observed_difference_keys"], ["destination"])
        with self.assertRaisesRegex(ValueError, "fixed condition differs"):
            audit(contract, left, {**right, "condition_receipt": {**right["condition_receipt"], "approach": "west"}})
        with self.assertRaisesRegex(ValueError, "difference not observed"):
            audit(contract, left, {**right, "condition_receipt": left["condition_receipt"]})
        with self.assertRaisesRegex(ValueError, "original source seals missing"):
            audit(contract, left, {**right, "source_seals": {"boundary": "same"}})


if __name__ == "__main__":
    unittest.main()
