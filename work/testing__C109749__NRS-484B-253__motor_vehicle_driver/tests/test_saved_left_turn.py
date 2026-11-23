import hashlib
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from saved_left_turn import ASSIGNMENT_ID, process


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def waypoint(x, y, junction):
    return {"x_m": x, "y_m": y, "road_id": 1, "lane_id": 1,
            "junction_id": junction, "source_ref": "diagnostic-map-waypoint"}


def body(x, y):
    return [[x + dx, y + dy, dz] for dz in (-0.5, 0.5)
            for dx in (-0.5, 0.5) for dy in (-0.5, 0.5)]


class SavedLeftTurn(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self.tmp.name)
        self.case_id = ASSIGNMENT_ID + "__inside_yield"
        self.map_path = root / "original-map.json"
        self.trace_path = root / "original-trace.jsonl"
        self.receipt_path = root / "receipt.json"
        packet = {"map_sha256": "a" * 64, "source_ref": "diagnostic-map",
                  "junction_id": 9, "intersection_polygon": [[-5, -5], [5, -5], [5, 5], [-5, 5]],
                  "ego_route": [waypoint(0, -10, None), waypoint(0, 0, 9), waypoint(-10, 0, None)],
                  "opposing_route": [waypoint(0, 10, None), waypoint(0, 0, 9), waypoint(0, -10, None)],
                  "ego_blueprint_id": "vehicle.ego", "opponent_blueprint_id": "vehicle.other"}
        self.map_path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
        rows = []
        for number in (100, 101):
            rows.append({"frame": number, "time_s": number / 20,
                         "ego_vertices": body(0, 0), "opponent_vertices": body(1, 0),
                         "ego_heading": [1, 0], "opponent_heading": [-1, 0],
                         "ego_speed_mps": 1, "opponent_speed_mps": 5,
                         "ego_signal_left": True, "ego_turn_committed": False,
                         "opponent_cleared": False, "ego_braking": True})
        self.rows = rows
        self.write_trace()
        self.receipt = {"assignment_id": ASSIGNMENT_ID, "case_id": self.case_id,
                        "map_sha256": sha(self.map_path), "trace_sha256": sha(self.trace_path),
                        "native_map_sha256": packet["map_sha256"], "source_id": "original-test",
                        "frame_count": 2, "simulator_frame_rate_hz": 20,
                        "diagnostic_fixture": False}
        self.write_receipt()

    def tearDown(self):
        self.tmp.cleanup()

    def write_trace(self):
        self.trace_path.write_text("".join(json.dumps(r) + "\n" for r in self.rows), encoding="utf-8")

    def write_receipt(self):
        self.receipt_path.write_text(json.dumps(self.receipt) + "\n", encoding="utf-8")

    def run_process(self):
        return process(case_id=self.case_id, map_path=self.map_path,
                       trace_path=self.trace_path, receipt_path=self.receipt_path)

    def test_sealed_sources_measure_original_frames(self):
        result = self.run_process()
        self.assertEqual(len(result["frames"]), 2)
        self.assertEqual(result["physical_acceptance"], "unverified")
        self.assertEqual(result["source_bindings"]["original_trace_sha256"], sha(self.trace_path))

    def test_rejects_diagnostic_fixture(self):
        self.receipt["diagnostic_fixture"] = True
        self.write_receipt()
        with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
            self.run_process()

    def test_rejects_source_mutation(self):
        self.rows[1]["ego_braking"] = False
        self.write_trace()
        with self.assertRaisesRegex(ValueError, "sealed source bytes changed"):
            self.run_process()

    def test_rejects_case_mismatch(self):
        self.receipt["case_id"] += "-wrong"
        self.write_receipt()
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            self.run_process()

    def test_rejects_dropped_frame(self):
        self.rows[1]["frame"] = 102
        self.rows[1]["time_s"] = 5.1
        self.write_trace()
        self.receipt["trace_sha256"] = sha(self.trace_path)
        self.write_receipt()
        with self.assertRaisesRegex(ValueError, "dropped or duplicated"):
            self.run_process()

    def test_rejects_false_cadence(self):
        self.rows[1]["time_s"] = 5.07
        self.write_trace()
        self.receipt["trace_sha256"] = sha(self.trace_path)
        self.write_receipt()
        with self.assertRaisesRegex(ValueError, "timestamp cadence"):
            self.run_process()


if __name__ == "__main__":
    unittest.main()
