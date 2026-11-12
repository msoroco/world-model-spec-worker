import hashlib
import unittest
from types import SimpleNamespace

from native_alley_survey import validate_placement, verify
from alley_route import select_alley_route


class Map:
    name = 'TestMap'

    def to_opendrive(self):
        return '<OpenDRIVE />'

    def get_waypoint_xodr(self, road_id, lane_id, s):
        return SimpleNamespace(road_id=road_id, lane_id=lane_id, s=s)


class SurveyTests(unittest.TestCase):
    def document(self):
        return {'format': 'worker-native-alley-survey-v1',
                'map_name': 'TestMap',
                'opendrive_sha256': hashlib.sha256(b'<OpenDRIVE />').hexdigest(),
                'reviewer': 'test reviewer', 'evidence_reference': 'test asset',
                'verified_alley': True,
                'polygon_xy': [[0, -3], [40, -3], [40, 3], [0, 3]],
                'alley_width_m': 6,
                'routes': {'east': {'road_id': 1, 'lane_id': 1, 'start_s': 2.0}}}

    def test_verified_source(self):
        scope, receipt = verify(Map(), self.document(), 'east', 'a' * 64)
        self.assertEqual(scope['route_reference']['start_s'], 2.0)
        self.assertEqual(receipt['operator_manifest_sha256'], 'a' * 64)

    def test_rejects_stale_map(self):
        document = self.document()
        document['opendrive_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'map/OpenDRIVE'):
            verify(Map(), document, 'east', 'a' * 64)

    def test_rejects_unreviewed_alley(self):
        document = self.document()
        document['verified_alley'] = False
        with self.assertRaisesRegex(ValueError, 'identity'):
            verify(Map(), document, 'east', 'a' * 64)

    def test_rejects_missing_route(self):
        with self.assertRaisesRegex(ValueError, 'selected route'):
            verify(Map(), self.document(), 'west', 'a' * 64)

    def test_selected_map_lane_must_fit_polygon(self):
        points = []
        for index in range(13):
            location = SimpleNamespace(x=2 + index * 2.5, y=0)
            transform = SimpleNamespace(location=location,
                get_forward_vector=lambda: SimpleNamespace(x=1, y=0))
            points.append(SimpleNamespace(road_id=1, lane_id=1,
                s=2 + index * 2.5, lane_width=3, is_junction=False,
                transform=transform))
        for index, point in enumerate(points):
            point.next = lambda step, index=index: [points[index + 1]] if index < 12 else []
        world_map = SimpleNamespace(get_waypoint_xodr=lambda *args: points[0])
        polygon = self.document()['polygon_xy']
        selected = select_alley_route(world_map, polygon, direction='east',
            polygon_source='alley-survey-original.json',
            route_reference={'road_id': 1, 'lane_id': 1, 'start_s': 2.0})
        self.assertEqual(selected, points)
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_alley_route(world_map, polygon, direction='east',
                polygon_source='alley-survey-original.json',
                route_reference={'road_id': 2, 'lane_id': 1, 'start_s': 2.0})

    def test_participants_must_fit_surveyed_polygon(self):
        scope = {'polygon_xy': self.document()['polygon_xy']}
        placement = SimpleNamespace(
            pedestrian=SimpleNamespace(x=10, y=1.8),
            property_center=SimpleNamespace(x=15, y=-1.9))
        validate_placement(scope, placement)
        placement.property_center.y = -2.5
        with self.assertRaisesRegex(ValueError, 'placement leaves'):
            validate_placement(scope, placement)


if __name__ == '__main__':
    unittest.main()
