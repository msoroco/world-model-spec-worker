import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from construct import ConstructionError, construct, load_site


def site():
    return {"case_id": "testing__C111706__NRS-484B-403-3__motor_vehicle_driver__intersection_vehicle_near",
            "map_name": "reviewed-map", "map_sha256": "source-map",
            "district_source_sha256": "source-district",
            "intersection_boundary_source_sha256": "source-boundary",
            "ego_blueprint": "vehicle.test.ego", "other_blueprint": "vehicle.test.other",
            "ego_route": [{"road_id": 7, "lane_id": 1, "junction_id": None},
                          {"road_id": 7, "lane_id": 1, "junction_id": 3},
                          {"road_id": 7, "lane_id": -1, "junction_id": None}],
            "other_route": [{"road_id": 8, "lane_id": 1}], "other_spawn": "other-transform"}


class Actor:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class BlueprintLibrary:
    def find(self, blueprint):
        return blueprint


class Map:
    name = "reviewed-map"


class World:
    def __init__(self, fail_second=False):
        self.calls = []
        self.actors = []
        self.fail_second = fail_second

    def get_map(self):
        return Map()

    def get_blueprint_library(self):
        return BlueprintLibrary()

    def try_spawn_actor(self, blueprint, transform):
        self.calls.append((blueprint, transform))
        if self.fail_second and len(self.calls) == 2:
            return None
        actor = Actor()
        self.actors.append(actor)
        return actor


class ConstructionTest(unittest.TestCase):
    def read(self, value):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "site.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            return load_site(path, hashlib.sha256(path.read_bytes()).hexdigest(),
                             expected_case=value["case_id"])

    def test_source_bound_site_spawns_two_distinct_vehicles(self):
        checked = self.read(site())
        world = World()
        built = construct(world, checked, ego_spawn="ego-transform", other_spawn="other-transform")
        self.assertEqual(world.calls, [("vehicle.test.ego", "ego-transform"),
                                       ("vehicle.test.other", "other-transform")])
        self.assertIsNot(built["ego"], built["other_vehicle"])

    def test_rejects_missing_intersection_geometry_source(self):
        value = site()
        del value["intersection_boundary_source_sha256"]
        with self.assertRaisesRegex(ConstructionError, "boundary source"):
            self.read(value)

    def test_rejects_wrong_destination_lane(self):
        value = site()
        value["ego_route"][-1]["lane_id"] = 1
        with self.assertRaisesRegex(ConstructionError, "opposite lane"):
            self.read(value)

    def test_approach_case_requires_route_outside_junction(self):
        value = site()
        value["case_id"] = value["case_id"].replace("intersection_vehicle_near", "approach_before_intersection")
        with self.assertRaisesRegex(ConstructionError, "intersection occupancy"):
            self.read(value)
        value["ego_route"][1]["junction_id"] = None
        self.assertEqual(self.read(value)["case_id"], value["case_id"])

    def test_second_spawn_failure_destroys_owned_ego(self):
        world = World(fail_second=True)
        with self.assertRaisesRegex(ConstructionError, "other vehicle spawn"):
            construct(world, site(), ego_spawn="ego", other_spawn="other")
        self.assertEqual(len(world.actors), 1)
        self.assertTrue(world.actors[0].destroyed)
