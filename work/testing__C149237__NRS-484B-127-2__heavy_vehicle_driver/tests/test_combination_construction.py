"""Synthetic CPU checks for the unselected combination construction draft."""

import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "combination_construction.py"
SPEC = importlib.util.spec_from_file_location("combination_construction", SOURCE)
combination = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(combination)


class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y


class Box:
    def __init__(self, width, length):
        self.width, self.length = width, length

    def get_world_vertices(self, actor):
        return [Point(actor.x + dx, actor.y + dy)
                for dx in (-self.length / 2, self.length / 2)
                for dy in (-self.width / 2, self.width / 2)]


class Actor:
    def __init__(self, x, y, width, length, parent=None):
        self.x, self.y, self.parent = x, y, parent
        self.bounding_box = Box(width, length)
        self.destroyed = False

    def get_transform(self):
        return self

    def get_location(self):
        return self

    def destroy(self):
        self.destroyed = True


class Map:
    def get_waypoint(self, location, project_to_road=False):
        if project_to_road or abs(location.y + 1.9) > 0.01:
            return None
        return type("Waypoint", (), {"road_id": 4, "lane_id": -1})()


class World:
    def __init__(self, fail_trailer=False):
        self.actors = []
        self.fail_trailer = fail_trailer

    def try_spawn_actor(self, blueprint, transform, attach_to=None, attachment_type=None):
        if attach_to is not None and (self.fail_trailer or attachment_type != "Rigid"):
            return None
        x = transform["x"] + (attach_to.x if attach_to else 0)
        y = transform["y"] + (attach_to.y if attach_to else 0)
        actor = Actor(x, y, transform["width"], transform["length"], attach_to)
        self.actors.append(actor)
        return actor

    def tick(self):
        return 1

    def get_map(self):
        return Map()


def inputs(width=2.2, hitch_x=-10):
    blueprints = {role: {"tractor": role + "-tractor", "trailer": role + "-trailer"}
                  for role in ("ego", "lead")}
    transforms = {
        role: {"tractor": {"x": x, "y": -1.9, "width": width, "length": 4},
               "trailer": {"x": hitch_x, "y": 0, "width": width, "length": 8}}
        for role, x in (("ego", 100), ("lead", 300))}
    return blueprints, transforms


class CombinationConstructionTests(unittest.TestCase):
    def test_pair_measures_combined_body_gap_and_releases_all_actors(self):
        world = World()
        blueprints, transforms = inputs()
        with combination.spawn_combination_pair(
            world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
            lane_forward_xy=[1, 0]) as pair:
            self.assertAlmostEqual(pair["initial_longitudinal_body_gap_m"], 184)
            self.assertFalse(pair["native_attachment_verified"])
            self.assertFalse(pair["legal_vehicle_class_verified"])
            self.assertEqual(len(world.actors), 4)
            self.assertIs(world.actors[1].parent, world.actors[0])
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_failed_attachment_cleans_up_owned_tractor(self):
        world = World(fail_trailer=True)
        blueprints, transforms = inputs()
        with self.assertRaisesRegex(ValueError, "trailer attachment failed"):
            with combination.spawn_combination_pair(
                world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
                lane_forward_xy=[1, 0]):
                pass
        self.assertEqual(len(world.actors), 1)
        self.assertTrue(world.actors[0].destroyed)

    def test_rejects_subthreshold_combined_width(self):
        world = World()
        blueprints, transforms = inputs(width=1.9)
        with self.assertRaisesRegex(ValueError, "below 80-inch width"):
            with combination.spawn_combination_pair(
                world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
                lane_forward_xy=[1, 0]):
                pass
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_rejects_unjoined_trailer_geometry(self):
        world = World()
        blueprints, transforms = inputs(hitch_x=-30)
        with self.assertRaisesRegex(ValueError, "planned hitch"):
            with combination.spawn_combination_pair(
                world, blueprints, transforms, "Rigid", road_id=4, lane_id=-1,
                lane_forward_xy=[1, 0]):
                pass
        self.assertTrue(all(actor.destroyed for actor in world.actors))


if __name__ == "__main__":
    unittest.main()
