import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner

class BundleTests(unittest.TestCase):
    def test_exact_case_and_source_gate(self):
        selected = json.loads((Path(__file__).resolve().parents[1]/"config.json").read_text())["selected_case_id"]
        self.assertEqual(runner.check()["selected_case_id"], selected)
        with patch("sys.argv", ["runner.py", "--host", "localhost", "--port", "2000", "--output-dir", "attempt"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(ValueError, "source-hashed reviewed center-lane"):
                    runner.main()
