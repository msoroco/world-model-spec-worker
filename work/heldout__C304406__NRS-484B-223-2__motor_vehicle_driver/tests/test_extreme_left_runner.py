import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from three_lane_runner_extreme_left import CASE, check_config, control_step
from three_lane_camera import CAMERAS


class ExtremeLeftRunnerTests(unittest.TestCase):
    def config(self):
        return {'selected_case_id': CASE, 'law_id': 'NRS-484B-223-2',
                'cell_id': 'C304406', 'actor': 'motor_vehicle_driver',
                'rate_hz': 20, 'frames': 160, 'duration_s': 8,
                'lane_role': 'extreme_left',
                'cameras': [{'name': name} for name in CAMERAS]}

    def test_exact_case_identity(self):
        config = self.config()
        check_config(config)
        config['lane_role'] = 'center'
        with self.assertRaisesRegex(ValueError, 'identity'):
            check_config(config)

    def test_counterflow_route_targets_forward_travel(self):
        command = control_step((0, 7), (1, 0), (0, 0), (10, 7))
        self.assertGreater(command['throttle'], 0)
        self.assertAlmostEqual(command['steer'], 0)
        reverse = control_step((0, 7), (-1, 0), (0, 0), (10, 7))
        self.assertNotEqual(reverse['steer'], command['steer'])


if __name__ == '__main__':
    unittest.main()
