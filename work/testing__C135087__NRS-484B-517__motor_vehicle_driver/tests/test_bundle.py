"""Exact stand bundle and unsourced launch checks."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner
from stand import SourceError


class BundleTests(unittest.TestCase):
    def test_exact_source_gated_case(self):
        config, case = runner.check()
        self.assertEqual(case["case_id"], config["selected_case_id"])

    def test_original_records_required(self):
        with self.assertRaisesRegex(SourceError, "reviewed original stand"):
            runner.run(None, None, None, None)


if __name__ == "__main__":
    unittest.main()
