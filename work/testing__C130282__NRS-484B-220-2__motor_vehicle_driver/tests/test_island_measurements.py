import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from island_measurements import ASSIGNMENT_ID, measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body(x, y):
    return [[x + dx, y + dy, z] for z in (-.3, .3)
            for dx in (-.3, .3) for dy in (-.3, .3)]


class IslandMeasurements(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.case = ASSIGNMENT_ID + "__inner_right"
        self.map_path = self.root / "original-map.json"
        self.trace_path = self.root / "original-trace.jsonl"
        self.receipt_path = self.root / "receipt.json"
        self.packet = {"case_id": self.case, "layout": "multilane_roundabout",
                       "native_map_sha256": "a" * 64,
                       "island": {"kind": "rotary_traffic_island", "identity_source": "original-island-review",
                                  "physical_polygon": [[-1, -1], [1, -1], [1, 1], [-1, 1]]},
                       "circulation_surface_polygon": [[-6, -6], [6, -6], [6, 6], [-6, 6]],
                       "circulation_lanes": [{"lane_id": "inner", "role": "inner", "source_ref": "original-inner-lane",
                                              "route_source": "original-inner-waypoints"},
                                             {"lane_id": "outer", "role": "outer", "source_ref": "original-outer-lane",
                                              "route_source": "original-outer-waypoints"}],
                       "connected_route_source": "original-entry-to-exit-route",
                       "vehicle_driver_source": "original-motor-vehicle-driver"}
        self.rows = [{"frame": 100 + i, "time_s": (100 + i) / 20,
                      "ego_center": [i, -4], "ego_heading": [1, 0],
                      "ego_lane_id": "inner", "ego_vertices": body(i, -4)} for i in range(3)]
        self.receipt = {"assignment_id": ASSIGNMENT_ID, "case_id": self.case,
                        "diagnostic_fixture": False, "fps": 20, "frame_count": 3}
        self.write()

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        self.map_path.write_text(json.dumps(self.packet) + "\n", encoding="utf-8")
        self.trace_path.write_text("".join(json.dumps(r) + "\n" for r in self.rows), encoding="utf-8")
        self.receipt["map_sha256"] = sha(self.map_path)
        self.receipt["trace_sha256"] = sha(self.trace_path)
        self.receipt_path.write_text(json.dumps(self.receipt) + "\n", encoding="utf-8")

    def run_measure(self):
        return measure(case_id=self.case, map_path=self.map_path,
                       trace_path=self.trace_path, receipt_path=self.receipt_path)

    def test_source_bound_right_side_and_cli(self):
        result = self.run_measure()
        self.assertEqual(result["sampled_right_of_island_frames"], [100, 101, 102])
        self.assertEqual(result["sampled_left_or_overlap_frames"], [])
        output = self.root / "measure.json"
        command = [sys.executable, str(ROOT / "island_measurements.py"),
                   "--case", self.case, "--map", str(self.map_path),
                   "--trace", str(self.trace_path), "--receipt", str(self.receipt_path),
                   "--output", str(output)]
        finished = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(output.read_text()), result)

    def test_left_side_from_original_heading(self):
        for row in self.rows:
            row["ego_heading"] = [-1, 0]
        self.write()
        result = self.run_measure()
        self.assertEqual(result["sampled_left_or_overlap_frames"], [100, 101, 102])

    def test_body_overlap_rejected_as_right_side(self):
        self.rows[1]["ego_center"] = [0, -1.1]
        self.rows[1]["ego_vertices"] = body(0, -1.1)
        self.write()
        result = self.run_measure()
        self.assertIn(101, result["sampled_left_or_overlap_frames"])
        self.assertTrue(result["observations"][1]["body_overlaps_island"])

    def test_rejects_roundabout_label_without_island_source(self):
        self.packet["island"]["identity_source"] = ""
        self.write()
        with self.assertRaisesRegex(ValueError, "rotary traffic island identity"):
            self.run_measure()

    def test_rejects_missing_original_route(self):
        self.packet["circulation_lanes"][0]["route_source"] = ""
        self.write()
        with self.assertRaisesRegex(ValueError, "lane route"):
            self.run_measure()

    def test_rejects_source_mutation(self):
        self.trace_path.write_text(self.trace_path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "source bytes changed"):
            self.run_measure()

    def test_rejects_missing_original_body(self):
        del self.rows[1]["ego_vertices"]
        self.write()
        with self.assertRaisesRegex(ValueError, "body vertices"):
            self.run_measure()

    def test_rejects_diagnostic_fixture(self):
        self.receipt["diagnostic_fixture"] = True
        self.write()
        with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
            self.run_measure()


if __name__ == "__main__":
    unittest.main()
