import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'yield_controller.py'
spec = importlib.util.spec_from_file_location('yield_controller', path)
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)

PREFIX = 'testing__C158190__NRS-484B-257-1__motor_vehicle_driver__'


class YieldStageTests(unittest.TestCase):
    def test_slows_only_at_view_bracket_then_crosses(self):
        stage = module.Stage(PREFIX + 'yield_nearest_view_through_approaches')
        self.assertEqual(stage.target(30, within_intersection=False,
                                      through_vehicle_clear=False), 6)
        self.assertEqual(stage.target(15, within_intersection=False,
                                      through_vehicle_clear=False), 2)
        self.assertEqual(stage.target(5, within_intersection=False,
                                      through_vehicle_clear=True), 4)
        self.assertEqual(stage.target(0, within_intersection=True,
                                      through_vehicle_clear=False), 4)
        self.assertEqual(module.speed_control(2, 6), {'throttle': 0, 'brake': 1})

    def test_no_slow_contrast_keeps_same_speed(self):
        stage = module.Stage(PREFIX + 'yield_nearest_view_no_slow')
        self.assertEqual(stage.target(15, within_intersection=False,
                                      through_vehicle_clear=False), 6)
        self.assertEqual(module.speed_control(6, 2), {'throttle': 1, 'brake': 0})

    def test_rejects_unsourced_distance_and_unknown_case(self):
        with self.assertRaisesRegex(ValueError, 'Unknown exact'):
            module.Stage(PREFIX + 'stop_sign')
        stage = module.Stage(PREFIX + 'yield_nearest_view_clear')
        with self.assertRaisesRegex(ValueError, 'Native approach distance'):
            stage.target(float('nan'), within_intersection=False,
                         through_vehicle_clear=True)
        with self.assertRaisesRegex(ValueError, 'Native crossing state'):
            stage.target(5, within_intersection=None,
                         through_vehicle_clear=True)


if __name__ == '__main__':
    unittest.main()
