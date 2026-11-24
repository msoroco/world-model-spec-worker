import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from roundabout_measurements import ASSIGNMENT_ID, measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body(x, y):
    return [[x + dx, y + dy, z] for z in (-.5, .5)
            for dx in (-.5, .5) for dy in (-.5, .5)]


class RoundaboutMeasurements(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.case = ASSIGNMENT_ID + "__connected_enter"
        self.map_path = self.root / "original-map.json"
        self.trace_path = self.root / "original-trace.jsonl"
        self.receipt_path = self.root / "receipt.json"
        self.packet = {"case_id": self.case, "layout": "multilane_roundabout",
                       "map_sha256": "a" * 64, "jurisdiction_source": "original-map-locality",
                       "roundabout_geometry_source": "original-map-geometry",
                       "circulating_surface_polygon": [[-4, -4], [4, -4], [4, 4], [-4, 4]],
                       "entry_conflict_polygon": [[-2, -4], [2, -4], [2, 0], [-2, 0]],
                       "circulating_lanes": [{"lane_id": "inner"}, {"lane_id": "outer"}],
                       "ego_entry_lane": {"lane_id": "entry-1", "connected_circulating_lane_id": "outer"},
                       "opponent_route": {"circulating_lane_id": "outer", "route_source": "original-waypoints",
                                          "potential_conflict_source": "original-trajectory-overlap",
                                          "initial_position": [1, 0]},
                       "entry_line": [[-2, -4], [2, -4]]}
        self.rows = [{"frame": 100 + i, "time_s": (100 + i) / 20,
                      "ego_vertices": body(0, y), "opponent_vertices": body(1, 0),
                      "ego_speed_mps": 3, "opponent_speed_mps": 4}
                     for i, y in enumerate((-5, -3, 0))]
        self.receipt = {"assignment_id": ASSIGNMENT_ID, "case_id": self.case,
                        "diagnostic_fixture": False, "fps": 20, "frame_count": 3}
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self):
        self.map_path.write_text(json.dumps(self.packet) + "\n", encoding="utf-8")
        self.trace_path.write_text("".join(json.dumps(r) + "\n" for r in self.rows), encoding="utf-8")
        self.receipt["map_sha256"] = sha(self.map_path)
        self.receipt["trace_sha256"] = sha(self.trace_path)
        self.receipt_path.write_text(json.dumps(self.receipt) + "\n", encoding="utf-8")

    def run_measure(self):
        return measure(case_id=self.case, map_path=self.map_path,
                       trace_path=self.trace_path, receipt_path=self.receipt_path)

    def test_source_bound_entry_and_cli(self):
        result = self.run_measure()
        self.assertEqual(result["first_observed_ego_entry_frame"], 101)
        self.assertTrue(result["opponent_in_ring_at_ego_entry"])
        self.assertTrue(result["opponent_in_conflict_at_ego_entry"])
        self.assertIsInstance(result["body_separation_at_entry_m"], float)
        self.assertEqual(result["opponent_circulating_lane_id"], "outer")
        output = self.root / "measured.json"
        command = [sys.executable, str(ROOT / "roundabout_measurements.py"),
                   "--case", self.case, "--map", str(self.map_path),
                   "--trace", str(self.trace_path), "--receipt", str(self.receipt_path),
                   "--output", str(output)]
        finished = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(output.read_text()), result)

    def test_rejects_unconnected_entry_lane(self):
        self.packet["ego_entry_lane"]["connected_circulating_lane_id"] = "imaginary"
        self.write()
        with self.assertRaisesRegex(ValueError, "not connected"):
            self.run_measure()

    def test_rejects_opponent_outside_ring(self):
        self.packet["opponent_route"]["initial_position"] = [9, 9]
        self.write()
        with self.assertRaisesRegex(ValueError, "start inside"):
            self.run_measure()

    def test_rejects_missing_conflict_source(self):
        self.packet["opponent_route"]["potential_conflict_source"] = ""
        self.write()
        with self.assertRaisesRegex(ValueError, "route/conflict source"):
            self.run_measure()

    def test_rejects_changed_trace_bytes(self):
        self.trace_path.write_text(self.trace_path.read_text() + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source bytes changed"):
            self.run_measure()

    def test_rejects_dropped_frame(self):
        self.rows[1]["frame"] = 103
        self.write()
        with self.assertRaisesRegex(ValueError, "frame order"):
            self.run_measure()

    def test_rejects_missing_original_body(self):
        del self.rows[1]["opponent_vertices"]
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
