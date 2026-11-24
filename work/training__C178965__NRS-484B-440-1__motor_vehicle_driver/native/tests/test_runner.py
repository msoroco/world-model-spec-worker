import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("runner", Path(__file__).resolve().parents[1] / "runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerPlanTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())

    def test_exact_plan(self):
        proof = runner.check(self.config)
        self.assertEqual(proof["frame_count"], 600)
        self.assertEqual(len(proof["views"]), 4)
        self.assertFalse(proof["carla_contacted"])

    def test_wrong_cell_rejected(self):
        self.config["cell_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "assignment identity changed"):
            runner.check(self.config)

    def test_short_capture_rejected(self):
        self.config["frames"] = 599
        with self.assertRaisesRegex(ValueError, "30-second capture required"):
            runner.check(self.config)


if __name__ == "__main__":
    unittest.main()
