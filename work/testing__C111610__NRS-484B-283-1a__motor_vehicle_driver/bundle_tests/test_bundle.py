"""Offline checks that run inside one materialized exact-case bundle."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import check


class BundleTests(unittest.TestCase):
    def test_selected_case_and_capture_contract(self):
        case_id = check(ROOT)
        config = json.loads((ROOT / "config.json").read_text())
        scene = json.loads((ROOT / "scene.json").read_text())
        self.assertEqual(case_id, scene["case_id"])
        self.assertEqual(config["frame_count"], 600)
        self.assertEqual(len(config["cameras"]), 4)


if __name__ == "__main__": unittest.main()
