"""CPU proof of the Native review packet's retained byte joins."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from preflight_reviewed_packet import preflight


class ReviewedPacketPreflightTest(unittest.TestCase):
    def fixture(self, directory):
        directory = Path(directory)
        scene = json.loads((ROOT / "scene.json").read_text())
        packet = json.loads((ROOT / "diagnostic-context.json").read_text())
        scene["diagnostic_only"] = False
        packet["diagnostic_only"] = False
        law = packet["law_context"]
        law["public_access"] = True
        law["human_driver"] = True
        sources = {}
        for key in ("public_access_source", "device_inventory_source", "driver_scope_source"):
            source = directory / (key + ".txt")
            source.write_text("synthetic packet protocol fixture: " + key)
            sources[key] = source
            law[key] = {"source_path": source.name,
                        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "reviewer": "CPU fixture", "source_citation": "fixture only"}
        packet_path = directory / "reviewed.json"
        packet_path.write_text(json.dumps(packet))
        scene["reviewed_context_source"] = packet_path.name
        scene["reviewed_context_sha256"] = hashlib.sha256(packet_path.read_bytes()).hexdigest()
        scene_path = directory / "scene.json"
        scene_path.write_text(json.dumps(scene))
        return scene_path, packet_path, sources

    def test_retains_exact_sources_and_rejects_tampering(self):
        with TemporaryDirectory() as directory:
            scene, packet, sources = self.fixture(directory)
            map_path = ROOT / "candidate-map.xodr"
            receipt = preflight(scene, map_path, Path(directory) / "retained")
            self.assertTrue(receipt["passed"])
            self.assertFalse(receipt["native_started"])
            self.assertEqual(receipt["source_packet_sha256"],
                             hashlib.sha256(packet.read_bytes()).hexdigest())
            sources["device_inventory_source"].write_text("changed")
            with self.assertRaisesRegex(ValueError, "device_inventory_source original bytes"):
                preflight(scene, map_path, Path(directory) / "tampered")

    def test_rejects_diagnostic_and_wrong_map(self):
        with TemporaryDirectory() as directory:
            scene_path, packet_path, _ = self.fixture(directory)
            scene = json.loads(scene_path.read_text())
            scene["diagnostic_only"] = True
            scene_path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "nondiagnostic scene"):
                preflight(scene_path, ROOT / "candidate-map.xodr", Path(directory) / "diagnostic")
            scene["diagnostic_only"] = False
            scene_path.write_text(json.dumps(scene))
            wrong_map = Path(directory) / "wrong.xodr"
            wrong_map.write_text("not the reviewed map")
            with self.assertRaisesRegex(ValueError, "OpenDRIVE bytes differ"):
                preflight(scene_path, wrong_map, Path(directory) / "wrong-map")
            packet = json.loads(packet_path.read_text())
            packet["diagnostic_only"] = True
            packet_path.write_text(json.dumps(packet))
            scene["reviewed_context_sha256"] = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            scene_path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "nondiagnostic packet"):
                preflight(scene_path, ROOT / "candidate-map.xodr", Path(directory) / "wrong-packet")

    def test_crlf_map_bytes_match_live_map_identity(self):
        with TemporaryDirectory() as directory:
            scene_path, packet_path, _ = self.fixture(directory)
            map_path = Path(directory) / "reviewed-crlf.xodr"
            original = (ROOT / "candidate-map.xodr").read_bytes()
            map_path.write_bytes(original.replace(b"\n", b"\r\n"))
            map_sha = hashlib.sha256(map_path.read_bytes()).hexdigest()
            scene = json.loads(scene_path.read_text())
            packet = json.loads(packet_path.read_text())
            for item in (scene, packet):
                item["crossing"]["map_source_sha256"] = map_sha
            packet["law_context"]["map_source"] = map_sha
            packet_path.write_text(json.dumps(packet))
            scene["reviewed_context_sha256"] = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            scene_path.write_text(json.dumps(scene))
            receipt = preflight(scene_path, map_path, Path(directory) / "preflight-crlf")
            self.assertTrue(receipt["passed"])
            self.assertEqual(receipt["map_sha256"], map_sha)


if __name__ == "__main__":
    unittest.main()
