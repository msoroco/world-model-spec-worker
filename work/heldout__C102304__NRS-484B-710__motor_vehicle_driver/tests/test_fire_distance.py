import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


path = Path(__file__).resolve().parents[1] / "fire_distance.py"
spec = importlib.util.spec_from_file_location("fire_distance", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def box(x0, x1, y0=-1, y1=1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


class FireDistanceTests(unittest.TestCase):
    def test_full_body_separation_not_centre_or_commanded_spacing(self):
        ego = box(0, 4)
        apparatus = box(4 + 500 / module.FEET_PER_METRE, 10 + 500 / module.FEET_PER_METRE)
        result = module.measure_frame(ego, apparatus)
        self.assertAlmostEqual(result["nearest_footprint_gap_ft"], 500)
        self.assertGreater(result["centre_distance_ft"], 500)
        self.assertFalse(result["overlap_or_contact"])

    def test_diagonal_nearest_edges_and_contact(self):
        measured = module.measure_frame(box(0, 2, 0, 2), box(5, 7, 6, 8))
        self.assertAlmostEqual(measured["nearest_footprint_gap_m"], 5)
        self.assertTrue(module.measure_frame(box(0, 2), box(2, 4))["overlap_or_contact"])

    def test_rejects_missing_or_self_crossing_geometry(self):
        with self.assertRaises(ValueError):
            module.measure_frame([(0, 0)] * 4, box(2, 4))
        with self.assertRaises(ValueError):
            module.measure_frame([(0, 0), (2, 2), (0, 2), (2, 0)], box(3, 4))

    def test_history_rejects_missing_tick_and_swapped_identity(self):
        def sample(frame, ego_id="ego"):
            return {"frame": frame, "time_s": frame / 20, "ego_id": ego_id,
                    "apparatus_id": "fire", "ego_corners": box(0, 4),
                    "apparatus_corners": box(10, 14)}
        history = module.measure_history([sample(0), sample(1)], 2)
        self.assertEqual([entry["frame"] for entry in history], [0, 1])
        with self.assertRaisesRegex(ValueError, "Missing or unordered"):
            module.measure_history([sample(0), sample(2)], 2)
        with self.assertRaisesRegex(ValueError, "identity changed"):
            module.measure_history([sample(0), sample(1, "replacement")], 2)
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            module.measure_history([sample(0)], 2)

    def test_retained_source_binding_and_missing_source_rejection(self):
        sample = {"frame": 12, "time_s": 0.6, "ego_id": "ego",
                  "apparatus_id": "fire", "ego_corners": box(0, 4),
                  "apparatus_corners": box(10, 14)}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "native-participants.jsonl"
            with self.assertRaises(FileNotFoundError):
                module.measure_native_source(source, 1)
            source.write_text(json.dumps(sample) + "\n")
            result = module.measure_native_source(source, 1)
            self.assertEqual(result["frame_count"], 1)
            self.assertEqual(result["source_sha256"], module.sha256(source.read_bytes()).hexdigest())
            source.write_text("{}\n")
            with self.assertRaises(ValueError):
                module.measure_native_source(source, 1)


if __name__ == "__main__":
    unittest.main()
