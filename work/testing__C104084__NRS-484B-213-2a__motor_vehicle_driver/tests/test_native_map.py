import importlib.util
import sys
from pathlib import Path
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('native_map', ROOT / 'native_map.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class Waypoint:
    def __init__(self, index, lane_id, z, yaw, route):
        self.index, self.route = index, route
        self.road_id, self.lane_id = 1, lane_id
        self.transform = SimpleNamespace(
            location=SimpleNamespace(x=index * 10, y=0 if lane_id == 1 else 3, z=z),
            rotation=SimpleNamespace(yaw=yaw))
    def next(self, interval):
        return self.route[self.index + 1:self.index + 2]
    def get_left_lane(self):
        return self.route.opposite[self.index]


class Route(list):
    pass


def world(crest=True, opposite=True):
    route, other = Route(), Route()
    for index in range(11):
        z = 8 if crest and index == 5 else 0
        route.append(Waypoint(index, 1, z, 0, route))
        other.append(Waypoint(index, -1, z, 180 if opposite else 0, other))
    route.opposite, other.opposite = other, route
    mapping = SimpleNamespace(name='original-test-map', get_waypoint=lambda _: route[0])
    return SimpleNamespace(get_map=lambda: mapping)


class NativeMapTests(unittest.TestCase):
    def test_source_binds_real_opposing_crest(self):
        result = native.bind_two_way_crest(world(), object())
        self.assertTrue(result['grade_proxy']['sampled_grade_blocks_proxy_ray'])
        self.assertEqual(result['ego_lane'][5]['road_z_m'], 8)
        self.assertEqual(result['opposing_lane'][5]['travel_direction'], 'decreasing_s')

    def test_rejects_flat_map_and_same_direction_lane(self):
        with self.assertRaisesRegex(ValueError, 'does not obstruct'):
            native.bind_two_way_crest(world(crest=False), object())
        with self.assertRaisesRegex(ValueError, 'not opposite'):
            native.bind_two_way_crest(world(opposite=False), object())

    def test_rejects_truncated_approach(self):
        bad = world()
        route = bad.get_map().get_waypoint(None).route
        del route[8:]
        with self.assertRaisesRegex(ValueError, 'terminates'):
            native.bind_two_way_crest(bad, object())


if __name__ == '__main__':
    unittest.main()
