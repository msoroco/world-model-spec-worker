"""CPU bundle checks keep provisional context out of Native acquisition."""
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from case_builder import config
from native_capture import reviewed_context, run_native
from runner import check_scene


class DiagnosticBundleTests(unittest.TestCase):
    def test_scene_config_binding(self):
        root = Path(__file__).resolve().parents[1]
        scene = json.loads((root / "scene.json").read_text())
        self.assertTrue(scene["diagnostic_only"])
        self.assertEqual(config(check_scene(scene)), json.loads((root / "config.json").read_text()))

    def test_provisional_packet_rejected_before_native_capture(self):
        root = Path(__file__).resolve().parents[1]
        scene = json.loads((root / "scene.json").read_text())
        packet = json.loads((root / "diagnostic-context.json").read_text())
        self.assertFalse(packet["law_context"]["public_access"])
        scene["reviewed_context_source"] = str(root / "diagnostic-context.json")
        class FakeMap:
            def to_opendrive(self):
                return (root / "candidate-map.xodr").read_text()
        class FakeWorld:
            def get_map(self):
                return FakeMap()
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "public driver scope"):
                reviewed_context(scene, directory, FakeWorld())

    def test_diagnostic_scene_cannot_start_native(self):
        root = Path(__file__).resolve().parents[1]
        scene = json.loads((root / "scene.json").read_text())
        with self.assertRaisesRegex(ValueError, "diagnostic scene"):
            run_native(scene, root, "127.0.0.1", 2000)

    def test_candidate_map_has_no_connected_junction(self):
        root = Path(__file__).resolve().parents[1]
        inventory = json.loads((root / "candidate-map-inventory.json").read_text())
        self.assertEqual(inventory["source_sha256"],
                         json.loads((root / "scene.json").read_text())["crossing"]["map_source_sha256"])
        self.assertFalse(any(junction["connections"] for junction in inventory["junctions"]))


if __name__ == "__main__":
    unittest.main()
