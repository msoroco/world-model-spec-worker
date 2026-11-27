import unittest
from controller import CASE_MODES, FRAMES, apply_light_request, light_request


class State:
    LowBeam = 1
    HighBeam = 2
    Position = 4

    def __call__(self, value):
        return value


class Carla:
    VehicleLightState = State()


class Vehicle:
    def __init__(self):
        self.states = []

    def set_light_state(self, state):
        self.states.append(state)


class LampRequestTest(unittest.TestCase):
    def test_distinct_statutory_alternatives(self):
        vehicle = Vehicle()
        for suffix, expected in [('witness_1', 1), ('witness_2', 2),
                                 ('exception_1_1', 2), ('exception_1_2', 6)]:
            request = apply_light_request(vehicle, Carla, suffix, 200)
            self.assertIsNone(request['optical_state_observed'])
            self.assertIsNone(request['lawfully_parked_observed'])
            self.assertEqual(vehicle.states[-1], expected)
        self.assertEqual(len(CASE_MODES), 4)

    def test_full_interval_and_unknown_rejection(self):
        self.assertEqual(light_request('witness_1', 0)['mode_request'], 'depressed_low_beam')
        self.assertEqual(light_request('witness_1', FRAMES-1)['mode_request'], 'depressed_low_beam')
        for suffix, frame in [('unknown', 0), ('witness_1', -1), ('witness_1', FRAMES)]:
            with self.assertRaises(ValueError):
                light_request(suffix, frame)


if __name__ == '__main__':
    unittest.main()
