import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("signal_measure", ROOT / "signal_measure.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SignalMeasurementTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "samples.json"

    def packet(self, signal_start=0, interrupted=False, rain=False):
        rows = []
        for frame in range(51):
            active = frame >= signal_start
            if interrupted and frame == 20:
                active = False
            rows.append({"frame": frame, "x_m": 0.61 * frame, "y_m": 0,
                         "right_signal": active, "course_change": frame >= 50})
        return {"format": "native-turn-signal-samples-v1", "case_id": "case-a",
                "ego_actor": "motor_vehicle_driver", "context": {
                    "highway_source": "native road packet", "district_kind": "business",
                    "district_source": "survey packet", "frontage_source": "survey packet",
                    "building_use_source": "survey packet", "loading_zone_source": "native map",
                    "maneuver": "right_turn", "weather_source": "rain" if rain else "clear"},
                "samples": rows}

    def read(self, packet):
        self.path.write_text(json.dumps(packet))
        return MODULE.measure(self.path, "case-a")

    def test_measured_distance_and_onset(self):
        result = self.read(self.packet())
        self.assertEqual(result["onset_frame"], 50)
        self.assertGreater(result["continuous_distance_ft"], 100)
        self.assertTrue(result["sampled_threshold_reached"])
        self.assertEqual(len(result["source_sha256"]), 64)

    def test_short_and_interrupted_are_measured(self):
        self.assertFalse(self.read(self.packet(signal_start=12))["sampled_threshold_reached"])
        result = self.read(self.packet(interrupted=True))
        self.assertFalse(result["sampled_threshold_reached"])
        self.assertIn(20, result["prior_inactive_frames"])

    def test_missing_and_wrong_source_rejected(self):
        packet = self.packet()
        del packet["samples"][10]["right_signal"]
        with self.assertRaisesRegex(ValueError, "missing source sample"):
            self.read(packet)
        packet = self.packet()
        packet["samples"][10]["frame"] = 11
        with self.assertRaisesRegex(ValueError, "duplicate frames"):
            self.read(packet)
        with self.assertRaisesRegex(ValueError, "wrong case identity"):
            MODULE.measure(self.path, "case-b")

    def test_context_cannot_be_inferred_from_name(self):
        packet = self.packet()
        packet["context"]["frontage_source"] = ""
        with self.assertRaisesRegex(ValueError, "missing frontage_source"):
            self.read(packet)

    def test_comparison_requires_fixed_context_and_difference(self):
        left = self.read(self.packet(signal_start=12))
        right = self.read(self.packet())
        right["case_id"] = "case-b"
        self.assertTrue(MODULE.compare(left, right, "business_right_distance")["software_measurement_passed"])
        right["context_sources"]["frontage_source"] = "different survey"
        with self.assertRaisesRegex(ValueError, "fixed context differs"):
            MODULE.compare(left, right, "business_right_distance")

    def test_missing_source_file_rejected(self):
        with self.assertRaises(FileNotFoundError):
            MODULE.measure(self.path, "case-a")


if __name__ == "__main__":
    unittest.main()
