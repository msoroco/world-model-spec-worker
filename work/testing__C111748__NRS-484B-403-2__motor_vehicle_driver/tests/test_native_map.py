import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("device_native_map", ROOT / "native_map.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
CASE = "testing__C111748__NRS-484B-403-2__motor_vehicle_driver__prohibited_attempt"


class Map:
    name = "Town01"
    def __init__(self, source): self.source = source
    def to_opendrive(self): return self.source


class World:
    def __init__(self, source): self.map = Map(source)
    def get_map(self): return self.map


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "site.json"
        self.source = "<OpenDRIVE><road id='1'/></OpenDRIVE>"
        self.site = {"case_id": CASE, "map_name": "Town01",
                     "map_sha256": hashlib.sha256(self.source.encode()).hexdigest(),
                     "highway_status": {"source_sha256": "reviewed-highway"},
                     "ego_blueprint": "vehicle.test", "ego_spawn": [1, 2],
                     "device_blueprint": "static.prop.sign",
                     "u_turn_route": [{"road_id": 1, "lane_id": 1},
                                      {"road_id": 1, "lane_id": 1},
                                      {"road_id": 1, "lane_id": -1}],
                     "device": {"authority_source_sha256": "reviewed-authority",
                                "legal_consistency_source_sha256": "reviewed-law",
                                "display_source_sha256": "reviewed-display",
                                "governed_approach": "A", "position_xy_m": [1, 2],
                                "prohibits_u_turn": True}}
        self.write()

    def write(self):
        raw = json.dumps(self.site).encode()
        self.path.write_bytes(raw)
        self.sha = hashlib.sha256(raw).hexdigest()

    def test_live_opendrive_bound(self):
        receipt = mod.verify(World(self.source), self.path, self.sha, CASE)
        self.assertEqual(receipt["map_sha256"], self.site["map_sha256"])
        self.assertFalse(receipt["physical_turn_verified"])

    def test_reject_different_live_map_bytes(self):
        with self.assertRaisesRegex(mod.MapBindingError, "OpenDRIVE"):
            mod.verify(World(self.source + " changed"), self.path, self.sha, CASE)

    def test_reject_wrong_live_map_name(self):
        world = World(self.source)
        world.map.name = "Town02"
        with self.assertRaisesRegex(mod.MapBindingError, "map name"):
            mod.verify(world, self.path, self.sha, CASE)

    def test_reject_source_tamper(self):
        self.site["device"]["prohibits_u_turn"] = False
        self.path.write_text(json.dumps(self.site))
        with self.assertRaisesRegex(ValueError, "source hash"):
            mod.verify(World(self.source), self.path, self.sha, CASE)
