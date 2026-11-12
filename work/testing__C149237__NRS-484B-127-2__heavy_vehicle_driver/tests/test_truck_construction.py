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

    def set_transform(self, transform):
        self.location = transform


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

    def test_realized_lengths_place_all_exact_gap_cases(self):
        class AuthoredWorld(World):
            def get_waypoint(self, location, project_to_road=False):
                return NS(road_id=149237, lane_id=-1)

            def tick(self):
                pass

        def transform_at(x, y, heading):
            self.assertEqual(heading, 0)
            return NS(x=x, y=y)

        for name, target in construction._site.GAP_TARGETS_M.items():
            world = AuthoredWorld()
            with construction.spawn_exact_gap_pair(world, NS(id='vehicle.carlamotors.european_hgv'),
                                                   NS(id='vehicle.carlamotors.carlacola'), name,
                                                   transform_at) as pair:
                self.assertAlmostEqual(pair['initial_body_gap_m'], target)
                self.assertEqual(pair['site']['same_direction_lane_count'], 1)
            self.assertTrue(all(a.destroyed for a in world.actors))

    def test_exact_gap_rejects_narrow_actor_and_cleans_up(self):
        class AuthoredWorld(World):
            def get_waypoint(self, location, project_to_road=False):
                return NS(road_id=149237, lane_id=-1)

            def tick(self):
                pass

        world = AuthoredWorld(widths=(2.1, 2.0))
        with self.assertRaisesRegex(ValueError, '80-inch'):
            with construction.spawn_exact_gap_pair(world, 'vehicle.carlamotors.european_hgv',
                                                   'vehicle.carlamotors.carlacola', 'gap_at_500ft',
                                                   lambda x, y, heading: NS(x=x, y=y)):
                pass
        self.assertTrue(all(a.destroyed for a in world.actors))

    def test_exact_gap_rejects_unclassified_blueprint(self):
        world = World()
        with self.assertRaisesRegex(ValueError, 'classification'):
            with construction.spawn_exact_gap_pair(world, 'vehicle.lincoln.mkz_2020',
                                                   'vehicle.carlamotors.carlacola', 'gap_at_500ft',
                                                   lambda x, y, heading: NS(x=x, y=y)):
                pass
        self.assertEqual(world.actors, [])


if __name__ == "__main__":
    unittest.main()
