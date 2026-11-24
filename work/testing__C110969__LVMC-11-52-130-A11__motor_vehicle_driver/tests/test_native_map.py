import hashlib
import json
import pathlib
import sys
import tempfile
import unittest


BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from native_map import PREFIX, SUFFIXES, bind


class FakeMap:
    name = "TownDiagnostic"

    def to_opendrive(self):
        return "diagnostic OpenDRIVE"


class FakeWorld:
    def get_map(self):
        return FakeMap()


class NativeMapBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name) / "map-packet.json"
        self.packet = {
            "case_ids": sorted(PREFIX + suffix for suffix in SUFFIXES),
            "map_name": "TownDiagnostic",
            "opendrive_sha256": hashlib.sha256(b"diagnostic OpenDRIVE").hexdigest(),
            "geometry_provenance": "diagnostic CPU fixture only",
            "boundary_review_source_sha256": "a" * 64,
            "intersection_boundary_local_m": {
                "west": -8, "south": -8, "east": 8, "north": 8},
            "approach": "east", "route_waypoint_ids": [11, 12, 13],
            "local_transform_source_sha256": "b" * 64,
            "vehicle_length_m": 4.5, "vehicle_width_m": 1.8}
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.packet))

    def test_exact_source_and_case_bind(self):
        result = bind(FakeWorld(), self.path, PREFIX + "stop_14ft")
        self.assertEqual(result["requested_gap_ft"], 14)
        self.assertAlmostEqual(result["requested_local_pose"]["x_m"],
                               8 + 14 * 0.3048 + 2.25)
        self.assertEqual(result["physical_realization"], "pending")

    def test_wrong_source_and_unreviewed_geometry_rejected(self):
        self.packet["opendrive_sha256"] = "c" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "OpenDRIVE"):
            bind(FakeWorld(), self.path, PREFIX + "stop_14ft")
        self.packet["opendrive_sha256"] = hashlib.sha256(b"diagnostic OpenDRIVE").hexdigest()
        self.packet["boundary_review_source_sha256"] = ""
        self.save()
        with self.assertRaisesRegex(ValueError, "boundary review"):
            bind(FakeWorld(), self.path, PREFIX + "stop_14ft")

    def test_missing_case_or_route_rejected(self):
        with self.assertRaisesRegex(ValueError, "Wrong exact case"):
            bind(FakeWorld(), self.path, PREFIX + "unknown")
        self.packet["route_waypoint_ids"] = []
        self.save()
        with self.assertRaisesRegex(ValueError, "approach/route"):
            bind(FakeWorld(), self.path, PREFIX + "stop_14ft")


if __name__ == "__main__":
    unittest.main()
