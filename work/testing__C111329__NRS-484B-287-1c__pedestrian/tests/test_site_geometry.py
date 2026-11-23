import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import compare_marking_cases, compare_operation_cases
from native_route import advance_pedestrian, spawn_pedestrian
from site_geometry import assess_site


class CrossingSiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        sources = {}
        for name in ("map", "route", "devices", "markings", "highway"):
            p = Path(self.tmp.name) / (name + ".json")
            p.write_text(json.dumps({"source": name}))
            sources[name] = {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        self.packet = {
            "sources": sources,
            "coordinate_frame": "map_xy_m",
            "highway": {"boundary_document_id": "h-boundary", "public_access_document_id": "h-access"},
            "junctions": [{"id": "west", "center": [0, 0], "envelope_radius_m": 8}, {"id": "east", "center": [100, 0], "envelope_radius_m": 8}],
            "between_edge": ["west", "east"],
            "intervening_junction_ids": [],
            "pedestrian_route": [[50, -10], [50, 10]],
            "crossing": {"entry": [50, -10], "exit": [50, 10], "time_s": [5, 15]},
            "highway_banks": [[[0, -3], [100, -3]], [[0, 3], [100, 3]]],
            "devices": [
                {"junction_id": j, "device_id": j + "-signal", "authority_record_id": j + "-auth", "placement_record_id": j + "-place", "purpose_record_id": j + "-purpose", "governing_participants": ["pedestrian"], "instructions": "recorded signal state", "operating_intervals_s": [[0, 20]]}
                for j in ("west", "east")
            ],
            "markings": {"survey_complete": True, "marked_crosswalks": []},
        }

    def marked(self):
        packet = copy.deepcopy(self.packet)
        packet["markings"]["marked_crosswalks"] = [{"marking_id": "stripe-1", "survey_record_id": "survey-1", "between_edge_station_fraction": [0.45, 0.55]}]
        return packet

    def test_unmarked_and_marked_comparison(self):
        self.assertFalse(assess_site(self.packet)["marked_crosswalk_present"])
        self.assertTrue(assess_site(self.marked())["marked_crosswalk_present"])
        self.assertEqual(compare_marking_cases(self.packet, self.marked())["case_status"], "source_measurements_compared")

    def test_opposite_approach_direction(self):
        packet = copy.deepcopy(self.packet)
        packet["pedestrian_route"] = list(reversed(packet["pedestrian_route"]))
        packet["crossing"]["entry"], packet["crossing"]["exit"] = packet["crossing"]["exit"], packet["crossing"]["entry"]
        self.assertTrue(assess_site(packet)["crosses_both_highway_banks"])

    def test_rejects_unordered_route(self):
        packet = copy.deepcopy(self.packet)
        packet["crossing"]["entry"], packet["crossing"]["exit"] = packet["crossing"]["exit"], packet["crossing"]["entry"]
        with self.assertRaisesRegex(ValueError, "ordered"):
            assess_site(packet)

    def test_requires_source_hash(self):
        packet = copy.deepcopy(self.packet)
        Path(packet["sources"]["map"]["path"]).write_text("tampered")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            assess_site(packet)

    def test_rejects_intervening_junction(self):
        packet = copy.deepcopy(self.packet)
        packet["intervening_junction_ids"] = ["middle"]
        with self.assertRaisesRegex(ValueError, "direct segment"):
            assess_site(packet)

    def test_rejects_inactive_device(self):
        packet = copy.deepcopy(self.packet)
        packet["devices"][1]["operating_intervals_s"] = [[0, 8]]
        with self.assertRaisesRegex(ValueError, "operation"):
            assess_site(packet)
        self.assertFalse(assess_site(packet, require_operating=False)["device_operation_observed"])
        self.assertEqual(compare_operation_cases(self.packet, packet)["comparison_id"], "both_devices_operating")

    def test_rejects_unobserved_crossing(self):
        packet = copy.deepcopy(self.packet)
        packet["highway_banks"][1] = [[0, 30], [100, 30]]
        with self.assertRaisesRegex(ValueError, "both highway banks"):
            assess_site(packet)

    def test_rejects_missing_authority(self):
        packet = copy.deepcopy(self.packet)
        packet["devices"][0]["authority_record_id"] = ""
        with self.assertRaisesRegex(ValueError, "provenance"):
            assess_site(packet)

    def test_rejects_incomplete_marking_survey(self):
        packet = copy.deepcopy(self.packet)
        packet["markings"]["survey_complete"] = False
        with self.assertRaisesRegex(ValueError, "survey incomplete"):
            assess_site(packet)

    def test_rejects_changed_fixed_device_source(self):
        packet = self.marked()
        new = Path(self.tmp.name) / "other-device.json"
        new.write_text("{}")
        packet["sources"]["devices"] = {"path": str(new), "sha256": hashlib.sha256(new.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError, "fixed source changed"):
            compare_marking_cases(self.packet, packet)

    def test_native_spawn_and_control(self):
        class Location:
            def __init__(self, x, y, z=0):
                self.x, self.y, self.z = x, y, z

        class Transform:
            def __init__(self, location):
                self.location = location

        class Vector3D:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z

        class WalkerControl:
            def __init__(self, direction, speed):
                self.direction, self.speed = direction, speed

        class Carla:
            pass
        Carla.Location = Location
        Carla.Transform = Transform
        Carla.Vector3D = Vector3D
        Carla.WalkerControl = WalkerControl

        class Actor:
            type_id = "walker.pedestrian.0001"
            def __init__(self, location):
                self.location = location
                self.control = None
                self.destroyed = False
            def get_location(self):
                return self.location
            def apply_control(self, control):
                self.control = control
            def destroy(self):
                self.destroyed = True

        class World:
            def get_blueprint_library(self):
                return self
            def find(self, value):
                return value
            def try_spawn_actor(self, blueprint, transform):
                self.blueprint, self.transform = blueprint, transform
                self.actor = Actor(transform.location)
                return self.actor

        self.packet["walker_blueprint_id"] = "walker.pedestrian.0001"
        self.packet["walker_speed_mps"] = 1.2
        world = World()
        actor = spawn_pedestrian(world, self.packet, carla_module=Carla)
        self.assertEqual(world.blueprint, self.packet["walker_blueprint_id"])
        self.assertEqual((world.transform.location.x, world.transform.location.y), (50, -10))
        self.assertEqual(advance_pedestrian(actor, self.packet, 1, carla_module=Carla), 1)
        self.assertAlmostEqual(actor.control.direction.y, 1.0)
        self.assertEqual(actor.control.speed, 1.2)
        actor.location = Location(50, 10)
        self.assertEqual(advance_pedestrian(actor, self.packet, 1, carla_module=Carla), 1)
        self.assertEqual(actor.control.speed, 0.0)

    def test_native_rejects_unverified_blueprint_before_spawn(self):
        packet = copy.deepcopy(self.packet)
        packet["walker_blueprint_id"] = "vehicle.foo"
        packet["walker_speed_mps"] = 1.2
        with self.assertRaisesRegex(ValueError, "walker blueprint"):
            spawn_pedestrian(object(), packet)


if __name__ == "__main__":
    unittest.main()
