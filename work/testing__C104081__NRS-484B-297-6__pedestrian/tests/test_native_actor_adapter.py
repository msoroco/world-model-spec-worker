"""Exercise source-bound live actor operations with a fake CARLA interface."""
import math
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from geometry import construct
from native_actor_adapter import CarlaActorAdapter, _world_xy
from native_readback import CarlaFrameReader


TRANSFORM = {"x": 100.0, "y": 200.0, "yaw_degrees": 3.0}


class Actor:
    def __init__(self, x, y, rectangle=None):
        self.id = 17
        self.is_alive = True
        self.pose = NS(location=NS(x=x, y=y))
        points = rectangle or [(x-.2, y-.2), (x+.2, y-.2),
                               (x+.2, y+.2), (x-.2, y+.2)]
        self.bounding_box = NS(get_world_vertices=lambda pose: [NS(x=a, y=b) for a, b in points])

    def get_transform(self):
        return self.pose

    def destroy(self):
        self.is_alive = False


class World:
    def __init__(self, rectangle):
        self.rectangle = rectangle
        self.last = None
        self.traffic = Actor(130, 180)

    def get_map(self):
        return NS(name="surveyed-hill-road")

    def get_blueprint_library(self):
        return NS(find=lambda name: name)

    def spawn_actor(self, blueprint, pose):
        rectangle = self.rectangle if blueprint.startswith("static.prop.") else None
        self.last = Actor(pose.location.x, pose.location.y, rectangle)
        return self.last

    def get_actor(self, value):
        return self.traffic if value == 42 else None


class NativeActorAdapterTest(unittest.TestCase):
    def setUp(self):
        scene = construct("exact-case")
        self.shape = scene.obstacles[0]
        self.rectangle = [_world_xy(x, y, TRANSFORM) for x in
                          (self.shape.x0, self.shape.x1) for y in
                          (self.shape.y0, self.shape.y1)]
        self.survey = {
            "map_id": "surveyed-hill-road", "local_to_world": TRANSFORM,
            "obstacle_assets": {self.shape.name: {
                "local_rectangle_m": [self.shape.x0, self.shape.x1, self.shape.y0, self.shape.y1],
                "blueprint_id": "static.prop.surveyed_barrier", "z_m": 0.0}},
            "pedestrian_blueprint": "walker.pedestrian.0001",
            "pedestrian_spawn_z_m": 0.1, "traffic_actor_ids": [42]}
        self.carla = NS(Transform=lambda location, rotation: NS(location=location, rotation=rotation),
                        Location=lambda **values: NS(**values), Rotation=lambda **values: NS(**values))

    def test_spawn_readback_and_original_source_factory(self):
        world = World(self.rectangle)
        adapter = CarlaActorAdapter(world, self.carla, self.survey)
        obstacle = adapter.spawn_obstacle(self.shape, TRANSFORM)
        walker = adapter.spawn_pedestrian((10, 5), TRANSFORM)
        adapter.set_pedestrian_route(walker, ((10, 5), (50, 5)), TRANSFORM)
        self.assertEqual(adapter.readback(walker, [obstacle, walker], world.get_map().name)
                         ["obstacle_count"], 1)
        recorder = object()
        rig = NS(recorder=recorder, sync=lambda frame: {name: frame for name in
                  ("overview", "approach", "reference_corner", "driver_reference")})
        reader = adapter.source_reader_factory(rig)(world, walker,
                    {"design": {"obstruction_kind": "impassable_section"}}, recorder)
        self.assertIsInstance(reader, CarlaFrameReader)
        self.assertEqual(reader.obstruction, obstacle)
        with self.assertRaisesRegex(ValueError, "roster"):
            adapter.survey["traffic_actor_ids"] = []
            adapter.source_reader_factory(rig)(world, walker,
                {"design": {"obstruction_kind": "impassable_section"}}, recorder)

    def test_undersized_obstruction_and_changed_asset_rejected(self):
        world = World([_world_xy(x, y, TRANSFORM) for x in (22, 23) for y in (4, 5)])
        adapter = CarlaActorAdapter(world, self.carla, self.survey)
        with self.assertRaisesRegex(ValueError, "does not cover"):
            adapter.spawn_obstacle(self.shape, TRANSFORM)
        self.assertFalse(world.last.is_alive)
        self.survey["obstacle_assets"][self.shape.name]["local_rectangle_m"][0] = 19
        with self.assertRaisesRegex(ValueError, "does not match exact case"):
            adapter.spawn_obstacle(self.shape, TRANSFORM)


if __name__ == "__main__":
    unittest.main()
