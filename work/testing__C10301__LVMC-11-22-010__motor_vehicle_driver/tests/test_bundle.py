import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_scene_and_controller_profile(self):
        self.assertEqual(runner.check(), json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())["selected_case_id"])

    def test_diagnostic_bundle_refuses_capture(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "diagnostic capture refused"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
