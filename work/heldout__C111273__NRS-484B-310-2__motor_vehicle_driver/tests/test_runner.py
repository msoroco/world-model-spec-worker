from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as NS

root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path: sys.path.insert(0, str(root))
import runner


def config(branch='east_cautious_approach'):
    return {'case_branch': branch,
            'selected_case_id': 'heldout__C111273__NRS-484B-310-2__motor_vehicle_driver__'+branch,
            'law_id': 'NRS-484B-310-2', 'cell_id': 'C111273',
            'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'frames': 160,
            'duration_s': 8,
            'cameras': [{'name': name} for name in runner.CAMERAS],
            'official_control_source': 'authored control source',
            'flash_period_s': .5,
            'target_speed_mps': runner.CASES[branch].approach_target_mps}


class TestRunner(unittest.TestCase):
    def test_exact_config_and_missing_sources(self):
        for branch in runner.CASES: self.assertTrue(runner.check_config(config(branch)))
        bad = config(); bad['official_control_source'] = ''
        with self.assertRaisesRegex(ValueError, 'official-control'):
            runner.check_config(bad)
        bad = config(); bad['cameras'] = bad['cameras'][:-1]
        with self.assertRaisesRegex(ValueError, 'four named'):
            runner.check_config(bad)
        bad = config(); bad['target_speed_mps'] = 99
        with self.assertRaisesRegex(ValueError, 'target speed'):
            runner.check_config(bad)

    def test_lane_controller_selects_forward_lane(self):
        target = NS(location=NS(x=6., y=0.), rotation=NS(yaw=0.))
        wrong = NS(location=NS(x=-6., y=0.), rotation=NS(yaw=180.))
        wp = NS(next=lambda step: [NS(transform=wrong), NS(transform=target)])
        actor = NS(is_alive=True, get_transform=lambda: NS(location=NS(x=0.,y=0.), rotation=NS(yaw=0.)),
                   get_velocity=lambda: NS(x=0., y=0.))
        controls = []
        actor.apply_control = controls.append
        world_map = NS(get_waypoint=lambda location: wp)
        carla = NS(VehicleControl=lambda **kwargs: kwargs)
        runner._lane_control(world_map, actor, 4., carla, 0.)
        self.assertGreater(controls[0]['throttle'], 0)
        self.assertEqual(controls[0]['steer'], 0)
        with self.assertRaisesRegex(ValueError, 'lookahead'):
            runner._lane_control(world_map, actor, 4., carla, 90.)


if __name__ == '__main__': unittest.main()
