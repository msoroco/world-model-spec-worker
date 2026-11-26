import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner
from native_capture import validate_survey

class BundleTests(unittest.TestCase):
    def test_exact_identity(self):
        self.assertEqual(runner.check(), json.loads((runner.HERE / "config.json").read_text())["selected_case_id"])

    def test_native_source_gate_precedes_carla_import(self):
        with patch("sys.argv", ["runner.py", "--host", "localhost", "--port", "2000", "--output-dir", "attempt"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(ValueError, "source-hashed reviewed site"):
                    runner.main()

    def test_unreviewed_site_rejected(self):
        with self.assertRaisesRegex(ValueError, "reviewed C135087"):
            validate_survey({}, json.loads((runner.HERE / "config.json").read_text())["selected_case_id"])

if __name__ == "__main__":
    unittest.main()
