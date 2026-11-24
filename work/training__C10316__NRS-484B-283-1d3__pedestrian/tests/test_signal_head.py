"""CPU test for source identity, state readback and fail-closed behavior."""

import unittest
from types import SimpleNamespace

from geometry import check
from signal_head import command_and_sample, resolve, sample


class FakeHead:
    type_id = 'traffic.traffic_light'
    id = 77

    def __init__(self, od_id='203'):
        self.od_id = od_id
        self.state = 'Off'
        self.frozen = False

    def get_opendrive_id(self):
        return self.od_id

    def set_state(self, state):
        self.state = state

    def get_state(self):
        return self.state

    def freeze(self, frozen):
        self.frozen = frozen


class SignalHeadTest(unittest.TestCase):
    def test_physical_head_map_and_readback(self):
        check()
        head = FakeHead()
        self.assertIs(resolve([head, FakeHead('999')]), head)
        states = SimpleNamespace(Green='Green', Red='Red', Off='Off')
        carla = SimpleNamespace(TrafficLightState=states)
        for indication, illuminated, expected in (
            ('walk', True, 'Green'),
            ('dont_walk_flashing', True, 'Red'),
            ('dont_walk_flashing', False, 'Off'),
            ('dont_walk_steady', True, 'Red'),
        ):
            receipt = command_and_sample(head, carla, indication, illuminated)
            self.assertEqual(receipt['native_state'], expected)
            self.assertEqual(receipt['opendrive_id'], '203')
            self.assertEqual(receipt['source'], 'native_actor_readback')
            self.assertTrue(head.frozen)
        head.state = 'Green'
        with self.assertRaisesRegex(ValueError, 'state differs'):
            sample(head, 'dont_walk_steady', True)

    def test_missing_or_ambiguous_source_fails(self):
        for actors in ([], [FakeHead('999')], [FakeHead(), FakeHead()]):
            with self.assertRaisesRegex(ValueError, 'Exactly one'):
                resolve(actors)


if __name__ == '__main__':
    unittest.main()
