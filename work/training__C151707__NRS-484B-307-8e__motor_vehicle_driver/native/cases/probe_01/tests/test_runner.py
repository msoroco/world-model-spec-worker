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
        self.assertEqual(proof["frames"], 600)
        self.assertEqual(len(proof["source_views"]), 4)
        self.assertFalse(proof["carla_contacted"])

    def test_wrong_cell_rejected(self):
        self.config["cell_id"] = "another-cell"
        with self.assertRaisesRegex(ValueError, "exact assignment mismatch"):
            runner.check(self.config)

    def test_wrong_purpose_rejected(self):
        self.config["purpose_declaration"] = "unknown"
        with self.assertRaisesRegex(ValueError, "controller purpose changed"):
            runner.check(self.config)


if __name__ == "__main__":
    unittest.main()
