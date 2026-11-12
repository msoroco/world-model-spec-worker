from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from center_turn_cameras import CAMERAS
from runner import PREFIX, check_config


class RunnerConfigTests(unittest.TestCase):
    def fixture(self):
        case = PREFIX + 'left_center_east'
        return {'law_id': 'LVMC-11-12-100-C', 'cell_id': 'C374648',
                'actor': 'motor_vehicle_driver', 'selected_case_id': case,
                'case': {'case_id': case, 'recording_description': {'subject': 'ego'}},
                'rate_hz': 20, 'frames': 80, 'duration_s': 4,
                'cameras': [{'name': name, 'width': profile[2][0],
                             'height': profile[2][1], 'fov_deg': profile[3]}
                            for name, profile in CAMERAS.items()]}

    def test_exact_first_case_and_four_source_profiles(self):
        config = self.fixture()
        self.assertEqual(check_config(config), config['selected_case_id'])
        config['cameras'][2]['width'] = 640
        with self.assertRaisesRegex(ValueError, 'profile differs'):
            check_config(config)

    def test_wrong_identity_and_case_rejected(self):
        config = self.fixture()
        config['case']['case_id'] = PREFIX + 'left_outer_east'
        with self.assertRaisesRegex(ValueError, 'exact first selected'):
            check_config(config)
        config = self.fixture()
        config['law_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'identity'):
            check_config(config)


if __name__ == '__main__':
    unittest.main()
