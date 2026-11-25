import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class ExactBundleTests(unittest.TestCase):
    def test_exact_case_and_source_gate(self):
        case = runner.check()
        self.assertEqual(case["selected_case_id"], json.loads(Path("config.json").read_text())["selected_case_id"])
        with self.assertRaisesRegex(ValueError, "reviewed original C111610 red-arrow site packet missing"):
            runner.run_native(Path.cwd(), Path("unused-output"), Path.cwd())


if __name__ == "__main__":
    unittest.main()
