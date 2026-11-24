import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from signal_measurements import ASSIGNMENT_ID, measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SignalMeasurements(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.case = ASSIGNMENT_ID + "__bicycle_right_arm_horizontal"
        self.context_path = self.root / "context.json"
        self.trace_path = self.root / "trace.jsonl"
        self.receipt_path = self.root / "receipt.json"
        self.context = {"case_id": self.case, "map_sha256": "a" * 64,
                        "operator_vehicle_kind": "bicycle", "operator_identity_source": "original-rider",
                        "roadway_status": "roadway", "highway_status_source": "original-road-class",
                        "roadway_polygon": [[-5, -5], [5, -5], [5, 5], [-5, 5]],
                        "shoulder_polygon": [[5, -5], [7, -5], [7, 5], [5, 5]],
                        "roadway_geometry_source": "original-road-waypoints",
                        "shoulder_geometry_source": "original-shoulder-edge",
                        "right_turn_route": {"waypoint_source": "original-right-route",
                                             "first_heading": [1, 0], "last_heading": [0, -1]}}
        arm = {"shoulder": [0, 0, 1], "elbow": [0, -.3, 1], "wrist": [0, -.6, 1]}
        self.rows = [{"frame": 100 + i, "time_s": (100 + i) / 20,
                      "operator_vehicle_contact_point": [i, 0],
                      "operator_heading": [1, 0], "right_arm": arm} for i in range(3)]
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

    def test_right_horizontal_pose_and_cli(self):
        result = self.run_measure()
        self.assertEqual(result["roadway_frames"], [100, 101, 102])
        self.assertAlmostEqual(result["observations"][0]["right_arm"]["wrist_right_m"], .6)
        self.assertEqual(result["observations"][0]["right_arm"]["wrist_vertical_from_shoulder_m"], 0)
        output = self.root / "measured.json"
        command = [sys.executable, str(ROOT / "signal_measurements.py"),
                   "--case", self.case, "--context", str(self.context_path),
                   "--trace", str(self.trace_path), "--receipt", str(self.receipt_path),
                   "--output", str(output)]
        finished = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(output.read_text()), result)

    def test_downward_arm_keeps_raw_vertical_measurement(self):
        for row in self.rows:
            row["right_arm"]["wrist"] = [0, -.6, .4]
        self.write()
        self.assertAlmostEqual(self.run_measure()["observations"][0]["right_arm"]["wrist_vertical_from_shoulder_m"], -.6)

    def test_left_side_arm_keeps_raw_right_projection(self):
        for row in self.rows:
            row["right_arm"]["wrist"] = [0, .6, 1]
        self.write()
        self.assertAlmostEqual(self.run_measure()["observations"][0]["right_arm"]["wrist_right_m"], -.6)

    def test_rejects_shoulder_contact_location(self):
        self.rows[1]["operator_vehicle_contact_point"] = [6, 0]
        self.write()
        self.assertEqual(self.run_measure()["shoulder_or_off_roadway_frames"], [101])

    def test_rejects_non_right_route(self):
        self.context["right_turn_route"]["last_heading"] = [0, 1]
        self.write()
        with self.assertRaisesRegex(ValueError, "does not turn right"):
            self.run_measure()

    def test_rejects_unqualified_operator(self):
        self.context["operator_vehicle_kind"] = "moped"
        self.write()
        with self.assertRaisesRegex(ValueError, "covered cycle/scooter"):
            self.run_measure()

    def test_rejects_missing_arm_joints(self):
        del self.rows[1]["right_arm"]
        self.write()
        with self.assertRaisesRegex(ValueError, "right-arm joint"):
            self.run_measure()

    def test_rejects_source_mutation(self):
        self.trace_path.write_text(self.trace_path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "original source bytes changed"):
            self.run_measure()

    def test_rejects_diagnostic_fixture(self):
        self.receipt["diagnostic_fixture"] = True
        self.write()
        with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
            self.run_measure()


if __name__ == "__main__":
    unittest.main()
