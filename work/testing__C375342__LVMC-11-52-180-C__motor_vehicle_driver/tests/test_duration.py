import importlib.util
import json
import hashlib
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "duration_measurement.py"
spec = importlib.util.spec_from_file_location("duration_measurement", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def intervals(*pairs):
    return [{"start_s": a, "end_s": b, "vehicle_id": "ego"} for a, b in pairs]


class DurationTests(unittest.TestCase):
    def test_continuous_exact_boundary(self):
        for seconds, expected in [(1740, False), (1800, False), (1860, True)]:
            with self.subTest(seconds=seconds):
                measured = m.maximum_rolling_hour(intervals((300, 300 + seconds)))
                self.assertEqual(measured["maximum_parked_seconds_in_any_hour"], seconds)
                self.assertEqual(measured["greater_than_thirty_minutes"], expected)

    def test_departure_return_does_not_reset(self):
        self.assertEqual(m.maximum_rolling_hour(intervals((300, 1260), (1860, 2700)))["maximum_parked_seconds_in_any_hour"], 1800)
        self.assertTrue(m.maximum_rolling_hour(intervals((300, 1260), (1860, 2760)))["greater_than_thirty_minutes"])

    def test_separated_by_more_than_hour(self):
        measured = m.maximum_rolling_hour(intervals((0, 1200), (5000, 6200)))
        self.assertEqual(measured["maximum_parked_seconds_in_any_hour"], 1200)

    def test_rejects_overlap_identity_and_nonfinite(self):
        for invalid in [intervals((0, 10), (9, 20)), [{"start_s": 0, "end_s": 10, "vehicle_id": "ego"}, {"start_s": 20, "end_s": 30, "vehicle_id": "other"}], intervals((0, float("nan")))]:
            with self.assertRaises(ValueError):
                m.maximum_rolling_hour(invalid)

    def test_source_hash_and_context_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packets = {
                "parking-intervals.json": json.dumps({"vehicle_id": "ego", "window_history_status": "complete_original", "intervals": intervals((300, 2160))}),
                "alley-context.json": json.dumps({"review_status": "original_reviewed", "municipal_alley_source": "source-a", "engineer_designation_source": "source-b", "angle_marking_source": "source-c", "other_parking_rules_source": "source-d"}),
                "video_frames.jsonl": '{"frame": 1}\n',
            }
            for name, content in packets.items():
                (root / name).write_text(content)
            inv = {name: {"sha256": hashlib.sha256(content.encode()).hexdigest()} for name, content in packets.items()}
            self.assertTrue(m.measure_source_packet(root, inv)["greater_than_thirty_minutes"])
            (root / "alley-context.json").write_text('{}')
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                m.measure_source_packet(root, inv)


if __name__ == "__main__":
    unittest.main()
