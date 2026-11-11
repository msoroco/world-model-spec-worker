import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


spec = importlib.util.spec_from_file_location("truck_construction", Path(__file__).resolve().parents[1] / "truck_construction.py")
construction = importlib.util.module_from_spec(spec)
spec.loader.exec_module(construction)


class Actor:
    def __init__(self, location, width):
        self.location = location
        self.bounding_box = NS(extent=NS(x=4.0, y=width / 2))
        self.destroyed = False

    def get_location(self):
        return self.location

    def get_transform(self):
        return NS(get_forward_vector=lambda: NS(x=1, y=0))

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, widths=(2.1, 2.1), lanes=(-1, -1)):
        self.widths, self.lanes, self.actors = widths, lanes, []

    def try_spawn_actor(self, blueprint, transform):
        actor = Actor(transform, self.widths[len(self.actors)])
        self.actors.append(actor)
        return actor

    def get_map(self):
        return self

    def get_waypoint(self, location, project_to_road=False):
        assert project_to_road is False
        return NS(road_id=7, lane_id=self.lanes[0 if location.x < 100 else 1])


class ConstructionTests(unittest.TestCase):
    def test_spawns_checks_and_cleans_up(self):
        world = World()
        with construction.spawn_qualifying_pair(world, "ego", "lead", NS(x=0, y=0),
                                                 NS(x=160, y=0), 7, -1, [1, 0]) as pair:
            self.assertEqual(pair["initial_longitudinal_body_gap_m"], 152)
            self.assertEqual(pair["realized_widths_m"], {"ego": 2.1, "lead": 2.1})
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_rejects_narrow_vehicle_and_wrong_lane_with_cleanup(self):
        for world in (World(widths=(2.0, 2.1)), World(lanes=(-1, -2))):
            with self.assertRaises(ValueError):
                with construction.spawn_qualifying_pair(world, "ego", "lead", NS(x=0, y=0),
                                                         NS(x=160, y=0), 7, -1, [1, 0]):
                    pass
            self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_rejects_overlapping_order(self):
        world = World()
        with self.assertRaisesRegex(ValueError, "overlap"):
            with construction.spawn_qualifying_pair(world, "ego", "lead", NS(x=0, y=0),
                                                     NS(x=5, y=0), 7, -1, [1, 0]):
                pass
        self.assertTrue(all(actor.destroyed for actor in world.actors))


if __name__ == "__main__":
    unittest.main()
