import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yield_construction import stage_case
from yield_stage import PREFIX, primary


class Actors:
    def __init__(self, other_stop):
        self.other_stop = other_stop

    def filter(self, pattern):
        if pattern == "traffic.stop*" and not self.other_stop:
            return []
        return [NS(id=90 if pattern == "traffic.stop*" else 88,
                   trigger_volume=NS(contains=lambda point, transform: True),
                   get_transform=lambda: None)]


class World:
    def __init__(self, other_stop=False):
        self.actors = Actors(other_stop)
        self.destroyed = []
        self.spawned = []
        self.probes = {(-20, 1.8): (158208, -1, False),
                       (0, 1.8): (158210, -1, True),
                       (1.8, 20): (158212, -1, False),
                       (1.8, 0): (158213, -1, True),
                       (-1.8, -20): (158214, 1, False),
                       (-60, 1.8): (158208, -1, False),
                       (1.8, -4): (158213, -1, True),
                       (1.8, 25): (158212, -1, False)}

    def get_map(self):
        return NS(name="signed-map", get_waypoint=self.get_waypoint)

    def get_waypoint(self, location, project_to_road=False):
        road, lane, junction = self.probes[(location.x, location.y)]
        return NS(road_id=road, lane_id=lane, is_junction=junction,
                  transform=NS(location=location))

    def get_actors(self):
        return self.actors

    def get_blueprint_library(self):
        return NS(find=lambda blueprint: blueprint)

    def try_spawn_actor(self, blueprint, transform):
        actor = NS(id=len(self.spawned) + 1, type_id=blueprint,
                   get_location=lambda: transform.location,
                   destroy=lambda: self.destroyed.append(transform.location))
        self.spawned.append(actor)
        return actor


class ConstructionTests(unittest.TestCase):
    location = staticmethod(lambda x, y, z: NS(x=x, y=y, z=z))

    def test_inside_approaching_and_obligated_spawn_on_different_native_lanes(self):
        for kind, other_stop, expected_road in (("yield_other_inside", False, 158213),
                                                ("yield_other_approaching", False, 158212),
                                                ("yield_other_obligated", True, 158213)):
            world = World(other_stop)
            with stage_case(world, primary(PREFIX + kind), location_factory=self.location) as actors:
                self.assertEqual(len(world.spawned), 2)
                self.assertEqual(world.get_waypoint(actors["other"].get_location()).road_id, expected_road)
                self.assertEqual(actors["site"]["native_other_stop_sign_id"], 90 if other_stop else None)
            self.assertEqual(len(world.destroyed), 2)

    def test_officer_case_refuses_unsourced_actor_and_cleans_up(self):
        world = World()
        with self.assertRaisesRegex(ValueError, "sourced Native officer"):
            with stage_case(world, primary(PREFIX + "officer_control_exception"),
                            location_factory=self.location):
                pass
        self.assertEqual(len(world.destroyed), 2)


if __name__ == "__main__":
    unittest.main()
