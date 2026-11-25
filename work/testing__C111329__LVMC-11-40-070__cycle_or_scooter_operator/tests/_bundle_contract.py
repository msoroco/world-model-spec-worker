import json
from pathlib import Path
import unittest
import runner

class BundleCheck(unittest.TestCase):
    def test_exact_identity(self):
        case = runner.check()
        self.assertEqual(case["case_id"], json.loads(Path("config.json").read_text())["selected_case_id"])

    def test_reviewed_source_is_required(self):
        with self.assertRaises(FileNotFoundError):
            runner.preflight_sources(runner.check(), Path("missing-original-site.json"), "0" * 64, None, None)
