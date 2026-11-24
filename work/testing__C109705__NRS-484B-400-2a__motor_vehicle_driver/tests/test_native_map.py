import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from native_map import verify_live_map
from test_approach import context


CASE = "testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__near_centerline"


class FakeWorld:
    def __init__(self, name="TownTest", source="<OpenDRIVE>surveyed</OpenDRIVE>"):
        self.map = SimpleNamespace(name=name, to_opendrive=lambda: source)

    def get_map(self):
        return self.map


class NativeMapTests(unittest.TestCase):
    def test_exact_loaded_map_source_and_case_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            packet_path = Path(temp) / "map-packet.json"
            source = "<OpenDRIVE>surveyed</OpenDRIVE>"
            packet = {"context": context(), "map_name": "TownTest",
                      "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                      "left_turn_route_waypoint_ids": [11, 12, 13],
                      "ego_blueprint_id": "vehicle.test",
                      "camera_plan": "four cameras, 20 Hz"}
            packet_path.write_text(json.dumps(packet))
            bound = verify_live_map(FakeWorld(), packet_path, CASE)
            self.assertEqual(bound["opendrive_sha256"], packet["source_sha256"])
            self.assertEqual(bound["planned_construction"]["case_id"], CASE)
            self.assertFalse(bound["public_highway_reviewed"])
            with self.assertRaisesRegex(ValueError, "OpenDRIVE hash"):
                verify_live_map(FakeWorld(source="different"), packet_path, CASE)
            with self.assertRaisesRegex(ValueError, "map identity"):
                verify_live_map(FakeWorld(name="TownOther"), packet_path, CASE)
            with self.assertRaisesRegex(ValueError, "unassigned exact case"):
                verify_live_map(FakeWorld(), packet_path, CASE + "__foreign")
            packet["context"]["intersecting_roads"][1]["lanes"] = []
            packet_path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "two-directional"):
                verify_live_map(FakeWorld(), packet_path, CASE)


if __name__ == "__main__":
    unittest.main()
