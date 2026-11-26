import json
from pathlib import Path
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner

class BundleTests(unittest.TestCase):
    def test_exact_case(self):
        self.assertEqual(runner.check()[0], json.loads((runner.HERE / "config.json").read_text())["selected_case_id"])

    def test_reviewed_sources_required_before_carla(self):
        with patch("sys.argv", ["runner.py", "--host", "localhost", "--port", "2000", "--output-dir", "attempt"]):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(ValueError, "source-hashed reviewed crosswalk site"):
                    runner.main()

if __name__ == "__main__":
    unittest.main()
