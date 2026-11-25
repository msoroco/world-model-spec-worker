import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_setup import create, validate_spawn
import test_red_left_measurement as fixture


class Actor:
    def __init__(self, number):
        self.id = number
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, fail_index=None):
        self.signal = Actor(7)
        self.spawned = []
        self.fail_index = fail_index

    def get_actors(self):
        return [self.signal]

    def get_blueprint_library(self):
        return self

    def find(self, name):
        return name

    def try_spawn_actor(self, blueprint, transform):
        if len(self.spawned) == self.fail_index:
            return None
        actor = Actor(len(self.spawned) + 10)
        self.spawned.append(actor)
        return actor


class NativeSetupTest(unittest.TestCase):
    write_packet = fixture.RedLeftMeasurementTest.write_packet
    def setUp(self):
        fixture.RedLeftMeasurementTest.setUp(self)
        self.packet["spawn_plan"] = {"ego": {"lane_id": "left", "location_xyz_m": [0, 3.5, 0],
                                             "rotation_rpy_deg": [0, 0, 0], "blueprint_id": "vehicle.test",
                                             "source_citation": "fixture-map"},
                                     "pedestrians": [], "other_traffic": []}
        self.write_packet()

    def test_lazy_native_spawn_and_cleanup(self):
        world = World()
        actors = create(world, self.packet_path, lambda xyz, rpy: (xyz, rpy))
        self.assertEqual(actors.signal.id, 7)
        self.assertEqual(len(world.spawned), 1)
        actors.close()
        self.assertTrue(world.spawned[0].destroyed)

    def test_reject_downstream_spawn(self):
        self.packet["spawn_plan"]["ego"]["location_xyz_m"] = [9, 3.5, 0]
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "not upstream"):
            validate_spawn(self.packet_path)

    def test_reject_uncited_participant(self):
        self.packet["spawn_plan"]["pedestrians"].append({"blueprint_id": "walker.test",
            "location_xyz_m": [12, 4, 0], "rotation_rpy_deg": [0, 0, 90],
            "route_points_xyz_m": [[12, 4, 0], [12, 6, 0]]})
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "uncited participant"):
            validate_spawn(self.packet_path)

    def test_reject_missing_signal(self):
        world = World()
        world.signal.id = 99
        with self.assertRaisesRegex(ValueError, "signal actor absent"):
            create(world, self.packet_path, lambda xyz, rpy: (xyz, rpy))

    def test_rollback_on_spawn_failure(self):
        self.packet["spawn_plan"]["pedestrians"].append({"blueprint_id": "walker.test",
            "location_xyz_m": [12, 4, 0], "rotation_rpy_deg": [0, 0, 90],
            "route_points_xyz_m": [[12, 4, 0], [12, 6, 0]],
            "source_citation": "fixture-map", "route_source_citation": "fixture-map"})
        self.write_packet()
        world = World(fail_index=1)
        with self.assertRaisesRegex(ValueError, "spawn failed"):
            create(world, self.packet_path, lambda xyz, rpy: (xyz, rpy))
        self.assertTrue(world.spawned[0].destroyed)

    def test_inner_lane_variant_uses_reviewed_inner_spawn(self):
        variables = {"approach_position": "inner_lane", "receiving_direction": "one_way_left"}
        with self.assertRaisesRegex(ValueError, "requested approach lane"):
            validate_spawn(self.packet_path, variables)
        self.packet["spawn_plan"]["ego"]["lane_id"] = "inner"
        self.packet["spawn_plan"]["ego"]["location_xyz_m"] = [0, 0, 0]
        self.write_packet()
        actors = create(World(), self.packet_path, lambda xyz, rpy: (xyz, rpy), variables)
        actors.close()

    def test_two_way_variant_requires_distinct_reviewed_route(self):
        variables = {"approach_position": "extreme_left", "receiving_direction": "two_way"}
        with self.assertRaisesRegex(ValueError, "inventory"):
            validate_spawn(self.packet_path, variables)
        route = self.root / "two_way_routes.txt"
        route.write_text("fixture-two-way")
        import hashlib
        self.packet["sources"].pop("one_way_routes")
        self.packet["sources"]["two_way_routes"] = {
            "path": route.name, "sha256": hashlib.sha256(route.read_bytes()).hexdigest(),
            "citation": "fixture-two-way", "reviewer": "fixture"}
        self.packet["receiving_one_way_to_left"] = False
        self.packet["receiving_two_way"] = True
        self.write_packet()
        validate_spawn(self.packet_path, variables)

    def test_conflict_variant_requires_sourced_participant(self):
        variables = {"conflict_response_request": "pedestrian_yield"}
        with self.assertRaisesRegex(ValueError, "requested pedestrian conflict"):
            validate_spawn(self.packet_path, variables)
