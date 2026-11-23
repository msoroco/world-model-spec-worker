import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "attention_measurement.py"
SPEC = importlib.util.spec_from_file_location("attention_measurement", MODULE)
measurement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measurement)
CASE = "testing__C10301__LVMC-11-22-010__motor_vehicle_driver__steady_travel"


def rows():
    return [{"case_id": CASE, "frame": i, "time_s": i / 20,
             "person_id": "driver-1", "vehicle_id": "ego-1", "operating": i >= 2,
             "position_x_m": i / 10, "position_y_m": 0.1 * (i % 2),
             "yaw_rate_rad_s": 0.01 * (i % 2), "speed_m_s": 2.0,
             "accel_longitudinal_m_s2": 0.0, "hard_deceleration": False,
             "straddles_marking": False, "time_to_conflict_s": None,
             "traffic_signal": "none"} for i in range(40)]


class SourceBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "history.jsonl"

    def run_rows(self, source):
        self.path.write_text("".join(json.dumps(row) + "\n" for row in source))
        return measurement.measure(self.path, CASE)

    def test_measures_original_operating_interval_without_judgment(self):
        report = self.run_rows(rows())
        self.assertEqual(report["operating_frame_count"], 38)
        self.assertEqual(report["observed_exterior"]["max_abs_yaw_rate_rad_s"], 0.01)
        self.assertEqual(report["legal_judgment"], "unresolved")
        self.assertEqual(report["attention_state"], "unobserved")

    def test_rejects_missing_observation(self):
        data = rows()
        del data[10]["straddles_marking"]
        with self.assertRaisesRegex(ValueError, "missing source fields"):
            self.run_rows(data)

    def test_rejects_wrong_case_and_identity_break(self):
        data = rows()
        data[7]["case_id"] = "other"
        with self.assertRaisesRegex(ValueError, "exact case identity"):
            self.run_rows(data)
        data = rows()
        data[7]["person_id"] = "driver-2"
        with self.assertRaisesRegex(ValueError, "participant identity"):
            self.run_rows(data)

    def test_rejects_unobserved_operation_and_invalid_time(self):
        data = rows()
        for row in data:
            row["operating"] = False
        with self.assertRaisesRegex(ValueError, "no observed operating"):
            self.run_rows(data)
        data = rows()
        data[11]["time_s"] = data[10]["time_s"]
        with self.assertRaisesRegex(ValueError, "nonmonotonic"):
            self.run_rows(data)


if __name__ == "__main__":
    unittest.main()
