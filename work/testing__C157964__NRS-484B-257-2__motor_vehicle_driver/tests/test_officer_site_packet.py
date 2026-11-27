import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from officer_site_packet import REQUIRED, validate_packet
from test_officer_scene import site


class OfficerSitePacketTest(unittest.TestCase):
    def packet(self, root):
        scene = site()
        scene.update({"format": "c157964-reviewed-officer-site-v1",
                      "case_id": "testing__C157964__NRS-484B-257-2__motor_vehicle_driver__occupied_stop", "law_id": "NRS-484B-257-2",
                      "non_through_highway": True,
                      "officer_visible_from_ego_approach": True,
                      "entrances": [{"id": "ego", "control": "yield", "reviewed_source": "map"},
                                    {"id": "other", "control": "none", "reviewed_source": "map"}]})
        scene["sources"] = {}
        for name in REQUIRED:
            raw = (name + " original review").encode()
            filename = name + ".txt"
            (root / filename).write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            scene["sources"][name] = {"path": filename, "sha256": digest}
            if name != "map_opendrive":
                scene[name + "_source_sha256"] = digest
        packet = root / "site.json"
        packet.write_text(json.dumps(scene))
        return packet

    def test_source_bound_site(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as temp:
            packet = self.packet(Path(temp))
            self.assertEqual(validate_packet(packet, "testing__C157964__NRS-484B-257-2__motor_vehicle_driver__occupied_stop")["cell_id"],
                             "C157964")

    def test_changed_source_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as temp:
            packet = self.packet(Path(temp))
            (Path(temp) / "officer_location.txt").write_text("new place")
            with self.assertRaisesRegex(ValueError, "reviewed source changed"):
                validate_packet(packet, "testing__C157964__NRS-484B-257-2__motor_vehicle_driver__occupied_stop")

    def test_wrong_case_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as temp:
            packet = self.packet(Path(temp))
            with self.assertRaisesRegex(ValueError, "exact officer case"):
                validate_packet(packet, "c157964__occupied_proceed")


if __name__ == "__main__":
    unittest.main()
