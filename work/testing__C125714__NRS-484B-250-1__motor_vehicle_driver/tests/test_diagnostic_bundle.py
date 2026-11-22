"""CPU bundle checks keep provisional context out of Native acquisition."""
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from case_builder import config
from native_capture import reviewed_context, run_native
from native_driver import control_step
from runner import check_scene


class DiagnosticBundleTests(unittest.TestCase):
    def test_scene_config_binding(self):
        root = Path(__file__).resolve().parents[1]
        scene = json.loads((root / "scene.json").read_text())
        self.assertTrue(scene["diagnostic_only"])
        self.assertEqual(config(check_scene(scene)), json.loads((root / "config.json").read_text()))

    def test_exact_response_variant_requests_next_tick_control(self):
        root = Path(__file__).resolve().parents[1]
        scene = json.loads((root / "scene.json").read_text())
        suffix = scene["case_id"].rsplit("__", 1)[1]
        expected = {"precedence": (True, "yield", "brake"),
                    "advance": (True, "advance", "proceed"),
                    "other_later": (False, "yield", "proceed")}[suffix]
        self.assertEqual((scene["other_entered_first"], scene["ego_response_request"]),
                         expected[:2])
        def body(x, y):
            return [[x-.2, y-.2], [x+.2, y-.2], [x+.2, y+.2], [x-.2, y+.2]]
        state = control_step(scene, {}, frame=0,
                             ego_body=body(-20, -5.75), other_body=body(0, -20))
        self.assertEqual(state["request"], expected[2])

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

    def test_candidate_map_has_declared_cpu_junction_paths(self):
        root = Path(__file__).resolve().parents[1]
        inventory = json.loads((root / "candidate-map-inventory.json").read_text())
        self.assertEqual(inventory["source_sha256"],
                         json.loads((root / "scene.json").read_text())["crossing"]["map_source_sha256"])
        self.assertEqual(len(inventory["junctions"][0]["connections"]), 3)


if __name__ == "__main__":
    unittest.main()
