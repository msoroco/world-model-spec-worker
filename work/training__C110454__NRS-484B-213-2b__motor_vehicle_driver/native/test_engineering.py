import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("engineering", HERE / "engineering.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EngineeringProof(unittest.TestCase):
    def test_distinct_knobs_and_fixed_conditions(self):
        for case in module.CASES:
            plans = [module.parameters(case, candidate) for candidate in module.CANDIDATES]
            self.assertEqual(len({json.dumps(p["knobs"], sort_keys=True) for p in plans}), 4)
            for plan in plans:
                self.assertEqual(plan["knobs"]["rate_hz"], 20)
                self.assertEqual(plan["knobs"]["duration_s"], 24)
                self.assertEqual(len(plan["knobs"]["camera_profile"]), 4)

    def test_trigger_positive_negative_and_tamper(self):
        for candidate, metric, low, high in (
            ("fallback1", "max_route_cross_track_error_m", .1, .8),
            ("fallback2", "parking_endpoint_speed_m_s", .1, .8),
            ("fallback3", "min_ego_pixel_margin_px", 20, 80),
        ):
            with self.subTest(candidate=candidate), tempfile.TemporaryDirectory() as temp:
                source = Path(temp) / "source-metrics.json"
                for value in (low, high):
                    metrics = {"source_kind": "original_native_and_video", metric: value}
                    source.write_text(json.dumps(metrics))
                    digest = hashlib.sha256(source.read_bytes()).hexdigest()
                    expected = value == high if candidate != "fallback3" else value == low
                    self.assertEqual(module.evaluate_trigger(candidate, metrics, source, digest), expected)
                with self.assertRaisesRegex(ValueError, "hash"):
                    module.evaluate_trigger(candidate, metrics, source, "0" * 64)


if __name__ == "__main__":
    unittest.main()
