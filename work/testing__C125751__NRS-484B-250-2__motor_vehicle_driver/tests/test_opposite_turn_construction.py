import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace


HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("opposite_turn_construction", HERE / "opposite_turn_construction.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def site():
    return {"routes": {"ego": [[-10, 0], [-5, 0], [0, 0], [0, 5]],
                       "other": [[10, 0], [5, 0], [0, 0], [-5, 0]]},
            "expected_approach_lanes": {"ego": [11, -1], "other": [11, 1]}}


class Actor:
    def __init__(self, lane, yaw):
        self.lane, self.yaw, self.destroyed = lane, yaw, False

    def get_location(self):
        return self

    def get_transform(self):
        return SimpleNamespace(rotation=SimpleNamespace(yaw=self.yaw))

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, actors):
        self.actors = actors
        self.index = 0
        self.ticks = 0

    def try_spawn_actor(self, blueprint, transform):
        actor = self.actors[self.index]
        self.index += 1
        return actor

    def tick(self):
        self.ticks += 1

    def get_map(self):
        return self

    def get_waypoint(self, actor, project_to_road):
        return SimpleNamespace(road_id=actor.lane[0], lane_id=actor.lane[1])


class OppositeTurnConstructionTest(unittest.TestCase):
    def test_opposing_left_turn_spawns_and_releases(self):
        actors = [Actor([11, -1], 0), Actor([11, 1], 180)]
        world = World(actors)
        with module.construct_opposite_turn_pair(world, {"ego": "car", "other": "car"},
                                                 {"ego": "pose1", "other": "pose2"}, site(), "ego") as built:
            self.assertEqual(built["geometry"]["approach_separation_deg"], 180)
            self.assertFalse(built["legal_exception_verified"])
            self.assertEqual(world.ticks, 1)
        self.assertTrue(all(actor.destroyed for actor in actors))

    def test_rejects_perpendicular_and_nonleft_routes(self):
        changed = site()
        changed["routes"]["other"] = [[0, -10], [0, -5], [0, 0], [0, 5]]
        with self.assertRaisesRegex(ValueError, "geometrically opposite"):
            module.check_routes(changed["routes"], "ego")
        changed = site()
        changed["routes"]["ego"] = [[-10, 0], [-5, 0], [0, 0], [5, 0]]
        with self.assertRaisesRegex(ValueError, "geometric left"):
            module.check_routes(changed["routes"], "ego")

    def test_rejects_wrong_native_lane_and_cleans_up(self):
        actors = [Actor([11, -1], 0), Actor([12, 1], 180)]
        with self.assertRaisesRegex(ValueError, "outside sourced approach lane"):
            with module.construct_opposite_turn_pair(World(actors), {"ego": "car", "other": "car"},
                                                     {"ego": "pose1", "other": "pose2"}, site(), "ego"):
                pass
        self.assertTrue(all(actor.destroyed for actor in actors))


if __name__ == "__main__":
    unittest.main()
