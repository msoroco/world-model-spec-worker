"""Offline checks for a materialized reviewed-source Native bundle."""
import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from case_builder import config
from runner import check_scene, resolve_reviewed_source


class ReviewedDeliveryBundleTest(unittest.TestCase):
    def test_scene_packet_map_and_sources(self):
        scene_path = ROOT / "scene.json"
        scene = check_scene(json.loads(scene_path.read_text()))
        if scene["diagnostic_only"]:
            self.skipTest("assignment root is a diagnostic bundle")
        self.assertIs(scene["diagnostic_only"], False)
        self.assertEqual(json.loads((ROOT / "config.json").read_text()), config(scene))
        packet_path = resolve_reviewed_source(scene, scene_path)
        packet = json.loads(packet_path.read_text())
        self.assertIs(packet["diagnostic_only"], False)
        self.assertEqual(packet["crossing"], scene["crossing"])
        map_hash = hashlib.sha256((ROOT / "reviewed-map.xodr").read_bytes()).hexdigest()
        self.assertEqual(map_hash, scene["crossing"]["map_source_sha256"])
        for key in ("public_access_source", "device_inventory_source", "driver_scope_source"):
            descriptor = packet["law_context"][key]
            path = (packet_path.parent / descriptor["source_path"]).resolve()
            self.assertTrue(path.is_relative_to(ROOT))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             descriptor["source_sha256"])


if __name__ == "__main__":
    unittest.main()
