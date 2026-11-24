import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner
import reviewed_sources
import saved_encounter


class BundleTests(unittest.TestCase):
    def test_exact_case_preflight(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_refuses_unsourced_native_run(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed Native map"):
                runner.main()

    def test_materialized_source_processors_keep_assignment_identity(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
        self.assertEqual(reviewed_sources.ASSIGNMENT_ID, config["assignment_id"])
        self.assertEqual(saved_encounter.ASSIGNMENT_ID, config["assignment_id"])


if __name__ == "__main__":
    unittest.main()
