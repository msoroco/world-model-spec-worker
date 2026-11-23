import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crest_route import bind_opposing_routes, survey_lane, survey_map_pair
import hashlib


MAP_HASH = 'a' * 64


class Waypoint:
    lane_type = 'LaneType.Driving'

    def __init__(self, x, y, z, road_id, lane_id, s):
        self.transform = SimpleNamespace(location=SimpleNamespace(x=x, y=y, z=z))
        self.road_id, self.lane_id, self.s = road_id, lane_id, s
        self.following = []

    def next(self, distance):
        return self.following


def route(lane_id, *, reverse=False, offset=0, flat=False):
    height = [0, 1, 3, 5, 7, 5, 3, 1, 0] if not flat else [0] * 9
    points = [Waypoint(i * 5 if not reverse else 40 - i * 5, offset,
                       height[i], 11, lane_id, i * 5) for i in range(9)]
    for left, right in zip(points, points[1:]):
        left.following = [right]
    return points


class CrestRouteTests(unittest.TestCase):
    def test_candidate_opendrive_has_real_two_way_grade_crest(self):
        document = ET.parse(Path(__file__).resolve().parents[1] / 'candidate-crest-road.xodr')
        road = document.find('.//road')
        self.assertEqual(road.get('length'), '500')
        lanes = {int(lane.get('id')): lane.get('type') for lane in road.findall('.//lane')}
        self.assertEqual(lanes[1], 'driving')
        self.assertEqual(lanes[-1], 'driving')
        elevation = road.find('elevationProfile/elevation')
        a, b, c, d = [float(elevation.get(key)) for key in ('a', 'b', 'c', 'd')]
        grade = lambda station: a + b * station + c * station ** 2 + d * station ** 3
        self.assertGreater(grade(250), grade(100))
        self.assertGreater(grade(250), grade(400))
        self.assertAlmostEqual(grade(250), 4.0)
        self.assertAlmostEqual(b + 2 * c * 250, 0.0)

    def test_actual_opendrive_source_must_match_declared_hash(self):
        native_map = SimpleNamespace(name='NativeHill', to_opendrive=lambda: '<OpenDRIVE>hill</OpenDRIVE>')
        actual = hashlib.sha256(native_map.to_opendrive().encode()).hexdigest()
        packet = survey_map_pair(native_map, route(1)[0], route(-1, reverse=True, offset=4)[0],
                                 expected_map_sha256=actual)
        self.assertEqual(packet['binding']['map_sha256'], actual)
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            survey_map_pair(native_map, route(1)[0], route(-1, reverse=True, offset=4)[0],
                            expected_map_sha256=MAP_HASH)

    def test_two_opposing_original_routes_are_bound(self):
        forward = survey_lane(route(1)[0], map_name='NativeHill', map_sha256=MAP_HASH)
        opposing = survey_lane(route(-1, reverse=True, offset=4)[0],
                               map_name='NativeHill', map_sha256=MAP_HASH)
        binding = bind_opposing_routes(forward, opposing)
        self.assertEqual(binding['forward_lane_id'], 1)
        self.assertEqual(binding['opposing_lane_id'], -1)
        self.assertEqual(binding['crest_separation_m'], 4)
        self.assertEqual(forward['crest_station_m'], opposing['crest_station_m'])
        self.assertTrue(all(MAP_HASH in point['source_ref'] for point in forward['waypoints']))

    def test_rejects_flat_grade_and_route_fork(self):
        with self.assertRaisesRegex(ValueError, 'crest'):
            survey_lane(route(1, flat=True)[0], map_name='NativeHill', map_sha256=MAP_HASH)
        points = route(1)
        points[2].following.append(Waypoint(15, 4, 5, 11, 1, 15))
        with self.assertRaisesRegex(ValueError, 'one connected'):
            survey_lane(points[0], map_name='NativeHill', map_sha256=MAP_HASH)

    def test_rejects_lane_change_and_disconnected_route(self):
        points = route(1)
        points[3].lane_id = 2
        with self.assertRaisesRegex(ValueError, 'road or lane'):
            survey_lane(points[0], map_name='NativeHill', map_sha256=MAP_HASH)
        points = route(1)
        points[4].transform.location.x = 200
        with self.assertRaisesRegex(ValueError, 'gap'):
            survey_lane(points[0], map_name='NativeHill', map_sha256=MAP_HASH)

    def test_rejects_same_direction_and_distinct_crest(self):
        forward = survey_lane(route(1)[0], map_name='NativeHill', map_sha256=MAP_HASH)
        same = survey_lane(route(2, offset=4)[0], map_name='NativeHill', map_sha256=MAP_HASH)
        with self.assertRaisesRegex(ValueError, 'opposite driving lanes'):
            bind_opposing_routes(forward, same)
        far = survey_lane(route(-1, reverse=True, offset=30)[0],
                          map_name='NativeHill', map_sha256=MAP_HASH)
        with self.assertRaisesRegex(ValueError, 'not colocated'):
            bind_opposing_routes(forward, far)


if __name__ == '__main__':
    unittest.main()
