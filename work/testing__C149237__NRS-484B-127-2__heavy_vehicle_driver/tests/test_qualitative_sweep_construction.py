import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

source = Path(__file__).resolve().parents[1] / 'qualitative_sweep_construction.py'
spec = importlib.util.spec_from_file_location('qualitative_sweep_construction', source)
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)


class Actor:
    def __init__(self, location, width=2.1):
        self.location = location
        self.bounding_box = NS(extent=NS(x=4.0, y=width / 2))
        self.destroyed = False

    def get_location(self):
        return self.location

    def get_transform(self):
        return NS(get_forward_vector=lambda: NS(x=1, y=0))

    def set_transform(self, transform):
        self.location = transform

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, widths=(2.1, 2.1), drift=0.0, wrong_lane=False):
        self.widths, self.drift, self.wrong_lane = widths, drift, wrong_lane
        self.actors = []

    def try_spawn_actor(self, blueprint, transform):
        actor = Actor(transform, self.widths[len(self.actors)])
        self.actors.append(actor)
        return actor

    def tick(self):
        if self.drift:
            self.actors[1].location.x += self.drift

    def get_map(self):
        return self

    def get_waypoint(self, location, project_to_road=False):
        return NS(road_id=149237, lane_id=-2 if self.wrong_lane else -1)


class SweepConstructionTests(unittest.TestCase):
    def test_all_selected_setpoints_have_source_bound_motion_budget(self):
        for gap in sweep.GAP_POINTS_M:
            plan = sweep.placement(gap, 4.0, 4.0)
            self.assertEqual(plan['target_body_gap_m'], gap)
            self.assertLessEqual(plan['projected_end_front_m'], 1150)
            self.assertEqual(len(plan['road_sha256']), 64)
            world = World()
            with sweep.spawn_sweep_pair(world, NS(id='vehicle.carlamotors.european_hgv'),
                                        NS(id='vehicle.carlamotors.carlacola'), gap,
                                        lambda x, y, yaw: NS(x=x, y=y)) as pair:
                self.assertAlmostEqual(pair['initial_body_gap_m'], gap)
                self.assertEqual(pair['placement']['road_sha256'], plan['road_sha256'])
            self.assertTrue(all(a.destroyed for a in world.actors))

    def test_rejects_unselected_or_infeasible_points(self):
        with self.assertRaisesRegex(ValueError, 'Unselected'):
            sweep.placement(500.0, 4.0, 4.0)
        with self.assertRaisesRegex(ValueError, 'motion envelope'):
            sweep.placement(200.0, 4.0, 250.0)

    def test_readback_and_lane_fail_closed_with_cleanup(self):
        bp1 = NS(id='vehicle.carlamotors.european_hgv')
        bp2 = NS(id='vehicle.carlamotors.carlacola')
        for world, expected in ((World(drift=1.0), 'readback'),
                                (World(wrong_lane=True), 'lane'),
                                (World(widths=(2.0, 2.1)), '80-inch')):
            with self.assertRaisesRegex(ValueError, expected):
                with sweep.spawn_sweep_pair(world, bp1, bp2, 152.4,
                                            lambda x, y, yaw: NS(x=x, y=y)):
                    pass
            self.assertTrue(all(a.destroyed for a in world.actors))


if __name__ == '__main__':
    unittest.main()
