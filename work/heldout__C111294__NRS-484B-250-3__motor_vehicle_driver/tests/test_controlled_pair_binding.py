import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controlled_pair_binding import bind_pair, require_same_pair, require_expected_binding
from native_pair_preflight import select_and_bind


class Point:
    def __init__(self, road, lane, x, y, junction=False):
        self.road_id, self.lane_id, self.is_junction = road, lane, junction
        self.transform = NS(location=NS(x=x, y=y),
                            get_forward_vector=lambda: NS(x=1, y=0))
        self.successors = []
        self.landmarks = []

    def next(self, distance):
        return self.successors

    def get_landmarks(self, distance, stop_at_junction=True):
        return self.landmarks

    def get_junction(self):
        return NS(id=42) if self.is_junction else None


def pair():
    return {'map_name': 'NativeMap', 'junction_id': 42,
            'ending': [Point(1, -1, -8, 0), Point(9, -1, 0, 0, True),
                       Point(3, -1, 8, 0)],
            'continuing': [Point(7, -1, -8, 4), Point(8, -1, 0, 4, True),
                           Point(7, -1, 8, 4)],
            'other': [Point(2, -1, 0, -8), Point(6, -1, 0, 0, True),
                      Point(2, -1, 0, 8)]}


class ControlledPairBindingTests(unittest.TestCase):
    def test_recreated_native_waypoints_preserve_pair_binding(self):
        first, second = pair(), pair()
        self.assertEqual(require_same_pair(first, second)['route_pair_sha256'],
                         bind_pair(first)['route_pair_sha256'])
        self.assertFalse(bind_pair(first)['legal_highway_classification_claimed'])

    def test_changed_fixed_through_lane_rejected(self):
        first, second = pair(), pair()
        second['other'][1].lane_id = -2
        with self.assertRaisesRegex(ValueError, 'other'):
            require_same_pair(first, second)
        second = pair()
        second['other'][1].transform.location.x += 0.00001
        with self.assertRaisesRegex(ValueError, 'other'):
            require_same_pair(first, second)

    def test_changed_subject_exit_or_junction_rejected(self):
        first, second = pair(), pair()
        second['continuing'][-1].road_id = 10
        with self.assertRaisesRegex(ValueError, 'continuity'):
            require_same_pair(first, second)
        second = pair()
        second['junction_id'] = 43
        with self.assertRaisesRegex(ValueError, 'junction'):
            require_same_pair(first, second)

    def test_nonfinite_and_missing_route_rejected(self):
        selected = pair()
        selected['ending'][0].transform.location.x = float('nan')
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            bind_pair(selected)
        selected = pair()
        del selected['other']
        with self.assertRaises(KeyError):
            bind_pair(selected)

    def test_expected_binding_rejects_stale_hash_and_changed_route(self):
        expected = bind_pair(pair())
        self.assertEqual(require_expected_binding(pair(), expected), expected)
        expected['routes']['other'][1]['lane_id'] = -2
        with self.assertRaisesRegex(ValueError, 'stale'):
            require_expected_binding(pair(), expected)
        expected = bind_pair(pair())
        changed = pair()
        changed['other'][1].lane_id = -2
        with self.assertRaisesRegex(ValueError, 'differs'):
            require_expected_binding(changed, expected)

    def test_preflight_selects_one_uncontrolled_pair(self):
        from test_categorical_highway_points import native_map
        world, ending, through = native_map(subject_continues=False)
        continuing = [Point(7, -1, -8, 4), Point(8, -1, 0, 4, True),
                      Point(7, -1, 8, 4)]
        continuing[0].successors = [continuing[1]]
        continuing[1].successors = [continuing[2]]
        starts = {id(p.transform.location): p
                  for p in (ending[0], through[0], continuing[0])}
        world.get_spawn_points = lambda: [NS(location=p.transform.location)
                                          for p in (ending[0], through[0], continuing[0])]
        world.get_waypoint = lambda location: starts[id(location)]
        world.to_opendrive = lambda: '<OpenDRIVE source="fixed" />'
        binding = select_and_bind(world, [])
        self.assertEqual(binding['routes']['other'][0]['road_id'], 2)
        self.assertEqual(select_and_bind(world, [], expected=binding), binding)
        world.to_opendrive = lambda: '<OpenDRIVE source="changed" />'
        with self.assertRaisesRegex(ValueError, 'differs'):
            select_and_bind(world, [], expected=binding)
        with self.assertRaisesRegex(ValueError, 'positive'):
            select_and_bind(world, [], max_spawns=0)


if __name__ == '__main__':
    unittest.main()
