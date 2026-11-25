"""CPU construction tests; fake actors exercise mutation and readback calls."""
import unittest
from types import SimpleNamespace

from native_scene import (BYPASS_Y, CAMERAS, FRAMES, apply_control, check,
                          request, spawn_obstruction, survey)


class _FakeCarla:
    LaneType = SimpleNamespace(Driving="driving", Biking="biking", Shoulder="shoulder",
                               Sidewalk="sidewalk")

    class Location:
        def __init__(self, x=0, y=0, z=0):
            self.x, self.y, self.z = x, y, z

    class Rotation:
        pass

    class Transform:
        def __init__(self, location, rotation=None):
            self.location = location

    class Vector3D:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z

    class WalkerControl:
        def __init__(self, direction, speed, jump):
            self.direction, self.speed, self.jump = direction, speed, jump


class _FakeActor:
    def __init__(self, transform):
        self._transform = transform
        self.bounding_box = SimpleNamespace(extent=SimpleNamespace(x=.4, y=.4, z=.6))
        self.destroyed = False

    def get_transform(self):
        return self._transform

    def destroy(self):
        self.destroyed = True


class _FakeMap:
    def get_waypoint(self, location, project_to_road, lane_type):
        lane_id = ({"driving": -1, "biking": -2, "shoulder": -3, "sidewalk": -4}
                   if lane_type == "biking" or location.y < -5.5 or
                      (lane_type == "shoulder" and location.y < -4) else
                   {"driving": -1, "shoulder": -2, "sidewalk": -3})[lane_type]
        return SimpleNamespace(road_id=2, lane_id=lane_id,
                               lane_type=lane_type,
                               transform=SimpleNamespace(location=location))


class _FakeWorld:
    def __init__(self, fail_spawn=False):
        self.fail_spawn = fail_spawn
        self.actors = []
        self.blueprint = SimpleNamespace(id="static.prop.streetbarrier")

    def get_map(self):
        return _FakeMap()

    def get_blueprint_library(self):
        return SimpleNamespace(filter=lambda pattern: [self.blueprint])

    def try_spawn_actor(self, blueprint, transform):
        if self.fail_spawn and len(self.actors) == 3:
            return None
        actor = _FakeActor(transform)
        self.actors.append(actor)
        return actor


class SceneTests(unittest.TestCase):
    def test_geometry_and_controlled_pair(self):
        self.assertTrue(check()["passed"])
        self.assertEqual(len(CAMERAS), 4)
        for condition in BYPASS_Y:
            rows = [request(condition, frame) for frame in range(FRAMES)]
            self.assertEqual(rows[0]["target_xy_m"][1], -5)
            self.assertLess(rows[250]["target_xy_m"][1], -3.5)
            self.assertEqual(rows[400]["target_xy_m"][1], -5)
            self.assertTrue(all(b["target_xy_m"][0] > a["target_xy_m"][0]
                                for a, b in zip(rows, rows[1:])))
        fixed = ["target_xy_m", "walker_direction_xyz", "walker_speed_mps"]
        self.assertTrue(any(request("condition_a", 250)[key] !=
                            request("condition_b", 250)[key] for key in fixed))
        self.assertEqual(request("condition_a", 250)["target_xy_m"][0],
                         request("condition_b", 250)["target_xy_m"][0])

    def test_actual_control_call(self):
        walker = SimpleNamespace(apply_control=lambda value: setattr(walker, "last", value))
        command = apply_control(walker, _FakeCarla, "condition_a", 250)
        self.assertAlmostEqual(walker.last.speed, command["walker_speed_mps"])
        self.assertFalse(walker.last.jump)
        self.assertAlmostEqual(walker.last.direction.x, 1)

    def test_direction_and_conditional_bicycle_alternatives(self):
        self.assertTrue(check("direction_west")["passed"])
        self.assertTrue(check("bike_impassable")["passed"])
        self.assertLess(request("direction_west", 300)["target_xy_m"][0],
                        request("direction_west", 100)["target_xy_m"][0])
        self.assertEqual(request("bike_passable", 250)["target_xy_m"][1], -4.8)
        self.assertEqual(request("bike_impassable", 250)["target_xy_m"][1], -4.1)
        world = _FakeWorld()
        self.assertEqual(set(survey(world, _FakeCarla, "bike_impassable")["lanes"]),
                         {"roadway", "bicycle", "shoulder", "sidewalk"})
        self.assertEqual(len(spawn_obstruction(world, _FakeCarla,
                                               "bike_impassable")), 15)

    def test_map_and_obstruction_readback(self):
        world = _FakeWorld()
        self.assertEqual(set(survey(world, _FakeCarla)["lanes"]),
                         {"roadway", "shoulder", "sidewalk"})
        actors = spawn_obstruction(world, _FakeCarla)
        self.assertEqual(len(actors), 10)
        self.assertTrue(all(20 <= a.get_transform().location.x <= 30 for a in actors))

    def test_spawn_failure_restores_owned_actors(self):
        world = _FakeWorld(fail_spawn=True)
        with self.assertRaisesRegex(ValueError, "spawn failed"):
            spawn_obstruction(world, _FakeCarla)
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_bad_request_or_missing_blueprint_rejected(self):
        with self.assertRaises(ValueError):
            request("not-a-case", 100)
        with self.assertRaises(ValueError):
            request("condition_a", FRAMES)
        with self.assertRaises(ValueError):
            request("condition_a", 100, lateral_shift_m=.5)
        world = _FakeWorld()
        world.get_blueprint_library = lambda: SimpleNamespace(filter=lambda pattern: [])
        with self.assertRaisesRegex(ValueError, "blueprint"):
            spawn_obstruction(world, _FakeCarla)


if __name__ == "__main__":
    unittest.main()
