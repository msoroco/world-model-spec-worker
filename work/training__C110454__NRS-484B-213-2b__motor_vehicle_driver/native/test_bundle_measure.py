import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("measure", HERE / "measure.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def samples(inside):
    x0 = -55 if not inside else -28
    out = []
    for i in range(4):
        x = x0 + i
        out.append({"video_frame": i, "native_frame": i, "time_s": i * .05,
                    "body_xy_m": [[x-2.6,.65],[x-2.6,2.85],[x+2.6,2.85],[x+2.6,.65]],
                    "speed_m_s": 5.0, "two_way_native_survey": True})
    return out


class NativeMeasurement(unittest.TestCase):
    def run_source(self, rows):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "native_samples.json"
            path.write_text(json.dumps(rows))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            return module.measure(rows, path, digest)

    def test_controlled_sides(self):
        self.assertEqual(self.run_source(samples(False))["sampled_relation"], "outside_100_ft")
        self.assertEqual(self.run_source(samples(True))["sampled_relation"], "within_100_ft")

    def test_missing_join(self):
        rows = samples(True); rows[2]["native_frame"] = 9
        with self.assertRaisesRegex(ValueError, "join"):
            self.run_source(rows)

    def test_one_way_unsurveyed(self):
        rows = samples(True); rows[2]["two_way_native_survey"] = False
        with self.assertRaisesRegex(ValueError, "Two-way"):
            self.run_source(rows)

    def test_no_original_body(self):
        rows = samples(True); del rows[1]["body_xy_m"]
        with self.assertRaisesRegex(ValueError, "footprint"):
            self.run_source(rows)

    def test_source_tamper(self):
        rows = samples(True)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "native_samples.json"
            path.write_text(json.dumps(rows))
            with self.assertRaisesRegex(ValueError, "hash"):
                module.measure(rows, path, "0" * 64)

    def test_stationary_not_driven(self):
        rows = samples(True)
        for row in rows: row["speed_m_s"] = 0
        with self.assertRaisesRegex(ValueError, "driven"):
            self.run_source(rows)


if __name__ == "__main__":
    unittest.main()
