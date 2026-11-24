import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("signal_audit", ROOT / "signal_audit.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class SavedSourceAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make(self, case_id, start):
        source = self.root / f"{case_id}-source.json"
        measurement = self.root / f"{case_id}-measurement.json"
        packet = {"format": "native-turn-signal-samples-v1", "case_id": case_id,
                  "ego_actor": "motor_vehicle_driver", "context": {
                      "highway_source": "native road", "district_kind": "business",
                      "district_source": "survey", "frontage_source": "survey",
                      "building_use_source": "survey", "loading_zone_source": "map",
                      "maneuver": "right_turn", "weather_source": "clear"},
                  "samples": [{"frame": i, "x_m": i * .61, "y_m": 0,
                               "right_signal": i >= start, "course_change": i >= 50}
                              for i in range(51)]}
        source.write_text(json.dumps(packet))
        measurement.write_text(json.dumps(AUDIT.MEASURE.measure(source, case_id)))
        return source, measurement

    def test_positive_and_tampered_measurement(self):
        source, measurement = self.make("case-a", 0)
        self.assertTrue(AUDIT.audit_measurement(measurement, source)["passed"])
        saved = json.loads(measurement.read_text())
        saved["continuous_distance_ft"] = 1000
        measurement.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, "differs from sealed source"):
            AUDIT.audit_measurement(measurement, source)

    def test_source_mutation_and_missing_source(self):
        source, measurement = self.make("case-a", 0)
        packet = json.loads(source.read_text())
        packet["samples"][25]["right_signal"] = False
        source.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "differs from sealed source"):
            AUDIT.audit_measurement(measurement, source)
        source.unlink()
        with self.assertRaises(FileNotFoundError):
            AUDIT.audit_measurement(measurement, source)

    def test_independent_distance_comparison(self):
        short_source, short_measure = self.make("short", 12)
        long_source, long_measure = self.make("long", 0)
        result = AUDIT.audit_comparison(short_measure, short_source, long_measure,
                                        long_source, "business_right_distance")
        self.assertTrue(result["software_measurement_passed"])


if __name__ == "__main__":
    unittest.main()
