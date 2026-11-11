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


if __name__ == '__main__':
    unittest.main()
