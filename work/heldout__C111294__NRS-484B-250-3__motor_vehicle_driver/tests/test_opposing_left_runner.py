import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ending_road_camera import CAMERAS
from opposing_left_runner import check_config


class OpposingLeftRunnerTest(unittest.TestCase):
    def config(self):
        return {'selected_case_id': 'heldout__C293604__NRS-484B-250-3__motor_vehicle_driver__opposing_left_turn',
                'law_id': 'NRS-484B-250-3', 'cell_id': 'C293604',
                'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'frames': 160,
                'cameras': [{'name': name, 'width': size[0], 'height': size[1]}
                            for name, (_, _, size, _) in CAMERAS.items()]}

    def test_exact_binding_and_four_source_profile(self):
        config = self.config()
        check_config(config)
        self.assertNotIn('carla', sys.modules)
        for key, value in [('cell_id', 'C111294'), ('rate_hz', 10), ('frames', 60),
                           ('selected_case_id', 'unbound_left_turn')]:
            changed = dict(config, **{key: value})
            with self.assertRaises(ValueError):
                check_config(changed)
        changed = dict(config, cameras=config['cameras'][:-1])
        with self.assertRaises(ValueError):
            check_config(changed)

    def test_local_travel_subject_binding(self):
        config = self.config()
        config['cell_id'] = 'C111294'
        config['selected_case_id'] = ('heldout__C111294__NRS-484B-250-3__motor_vehicle_driver'
                                      '__opposing_left_travel_subject')
        check_config(config)
        self.assertNotIn('carla', sys.modules)
        with self.assertRaisesRegex(ValueError, 'case and cell binding'):
            check_config(dict(config, selected_case_id=self.config()['selected_case_id']))

    def test_bounded_physical_fallback_knobs(self):
        config = self.config()
        for knob, value in [('route_search_cap', 600),
                            ('turning_released_speed_mps', 3.2),
                            ('opposite_speed_mps', 4.0)]:
            check_config(dict(config, **{knob: value}))
        for knob, value in [('route_search_cap', 601),
                            ('turning_released_speed_mps', 0),
                            ('opposite_speed_mps', 10)]:
            with self.assertRaises(ValueError):
                check_config(dict(config, **{knob: value}))


if __name__ == '__main__':
    unittest.main()
