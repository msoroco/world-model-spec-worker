import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from test_observed_speed import SCRATCH, fixture

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("compare_speed", ROOT / "compare_speed.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ComparisonTest(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.a = Path(self.temp.name) / "a.jsonl"
        self.b = Path(self.temp.name) / "b.jsonl"

    def _write(self, path, rows):
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))

    def test_fixed_context_and_speed_difference(self):
        self._write(self.a, fixture("a"))
        self._write(self.b, fixture("b"))
        report = module.compare(self.a, self.b, synthetic=True)
        self.assertEqual(report["fixed_context_checked_frames"], 600)
        self.assertGreater(report["reduction_difference_mps"], 3)
        self.assertTrue(report["fixture_only"])

    def test_rejects_other_vehicle_change(self):
        rows = fixture("b")
        rows[250]["qualifying_vehicle"]["road_x_m"] += 1
        self._write(self.a, fixture("a"))
        self._write(self.b, rows)
        with self.assertRaisesRegex(ValueError, "Fixed qualifying vehicle"):
            module.compare(self.a, self.b, synthetic=True)

    def test_rejects_context_change(self):
        rows = fixture("b")
        rows[250]["weather_context_source_id"] = "different-weather"
        self._write(self.a, fixture("a"))
        self._write(self.b, rows)
        with self.assertRaisesRegex(ValueError, "Fixed road, weather"):
            module.compare(self.a, self.b, synthetic=True)

    def test_rejects_changed_baseline(self):
        rows = fixture("b")
        rows[50]["ego"]["speed_mps"] += 1
        self._write(self.a, fixture("a"))
        self._write(self.b, rows)
        with self.assertRaisesRegex(ValueError, "Initial ego speed"):
            module.compare(self.a, self.b, synthetic=True)


if __name__ == "__main__":
    unittest.main()
