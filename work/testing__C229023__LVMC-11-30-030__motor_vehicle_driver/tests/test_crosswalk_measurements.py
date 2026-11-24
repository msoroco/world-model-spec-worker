import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crosswalk_measurements import ASSIGNMENT_ID, measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body(x, y):
    return [[x + dx, y + dy, z] for z in (-.5, .5)
            for dx in (-.5, .5) for dy in (-.5, .5)]


class CrosswalkMeasurements(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.case = ASSIGNMENT_ID + "__unmarked_pass"
        self.context_path = self.root / "context.json"
        self.trace_path = self.root / "trace.jsonl"
        self.receipt_path = self.root / "receipt.json"
        self.context = {"case_id": self.case, "map_sha256": "a" * 64,
                        "layout": "intersection", "junction_kind": "road_intersection",
                        "crosswalk": {"kind": "unmarked", "polygon": [[-2, -2], [2, -2], [2, 2], [-2, 2]],
                                      "opposite_sidewalk_lateral_lines": ["original-sidewalk-left", "original-sidewalk-right"],
                                      "curb_or_traveled_edge_sources": ["original-curb-left", "original-curb-right"]},
                        "stopped_vehicle_purpose": {"claim": "permit_pedestrian", "source_ref": "original-driver-plan"},
                        "pedestrian_identity": "pedestrian.1", "lead_vehicle_identity": "vehicle.lead",
                        "ego_vehicle_identity": "vehicle.ego",
                        "road_axis": {"origin": [0, 0], "forward": [0, 1]}}
        self.rows = [{"frame": 50 + i, "time_s": (50 + i) / 20,
                      "ego_center": [1, -4 + i * 4], "lead_center": [0, 0],
                      "ego_vertices": body(1, -4 + i * 4), "lead_vertices": body(0, 0),
                      "pedestrian_center": [-1 + i, 0],
                      "ego_speed_mps": 4, "lead_speed_mps": 0} for i in range(3)]
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

    def test_original_sequence_and_cli(self):
        result = self.run_measure()
        self.assertEqual(result["rear_approach_frames"], [50])
        self.assertEqual(result["ego_ahead_frames"], [52])
        self.assertEqual(result["lead_stopped_frames"], [50, 51, 52])
        self.assertEqual(result["pedestrian_crosswalk_frames"], [50, 51, 52])
        output = self.root / "result.json"
        command = [sys.executable, str(ROOT / "crosswalk_measurements.py"),
                   "--case", self.case, "--context", str(self.context_path),
                   "--trace", str(self.trace_path), "--receipt", str(self.receipt_path),
                   "--output", str(output)]
        finished = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(output.read_text()), result)

    def test_rejects_no_crosswalk_geometry(self):
        self.context["crosswalk"]["opposite_sidewalk_lateral_lines"] = []
        self.write()
        with self.assertRaisesRegex(ValueError, "unmarked crosswalk geometry"):
            self.run_measure()

    def test_rejects_purpose_without_source(self):
        self.context["stopped_vehicle_purpose"]["source_ref"] = ""
        self.write()
        with self.assertRaisesRegex(ValueError, "independent source"):
            self.run_measure()

    def test_rejects_false_marked_crosswalk(self):
        self.context["crosswalk"]["kind"] = "marked"
        self.write()
        with self.assertRaisesRegex(ValueError, "marked crosswalk source"):
            self.run_measure()

    def test_rejects_source_mutation(self):
        self.trace_path.write_text(self.trace_path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "source bytes changed"):
            self.run_measure()

    def test_rejects_dropped_frame(self):
        self.rows[1]["frame"] = 52
        self.write()
        with self.assertRaisesRegex(ValueError, "frame order"):
            self.run_measure()

    def test_rejects_missing_original_body_vertices(self):
        del self.rows[1]["ego_vertices"]
        self.write()
        with self.assertRaisesRegex(ValueError, "body vertices"):
            self.run_measure()

    def test_diagnostic_is_not_delivery_evidence(self):
        self.receipt["diagnostic_fixture"] = True
        self.write()
        with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
            self.run_measure()


if __name__ == "__main__":
    unittest.main()
