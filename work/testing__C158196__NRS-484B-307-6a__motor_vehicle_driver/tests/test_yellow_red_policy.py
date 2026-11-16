import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

source = Path(__file__).resolve().parents[1] / 'yellow_red_policy.py'
spec = importlib.util.spec_from_file_location('yellow_red_policy', source)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class Signal:
    def __init__(self):
        self.state = None
        self.frozen = False

    def set_state(self, state):
        self.state = state

    def freeze(self, value):
        self.frozen = value


class Actor:
    def apply_control(self, control):
        self.control = control


class PolicyTests(unittest.TestCase):
    def test_exact_yellow_to_red_schedule(self):
        self.assertEqual([policy.signal_state(i) for i in (99, 100, 159, 160)],
                         ['Green', 'Yellow', 'Yellow', 'Red'])
        for i in (-1, 900):
            with self.assertRaises(ValueError):
                policy.signal_state(i)

    def test_all_selected_cases_issue_native_signal_and_vehicle_commands(self):
        carla = NS(TrafficLightState=NS(Green='G', Yellow='Y', Red='R'),
                   VehicleControl=lambda **k: NS(**k))
        for case, target in policy.CASES.items():
            signal, actor = Signal(), Actor()
            command = policy.apply_step(signal, actor, carla, case, 160, 8.0, 4.0)
            self.assertEqual(signal.state, 'R')
            self.assertTrue(signal.frozen)
            self.assertEqual(command['target_entry_frame'], target)
            self.assertEqual(command['observed_entry'], 'unverified')
            self.assertTrue(0 <= actor.control.throttle <= 0.65)
            self.assertTrue(0 <= actor.control.brake <= 0.9)
        stopped = policy.approach_control('stops_on_yellow', 160, 8.0, 4.0)
        self.assertEqual(stopped['target_speed_mps'], 0)
        self.assertGreater(stopped['brake'], 0)

    def test_rejects_missing_native_motion(self):
        for distance, speed in ((float('nan'), 1), (1, float('inf')), (1, -1)):
            with self.assertRaises(ValueError):
                policy.approach_control('entry_at_red', 120, distance, speed)


if __name__ == '__main__':
    unittest.main()
