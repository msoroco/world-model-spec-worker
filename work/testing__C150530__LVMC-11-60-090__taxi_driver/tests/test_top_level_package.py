import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_top_level import build


class TopLevelPackageTest(unittest.TestCase):
    def test_materialized_cpu_package_matches_authored_sources(self):
        construction = build()
        self.assertEqual(json.loads((ROOT / "construction.json").read_text()), construction)
        files = {item["path"]: item["content"] for item in construction["files"]}
        self.assertEqual((ROOT / "runner.py").read_text(), files["runner.py"])
        self.assertEqual((ROOT / "config.json").read_text(), files["config.json"])
        self.assertEqual(construction["recording_description"],
                         json.loads((ROOT / "config.json").read_text())["case"]["recording_description"])
        for case in ("near_stand", "far_stand", "near_stand_straight"):
            self.assertIn("testing__C150530__LVMC-11-60-090__taxi_driver__" + case,
                          json.loads((ROOT / "config.json").read_text())["supported_case_ids"])


if __name__ == "__main__":
    unittest.main()
