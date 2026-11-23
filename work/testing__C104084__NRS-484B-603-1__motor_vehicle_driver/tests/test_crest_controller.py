import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crest_controller import step, target_speed


class Vehicle:
    def __init__(self):
        self.commands = []

    def apply_control(self, command):
        self.commands.append(command)


class CrestControllerTests(unittest.TestCase):
    def test_early_late_steady_diverge_only_at_declared_station(self):
        self.assertEqual({name: target_speed(name, crest_s_m=100, ego_s_m=75)
                          for name in ('early_decrease', 'late_decrease', 'steady_approach')},
                         {'early_decrease': 10.0, 'late_decrease': 12.0,
                          'steady_approach': 12.0})

    def test_control_calls_and_brakes(self):
        vehicle = Vehicle()
        result = step(vehicle, dict, 'early_decrease', crest_s_m=100,
                      ego_s_m=75, measured_speed_mps=12)
        self.assertEqual(len(vehicle.commands), 1)
        self.assertGreater(result['brake'], 0)
        self.assertEqual(result['throttle'], 0)

    def test_rejects_postcrest_and_missing_speed(self):
        with self.assertRaisesRegex(ValueError, 'passed'):
            target_speed('early_decrease', crest_s_m=100, ego_s_m=101)
        with self.assertRaisesRegex(ValueError, 'measured speed'):
            step(Vehicle(), dict, 'early_decrease', crest_s_m=100,
                 ego_s_m=75, measured_speed_mps=float('nan'))


if __name__ == '__main__':
    unittest.main()
