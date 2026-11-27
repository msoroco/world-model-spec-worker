"""Fake Native world checks actor setup, map binding and cleanup."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from native_taxi_operator import NativeTaxiOperator, read_site

SCRATCH = REPO / ".runtime-work/c378245-native-tests"
SCRATCH.mkdir(parents=True, exist_ok=True)


def site():
    pose = lambda x, y: {"x": x, "y": y, "z": 0.5, "yaw": 0}
    return {
        "source_kind": "original_independent_site_review", "cell_id": "C378245",
        "business_district": True, "map_sha256": hashlib.sha256(b"map-fixture").hexdigest(),
        "designation_id": "stand-fixture",
        "stand_polygon_xy_m": [[0, 0], [5, 0], [5, 4], [0, 4]],
        "street_polygon_xy_m": [[-10, -10], [20, -10], [20, 10], [-10, 10]],
        "native_scene": {
            "taxi_blueprint_id": "vehicle.fixture.taxi",
            "passenger_blueprint_id": "walker.pedestrian.fixture",
            "halt_poses": {"in_stand": pose(2, 2), "outside_stand": pose(8, 2)},
            "passenger_start_pose": pose(9, 3), "passenger_door_pose": pose(8, 2),
            "camera_mounts": {name: {"attach_to": "taxi", "transform": pose(0, 0), "fov_deg": 90}
                              for name in ("overview", "approach", "curb_reference", "passenger_side")},
        },
    }


class Blueprint:
    def __init__(self, name):
        self.name, self.attributes = name, {}

    def set_attribute(self, name, value):
        self.attributes[name] = value


class Blueprints:
    def find(self, name):
        return Blueprint(name)


class Actor:
    def __init__(self, identity, blueprint, transform):
        self.id, self.blueprint, self.transform = identity, blueprint, transform
        self.destroyed = False

    def get_transform(self):
        return self.transform

    def destroy(self):
        self.destroyed = True

    def stop(self):
        pass


class Map:
    def to_opendrive(self):
        return "map-fixture"


class World:
    def __init__(self, fail_on=None):
        self.actors, self.fail_on = [], fail_on

    def get_map(self):
        return Map()

    def get_blueprint_library(self):
        return Blueprints()

    def spawn_actor(self, blueprint, transform, **kwargs):
        if blueprint.name == self.fail_on:
            return None
        actor = Actor(len(self.actors) + 1, blueprint, transform)
        self.actors.append(actor)
        return actor


class Carla:
    class Location:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Rotation:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Transform:
        def __init__(self, location, rotation):
            self.location, self.rotation = location, rotation


class NativeTaxiTests(unittest.TestCase):
    def test_site_source_hash_and_geometry(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as name:
            path = Path(name) / "reviewed-site.json"
            raw = json.dumps(site()).encode()
            path.write_bytes(raw)
            self.assertEqual(read_site(path, hashlib.sha256(raw).hexdigest())["designation_id"], "stand-fixture")
            with self.assertRaisesRegex(ValueError, "SHA256"):
                read_site(path, "0" * 64)

    def test_builds_stand_taxi_and_four_cameras_then_releases(self):
        world = World()
        operator = NativeTaxiOperator(world, Carla, site())
        result = operator.setup({"case_id": "fixture__designated_stand_park", "location_request": "in_stand",
                                 "halt_activity_request": "park", "passenger_exchange_request": "none"})
        self.assertEqual(len(result["camera_actor_ids"]), 4)
        self.assertIsNone(result["passenger_actor_id"])
        self.assertEqual(world.actors[1].blueprint.attributes["image_size_x"], "1920")
        operator.close()
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_loading_spawns_passenger_at_outside_stand(self):
        world = World()
        operator = NativeTaxiOperator(world, Carla, site())
        result = operator.setup({"case_id": "fixture__outside_stand_load", "location_request": "outside_stand",
                                 "halt_activity_request": "temporary_stop", "passenger_exchange_request": "loading"})
        self.assertIsNotNone(result["passenger_actor_id"])
        self.assertEqual(result["reviewed_location"], "outside_stand")
        operator.close()

    def test_camera_failure_releases_owned_taxi(self):
        world = World(fail_on="sensor.camera.rgb")
        operator = NativeTaxiOperator(world, Carla, site())
        with self.assertRaisesRegex(ValueError, "camera spawn"):
            operator.setup({"case_id": "fixture__designated_stand_park", "location_request": "in_stand",
                            "halt_activity_request": "park", "passenger_exchange_request": "none"})
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_native_map_mismatch_rejected_before_spawn(self):
        original = site()
        original["map_sha256"] = "0" * 64
        world = World()
        operator = NativeTaxiOperator(world, Carla, original)
        with self.assertRaisesRegex(ValueError, "OpenDRIVE"):
            operator.setup({"case_id": "fixture__designated_stand_park", "location_request": "in_stand",
                            "halt_activity_request": "park", "passenger_exchange_request": "none"})
        self.assertEqual(world.actors, [])


if __name__ == "__main__":
    unittest.main()
