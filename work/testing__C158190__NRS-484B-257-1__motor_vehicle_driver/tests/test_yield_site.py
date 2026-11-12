import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

source = Path(__file__).resolve().parents[1] / 'yield_site.py'
spec = importlib.util.spec_from_file_location('c158190_yield_site', source)
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class Actors:
    def __init__(self, actors):
        self.actors = actors

    def filter(self, pattern):
        assert pattern == 'traffic.yield*'
        return self.actors


class Map:
    name = 'OpenDriveMap'

    def __init__(self, override=None):
        self.override = override or {}

    def get_waypoint(self, point, project_to_road=False):
        assert project_to_road is False
        key = (point.x, point.y)
        inventory = {(-20, 1.8): (158190, -1, False),
                     (0, 1.8): (158192, -1, True),
                     (1.8, 20): (158194, -1, False),
                     (1.8, 0): (158195, -1, True),
                     (-1.8, -20): (158196, 1, False)}
        road_id, lane_id, junction = self.override.get(key, inventory[key])
        return NS(road_id=road_id, lane_id=lane_id, is_junction=junction)


def world(override=None, sign_present=True):
    sign = NS(id=301, trigger_volume=NS(contains=lambda point, transform:
                                       sign_present and point.x == -20 and point.y == 1.8),
              get_transform=lambda: object())
    return NS(get_map=lambda: Map(override), get_actors=lambda: Actors([sign]))


class SiteTests(unittest.TestCase):
    def test_authored_junction_and_native_governance(self):
        self.assertEqual(site.opendrive_to_carla(-20, -1.8), (-20., 1.8))
        self.assertEqual(site.opendrive_to_carla(1.8, -20), (1.8, 20.))
        authored = site.validate_authored_site()
        self.assertEqual(authored['approach_lane_id'], -1)
        self.assertEqual(authored['through_road_ids'], [158194, 158195, 158196])
        self.assertFalse(authored['native_marking_absence_claimed'])
        observed = site.validate_native_site(world(), location_factory=lambda **values: NS(**values))
        self.assertEqual(observed['native_yield_sign_id'], 301)
        self.assertFalse(observed['properly_erected_sign_face_claimed'])

    def test_rejects_wrong_sign_lane_and_through_junction(self):
        original = site.ROAD.read_text()
        with tempfile.TemporaryDirectory() as temporary:
            bad = Path(temporary) / 'bad.xodr'
            bad.write_text(original.replace('fromLane="-1" toLane="-1"',
                                            'fromLane="1" toLane="1"'))
            with self.assertRaisesRegex(ValueError, 'Yield sign does not govern'):
                site.validate_authored_site(bad)
        with self.assertRaisesRegex(ValueError, 'Native road/lane/junction'):
            site.validate_native_site(world({(1.8, 0): (158195, 1, True)}),
                                      location_factory=lambda **values: NS(**values))
        with self.assertRaisesRegex(ValueError, 'Expected one Native yield trigger'):
            site.validate_native_site(world(sign_present=False),
                                      location_factory=lambda **values: NS(**values))


if __name__ == '__main__':
    unittest.main()
