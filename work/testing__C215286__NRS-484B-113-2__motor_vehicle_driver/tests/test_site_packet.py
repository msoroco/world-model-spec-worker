import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("site_packet", ROOT / "site_packet.py")
site_packet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_packet)
CASE = "testing__C215286__NRS-484B-113-2__motor_vehicle_driver__reverse_clear"


def transform(source):
    return {"xyz": [1.0, 2.0, 3.0], "rpy": [0.0, 0.0, 0.0], "source": source}


def site():
    return {
        "map_name": "Town", "map_sha256": hashlib.sha256(b"odr").hexdigest(),
        "crosswalk_source": "OpenDRIVE crossing/1", "crosswalk_polygon_xy": [[0, 0], [2, 0], [2, 4], [0, 4]],
        "vehicle_blueprint_id": "vehicle.car", "spawn_transform_source": "waypoint/2",
        "reverse_route_xy": [[5, 2], [1, 2]], "driver_source": "ego/4",
        "district_source": "district/1", "highway_boundary_source": "road/1",
        "crosswalk_marking_source": "lane-marking/1", "vehicle_class_source": "vehicle/1",
        "camera_transforms": {name: transform("station/" + name) for name in site_packet.VIEWS},
        "spawn_transform": transform("waypoint/2"),
    }


class SitePacketTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(dir=pathlib.Path.cwd() / ".runtime-work")
        self.addCleanup(self.scratch.cleanup)
        self.root = pathlib.Path(self.scratch.name)
        self.source = self.root / "source.json"
        self.packet = self.root / "packet.json"
        self.original = site()
        self.write()

    def write(self):
        raw = json.dumps(self.original, sort_keys=True).encode()
        self.source.write_bytes(raw)
        self.authored = dict(self.original, case_id=CASE,
                             site_source_path=str(self.source),
                             site_source_sha256=hashlib.sha256(raw).hexdigest())
        self.packet.write_text(json.dumps(self.authored))

    def test_valid_source_and_original_map(self):
        packet, packet_bytes, source_bytes = site_packet.read(self.packet, CASE)
        self.assertEqual(packet_bytes, self.packet.read_bytes())
        self.assertEqual(source_bytes, self.source.read_bytes())
        world = type("World", (), {"get_map": lambda self: type("Map", (), {
            "name": "Town", "to_opendrive": lambda self: "odr"})()})()
        self.assertEqual(site_packet.check_world(world, packet), self.original["map_sha256"])

    def test_reject_modified_original_document(self):
        self.source.write_text(self.source.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "hash differs"):
            site_packet.read(self.packet, CASE)

    def test_reject_changed_packet_geometry(self):
        self.authored["crosswalk_polygon_xy"][0] = [-1, 0]
        self.packet.write_text(json.dumps(self.authored))
        with self.assertRaisesRegex(ValueError, "crosswalk_polygon_xy"):
            site_packet.read(self.packet, CASE)

    def test_reject_missing_camera_station(self):
        self.original["camera_transforms"].pop("overview")
        self.write()
        with self.assertRaisesRegex(ValueError, "four original camera"):
            site_packet.read(self.packet, CASE)

    def test_reject_wrong_map_bytes(self):
        packet, _, _ = site_packet.read(self.packet, CASE)
        world = type("World", (), {"get_map": lambda self: type("Map", (), {
            "name": "Town", "to_opendrive": lambda self: "changed"})()})()
        with self.assertRaisesRegex(ValueError, "OpenDRIVE bytes"):
            site_packet.check_world(world, packet)


if __name__ == "__main__":
    unittest.main()
