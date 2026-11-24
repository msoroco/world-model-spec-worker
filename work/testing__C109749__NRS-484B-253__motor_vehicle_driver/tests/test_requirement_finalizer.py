import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from native_acquisition import capture
from requirement_finalizer import BRANCHES, finalize
from saved_left_turn import ASSIGNMENT_ID
from test_native_acquisition import Adapter, waypoint


class RequirementFinalizer(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.case = ASSIGNMENT_ID + "__inside_yield"
        packet = {"map_sha256": "a" * 64, "source_ref": "fixture-map",
                  "junction_id": 9, "reviewed_original_map": True,
                  "intersection_polygon": [[-5, -5], [5, -5], [5, 5], [-5, 5]],
                  "ego_route": [waypoint(0, -10, None), waypoint(0, 0, 9), waypoint(-10, 0, None)],
                  "opposing_route": [waypoint(0, 10, None), waypoint(0, 0, 9), waypoint(0, -10, None)],
                  "ego_blueprint_id": "vehicle.ego", "opponent_blueprint_id": "vehicle.other"}
        self.map_path = self.root / "map.json"
        self.map_path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
        adapter = Adapter()
        adapter.native_origin = True  # Synthetic adapter tests joins only.
        self.attempt = self.root / "attempt"
        capture(adapter=adapter, case_id=self.case, map_path=self.map_path,
                output=self.attempt, frame_count=2)

    def test_initial_within_has_saved_occupancy_and_control_sources(self):
        report = finalize(case_id=self.case, attempt=self.attempt)
        self.assertEqual(report["selected_disposition_index"], 0)
        self.assertEqual(report["observations"]["opponent_full_body_inside_first_frame"], 100)
        self.assertEqual(report["observations"]["ego_commit_first_frame"], None)
        self.assertEqual(report["physical_acceptance"], "unverified")
        self.assertEqual(set(report["source_hashes"]), {"original-map.json", "original-trace.jsonl",
                                                       "acquisition-receipt.json", "original-frame-map.json"})

    def test_all_eight_methods_return_case_specific_structures(self):
        for suffix, (index, method) in BRANCHES.items():
            # Exact receipt identity must match; create one fresh acquisition
            # per case rather than relabel an existing original source.
            if suffix == "inside_yield":
                attempt = self.attempt
            else:
                adapter = Adapter()
                adapter.native_origin = True
                attempt = self.root / suffix
                capture(adapter=adapter, case_id=ASSIGNMENT_ID + "__" + suffix,
                        map_path=self.map_path, output=attempt, frame_count=2)
            report = finalize(case_id=ASSIGNMENT_ID + "__" + suffix, attempt=attempt)
            self.assertEqual((report["selected_disposition_index"], report["method"]), (index, method))
            self.assertTrue(report["observations"])
            self.assertEqual(report["legal_judgment"], "unresolved")

    def test_rejects_wrong_exact_case_and_missing_original(self):
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            finalize(case_id=ASSIGNMENT_ID + "__inside_no_yield", attempt=self.attempt)
        with self.assertRaisesRegex(ValueError, "selected statutory requirement"):
            finalize(case_id=ASSIGNMENT_ID + "__invented", attempt=self.attempt)
        (self.attempt / "original-trace.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: original-trace.jsonl"):
            finalize(case_id=self.case, attempt=self.attempt)

    def test_rejects_mutated_original_frame_map(self):
        mapping = self.attempt / "original-frame-map.json"
        mapping.write_text(mapping.read_text() + " ", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "sealed camera frame map changed"):
            finalize(case_id=self.case, attempt=self.attempt)

    def test_cli_exact_positive_and_missing_source_negative(self):
        script = ROOT / "requirement_finalizer.py"
        output = self.root / "analysis-report.json"
        command = [sys.executable, str(script), "--attempt", str(self.attempt),
                   "--output", str(output)]
        success = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(success.returncode, 0, success.stderr)
        report = json.loads(output.read_text())
        self.assertIn("initial_within_events", report["measurements"])
        (self.attempt / "original-trace.jsonl").unlink()
        failure = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(failure.returncode, 0)
        self.assertIn("Missing required source: original-trace.jsonl", failure.stderr)


if __name__ == "__main__":
    unittest.main()
