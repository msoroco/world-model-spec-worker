"""CPU fake-actor tests for original signal identity and state readback."""
import unittest

from signals import configure, resolve, sample


class Actor:
    type_id = 'traffic.traffic_light'

    def __init__(self, actor_id, opendrive_id, state):
        self.id, self.op_end, self.state = actor_id, opendrive_id, state

    def get_opendrive_id(self):
        return self.op_end

    def get_state(self):
        return self.state

    def set_state(self, state):
        self.state = state

    def freeze(self, value):
        self.frozen = value


class SignalsTest(unittest.TestCase):
    def test_configure_both_contrasts_and_readback(self):
        class Carla:
            class TrafficLightState:
                Green = 'Green'
                Red = 'Red'
        heads = resolve([Actor(11, '201', 'Red'), Actor(12, '202', 'Green')])
        for requested, expected in [('walk', 'walk'), ('dont_walk', 'dont_walk')]:
            observed = configure(heads, requested, Carla)
            self.assertEqual(observed['traffic']['state'], 'circular_green')
            self.assertEqual(observed['pedestrian']['state'], expected)
            self.assertTrue(all(actor.frozen for actor in heads.values()))
        with self.assertRaisesRegex(ValueError, 'Unknown requested'):
            configure(heads, 'unknown', Carla)
    def test_two_distinct_heads(self):
        heads = resolve([Actor(11, '201', 'Green'), Actor(12, '202', 'Red')])
        observed = sample(heads)
        self.assertEqual(observed['traffic']['state'], 'circular_green')
        self.assertEqual(observed['pedestrian']['state'], 'dont_walk')
        self.assertEqual(observed['pedestrian']['source'], 'native_readback')

    def test_missing_head_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Both distinct'):
            resolve([Actor(11, '201', 'Green')])

    def test_duplicate_head_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            resolve([Actor(11, '201', 'Green'), Actor(12, '201', 'Red'), Actor(13, '202', 'Red')])

    def test_unrecognized_state_rejected(self):
        heads = resolve([Actor(11, '201', 'Green'), Actor(12, '202', 'Yellow')])
        with self.assertRaisesRegex(ValueError, 'Unrecognized'):
            sample(heads)


if __name__ == '__main__':
    unittest.main()
