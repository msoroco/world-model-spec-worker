"""CPU geometry and fake Native actor checks for the passing attempt."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overtaking_site import validate_site
from overtaking_construction import spawn_overtaking_pair
from overtaking_controller import PassingPolicy


class Actor:
    def __init__(self, location, width):
        self.location = location
        self.bounding_box = NS(extent=NS(x=5, y=width/2))
        self.destroyed = False
        self.control = None

    def get_location(self):
        return self.location

    def get_transform(self):
        return NS(location=self.location, get_forward_vector=lambda: NS(x=1, y=0))

    def get_velocity(self):
        return NS(x=0, y=0)

    def set_transform(self, location):
        self.location = location

    def apply_control(self, control):
        self.control = control

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, road=149239, lane=-1, widths=(2.2, 2.2)):
        self.road, self.lane, self.widths = road, lane, widths
        self.actors = []
        self.ticks = 0

    def try_spawn_actor(self, blueprint, transform):
        actor = Actor(transform, self.widths[len(self.actors)])
        self.actors.append(actor)
        return actor

    def get_map(self):
        return self

    def get_waypoint(self, location, project_to_road=False):
        if project_to_road:
            raise AssertionError('Native lane readback must be unprojected')
        return NS(road_id=self.road, lane_id=self.lane)

    def tick(self):
        self.ticks += 1


def transform(x, y, heading):
    if heading:
        raise AssertionError('Expected forward direction')
    return NS(x=x, y=y)


class OvertakingTests(unittest.TestCase):
    def test_one_forward_and_one_opposing_lane(self):
        site = validate_site()
        self.assertEqual(site['same_direction_lane_count'], 1)
        self.assertEqual(site['lane_id'], -1)
        self.assertEqual(site['passing_lane_id'], 1)

    def test_initial_gap_and_cleanup(self):
        world = World()
        with spawn_overtaking_pair(world, 'vehicle.carlamotors.european_hgv',
                                   'vehicle.carlamotors.carlacola', transform) as pair:
            self.assertAlmostEqual(pair['initial_body_gap_m'], 150)
            self.assertEqual(pair['site']['road_id'], 149239)
            self.assertEqual(world.ticks, 1)
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_rejects_narrow_truck_and_wrong_road(self):
        for world, message in ((World(widths=(2.0, 2.2)), '80 inches'),
                               (World(road=149237), 'forward lane')):
            with self.assertRaisesRegex(ValueError, message):
                with spawn_overtaking_pair(world, 'vehicle.carlamotors.european_hgv',
                                           'vehicle.carlamotors.carlacola', transform):
                    pass
            self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_policy_changes_lanes_only_during_pass(self):
        ego, lead = Actor(transform(100, -1.9, 0), 2.2), Actor(transform(260, -1.9, 0), 2.2)
        policy = PassingPolicy()
        self.assertEqual(policy.update(ego, lead), 'approach')
        ego.location = transform(140, -1.9, 0)
        self.assertEqual(policy.update(ego, lead), 'passing')
        controls = policy.apply(ego, lead, lambda **kw: kw)
        self.assertLess(controls['ego']['lateral_error_m'], 0)
        self.assertGreater(ego.control['steer'], 0)
        ego.location = transform(300, 1.9, 0)
        self.assertEqual(policy.update(ego, lead), 'return')
        controls = policy.apply(ego, lead, lambda **kw: kw)
        self.assertGreater(controls['ego']['lateral_error_m'], 0)
        self.assertLess(ego.control['steer'], 0)


if __name__ == '__main__':
    unittest.main()
