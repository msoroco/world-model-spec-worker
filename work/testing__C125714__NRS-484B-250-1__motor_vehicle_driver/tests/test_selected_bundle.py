"""Offline checks for a source-gated exact crossing construction."""
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from case_builder import config
from runner import check_scene, reviewed_source


class SelectedBundleTest(unittest.TestCase):
    def test_exact_scene_and_config(self):
        scene = check_scene(json.loads((ROOT / "scene.json").read_text()))
        actual = json.loads((ROOT / "config.json").read_text())
        for key, value in config(scene).items():
            self.assertEqual(actual[key], value)
        self.assertFalse(scene["diagnostic_only"])
        self.assertEqual(actual["selected_case_id"], scene["case_id"])

    def test_native_needs_separately_reviewed_packet(self):
        scene = json.loads((ROOT / "scene.json").read_text())
        with self.assertRaisesRegex(ValueError, "source-hashed reviewed crossing packet"):
            reviewed_source(scene, None, None)


if __name__ == "__main__":
    unittest.main()
