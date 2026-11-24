"""CPU fake-actor tests for original signal identity and state readback."""
import unittest

from signals import resolve, sample


class Actor:
    type_id = 'traffic.traffic_light'

    def __init__(self, actor_id, opendrive_id, state):
        self.id, self.op_end, self.state = actor_id, opendrive_id, state

    def get_opendrive_id(self):
        return self.op_end

    def get_state(self):
        return self.state


class SignalsTest(unittest.TestCase):
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
