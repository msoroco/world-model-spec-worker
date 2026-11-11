import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_construction_probe import check_config


class SelectedCaseConfigTest(unittest.TestCase):
    def test_materialized_exact_case(self):
        config_path = Path(__file__).resolve().parents[1] / "config.json"
        if not config_path.exists():
            self.skipTest("Materialized exact construction only")
        config = json.loads(config_path.read_text())
        suffix = check_config(config)
        self.assertEqual(config["selected_case_id"].rsplit("__", 1)[-1], suffix)
        self.assertEqual(config["case"]["case_id"], config["selected_case_id"])


if __name__ == "__main__":
    unittest.main()
