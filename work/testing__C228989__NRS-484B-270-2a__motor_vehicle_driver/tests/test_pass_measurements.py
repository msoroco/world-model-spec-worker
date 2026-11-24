import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pass_measurements import ASSIGNMENT_ID, measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body(x, y):
    return [[x + dx, y + dy, z] for z in (-.3, .3)
            for dx in (-.3, .3) for dy in (-.3, .3)]


class PassMeasurements(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.case = ASSIGNMENT_ID + "__bicycle_open_left_move"
        self.context_path = self.root / "context.json"
        self.trace_path = self.root / "trace.jsonl"
        self.receipt_path = self.root / "receipt.json"
        self.context = {"case_id": self.case, "map_sha256": "a" * 64,
                        "ego_kind": "motor_vehicle", "control_kind": "bicycle",
                        "ego_driver_source": "original-ego-driver", "control_rider_source": "original-rider",
                        "road_origin": [0, 0], "road_forward": [0, 1],
                        "lanes": [{"lane_id": "right", "forward": [0, 1], "source_ref": "original-right-lane",
                                   "immediate_left_lane_id": "left"},
                                  {"lane_id": "left", "forward": [0, 1], "source_ref": "original-left-lane"}],
                        "ego_initial_lane_id": "right", "control_initial_lane_id": "right",
                        "immediate_left_lane_id": "left",
                        "lane_restrictions_source": "original-road-rules",
                        "left_lane_traffic_source": "original-actor-inventory",
                        "left_lane_obstructions_source": "original-scene-graph",
                        "surrounding_trajectories_source": "original-actor-histories"}
        self.rows = [{"frame": 100 + i, "time_s": (100 + i) / 20,
                      "ego_vertices": body(0, -4 + 4*i), "control_vertices": body(0, 0),
                      "ego_lane_id": "left" if i else "right", "control_lane_id": "right",
                      "left_lane_occupied_actor_ids": [],
                      "ego_speed_mps": 4, "control_speed_mps": 2}
                     for i in range(3)]
        self.receipt = {"assignment_id": ASSIGNMENT_ID, "case_id": self.case,
                        "diagnostic_fixture": False, "fps": 20, "frame_count": 3}
        self.write()

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        self.context_path.write_text(json.dumps(self.context) + "\n", encoding="utf-8")
        self.trace_path.write_text("".join(json.dumps(r) + "\n" for r in self.rows), encoding="utf-8")
        self.receipt["context_sha256"] = sha(self.context_path)
        self.receipt["trace_sha256"] = sha(self.trace_path)
        self.receipt_path.write_text(json.dumps(self.receipt) + "\n", encoding="utf-8")

    def run_measure(self):
        return measure(case_id=self.case, context_path=self.context_path,
                       trace_path=self.trace_path, receipt_path=self.receipt_path)

    def test_original_body_pass_and_cli_replay(self):
        result = self.run_measure()
        self.assertEqual(result["first_observed_full_pass_frame"], 102)
        self.assertEqual(result["ego_lane_at_full_pass"], "left")
        self.assertEqual(result["same_direction_lane_count"], 2)
        self.assertEqual(result["due_care_judgment"], "unresolved")
        output = self.root / "measure.json"
        command = [sys.executable, str(ROOT / "pass_measurements.py"),
                   "--case", self.case, "--context", str(self.context_path),
                   "--trace", str(self.trace_path), "--receipt", str(self.receipt_path),
                   "--output", str(output)]
        finished = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(output.read_text()), result)

    def test_rejects_wrong_direction_left_lane(self):
        self.context["lanes"][1]["forward"] = [0, -1]
        self.write()
        with self.assertRaisesRegex(ValueError, "single-lane context"):
            self.run_measure()

    def test_rejects_wrong_adjacency(self):
        self.context["lanes"][0]["immediate_left_lane_id"] = "other"
        self.write()
        with self.assertRaisesRegex(ValueError, "adjacency"):
            self.run_measure()

    def test_rejects_unqualified_control_actor(self):
        self.context["control_kind"] = "pedestrian"
        self.write()
        with self.assertRaisesRegex(ValueError, "qualifying"):
            self.run_measure()

    def test_rejects_actor_not_initially_ahead(self):
        self.rows[0]["ego_vertices"] = body(0, 4)
        self.write()
        with self.assertRaisesRegex(ValueError, "start ahead"):
            self.run_measure()

    def test_rejects_missing_traffic_inventory(self):
        del self.rows[1]["left_lane_occupied_actor_ids"]
        self.write()
        with self.assertRaisesRegex(ValueError, "occupancy inventory"):
            self.run_measure()

    def test_rejects_wrong_original_initial_lane(self):
        self.rows[0]["ego_lane_id"] = "left"
        self.write()
        with self.assertRaisesRegex(ValueError, "initial actor lane mismatch"):
            self.run_measure()

    def test_rejects_source_mutation(self):
        self.trace_path.write_text(self.trace_path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "source bytes changed"):
            self.run_measure()

    def test_rejects_diagnostic_fixture(self):
        self.receipt["diagnostic_fixture"] = True
        self.write()
        with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
            self.run_measure()


if __name__ == "__main__":
    unittest.main()
