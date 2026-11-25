import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_construction import ASSIGNMENT, LaneChangeController, check_live_world, load_reviewed_site


def reviewed_packet():
    road = "<OpenDRIVE>reviewed</OpenDRIVE>"
    return {
        "reviewed_provenance": {
            "reviewer": "independent geometry reviewer",
            "source_citation": "reviewed original map packet",
            "native_map_name": "TownReviewed",
            "opendrive_sha256": hashlib.sha256(road.encode()).hexdigest(),
            "highway_dedication_source": "reviewed source",
            "public_access_source": "reviewed source",
            "lane_marking_source": "reviewed source"},
        "lanes": {
            name: {"lane_id": name, "travel_direction": "forward",
                   "lane_type": "driving", "marking_visibility": "clearly_marked",
                   "centerline_world_xyz_m": [[i * 5.0, offset, 0.0] for i in range(10)]}
            for name, offset in (("source", 0.0), ("destination", 3.5))},
        "ego_blueprint": "vehicle.test", "ego_spawn_xyz_yaw": [0.0, 0.0, 0.0, 0.0],
        "target_vehicle_blueprint": "vehicle.target", "target_spawn_xyz_yaw": [20.0, 3.5, 0.0, 0.0],
        "change_station_index": 2,
        "camera_poses_xyz_pitch_yaw": {
            "overview": [10, 0, 20, -70, 0],
            "approach": [0, 0, 5, -10, 0],
            "reference_corner": [15, 0, 8, -25, 0],
            "driver_reference": [0, 0, 1.5, 0, 0]}}


class FakeVehicle:
    def __init__(self):
        self.controls = []
        self.lights = []

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=5.0, y=0.0),
                               rotation=SimpleNamespace(yaw=0.0))

    def apply_control(self, control):
        self.controls.append(control)

    def set_light_state(self, state):
        self.lights.append(state)


class FakeCarla:
    VehicleLightState = type("VehicleLightState", (), {
        "LeftBlinker": 4, "__new__": staticmethod(lambda cls, value: value)})

    @staticmethod
    def VehicleControl(**kwargs):
        return kwargs


class NativeConstructionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "reviewed-site.json"
        self.packet = reviewed_packet()
        self.write_packet()

    def write_packet(self):
        self.path.write_text(json.dumps(self.packet) + "\n")
        self.sha = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def load(self, variant="both_observed"):
        return load_reviewed_site(self.path, self.sha, ASSIGNMENT + "__" + variant)

    def test_reviewed_geometry_controls_three_variants(self):
        packet = self.load()
        world = SimpleNamespace(get_map=lambda: SimpleNamespace(
            name="TownReviewed", to_opendrive=lambda: "<OpenDRIVE>reviewed</OpenDRIVE>"))
        check_live_world(world, packet)
        for variant, expected_signal, expected_check in (
                ("both_observed", True, True), ("signal_missing", False, True),
                ("check_missing", True, False)):
            actor = FakeVehicle()
            output = LaneChangeController(packet, variant, FakeCarla).step(actor)
            self.assertEqual(output["signal_requested"], expected_signal)
            self.assertEqual(output["driver_check_requested"], expected_check)
            self.assertEqual(actor.lights[-1], 4 if expected_signal else 0)
            self.assertEqual(len(actor.controls), 1)
            self.assertTrue(0 <= actor.controls[-1]["throttle"] <= 1)

    def test_unreviewed_or_wrong_direction_fails_before_control(self):
        with self.assertRaisesRegex(ValueError, "SHA256"):
            load_reviewed_site(self.path, "0" * 64, ASSIGNMENT + "__both_observed")
        self.packet["lanes"]["destination"]["travel_direction"] = "reverse"
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "same-direction"):
            self.load()
        self.packet["lanes"]["destination"]["travel_direction"] = "forward"
        self.packet["lanes"]["source"]["marking_visibility"] = "unverified"
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "clearly marked"):
            self.load()

    def test_live_map_must_match_reviewed_opendrive(self):
        packet = self.load()
        wrong = SimpleNamespace(get_map=lambda: SimpleNamespace(
            name="TownReviewed", to_opendrive=lambda: "changed"))
        with self.assertRaisesRegex(ValueError, "OpenDRIVE"):
            check_live_world(wrong, packet)


if __name__ == "__main__":
    unittest.main()
