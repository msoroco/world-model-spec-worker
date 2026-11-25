"""Offline source precheck for a materialized exact pedestrian case."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check


class SelectedBundleTests(unittest.TestCase):
    def test_exact_reviewed_scene_and_source_snapshots(self):
        root = Path.cwd()
        if not (root / "scene.json").is_file():
            self.skipTest("reviewed scene is supplied only in the offline materialized bundle")
        selected = json.loads((root / "config.json").read_text())["selected_case_id"]
        scene = check(root)
        self.assertEqual(scene["case_id"], selected)
        self.assertEqual(scene["planned_frames"], 240)
        self.assertEqual(scene["fixed_delta_seconds"], .05)


if __name__ == "__main__":
    unittest.main()
