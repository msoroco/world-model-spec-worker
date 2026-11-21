"""Controlled newly laid route and source requirement tests."""
import copy
import unittest
from types import SimpleNamespace

from newly_laid_plan import ROUTES, bind, validate


def survey():
    return {
        'cell_id': 'C183370', 'map_name': 'TownSource', 'road_id': 12,
        'laid_polygon_xy_m': [[-1, -1], [1, -1], [1, 1], [-1, 1]],
        'route_over_xy_m': [[-3, 0], [3, 0]],
        'route_avoid_xy_m': [[-3, 0], [-3, 3], [3, 3], [3, 0]],
        'frames': 600, 'anchor_z_m': 0.0,
        'ego_blueprint': 'vehicle.mock', 'weather_profile': 'fixed_daylight',
        'warning_person_actor_id': 34,
        'warning_person_type_id': 'walker.pedestrian.0001',
        'warning_person_xy_m': [0, 2],
        'surface_condition_source': 'original-paving-work-log-and-camera-review',
        'warning_act_source': 'original-four-camera-warning-act-review',
        'operator_activity_source': 'independent-original-operator-review',
    }


class NewlyLaidPlanTests(unittest.TestCase):
    def test_pair_is_same_cell_and_30_seconds(self):
        plan = validate(survey(), 'TownSource')
        self.assertEqual(tuple(plan['cases']), ROUTES)
        self.assertEqual(plan['capture_rate_hz'], 20)
        self.assertEqual(plan['frames'], 600)
        self.assertTrue(plan['cases'][ROUTES[0]]['requested_pavement_crossing'])
        self.assertFalse(plan['cases'][ROUTES[1]]['requested_pavement_crossing'])
        self.assertFalse(plan['newly_laid_status_verified'])

    def test_source_and_duration_are_required(self):
        for key in ('surface_condition_source', 'warning_act_source',
                    'operator_activity_source'):
            row = survey()
            row[key] = ''
            with self.assertRaisesRegex(ValueError, 'source-bound'):
                validate(row, 'TownSource')
        row = survey()
        row['frames'] = 599
        with self.assertRaisesRegex(ValueError, '30-second'):
            validate(row, 'TownSource')

    def test_route_isolation_and_common_endpoints(self):
        row = survey()
        row['route_avoid_xy_m'] = copy.deepcopy(row['route_over_xy_m'])
        with self.assertRaisesRegex(ValueError, 'isolate'):
            validate(row, 'TownSource')
        row = survey()
        row['route_avoid_xy_m'][-1] = [4, 0]
        with self.assertRaisesRegex(ValueError, 'common surveyed endpoints'):
            validate(row, 'TownSource')

    def test_live_binding_checks_actor_and_road(self):
        row = survey()
        person = SimpleNamespace(id=34, type_id=row['warning_person_type_id'],
                                 get_transform=lambda: SimpleNamespace(
                                     location=SimpleNamespace(x=0, y=2, z=0)))
        waypoint = SimpleNamespace(road_id=12, lane_id=1, lane_type='Driving')
        mapping = SimpleNamespace(name='TownSource',
                                  get_waypoint=lambda *args, **kwargs: waypoint)
        world = SimpleNamespace(get_map=lambda: mapping,
                                get_actors=lambda: SimpleNamespace(find=lambda _: person))
        carla = SimpleNamespace(Location=lambda **kwargs: SimpleNamespace(**kwargs),
                                LaneType=SimpleNamespace(Any='Any', Driving='Driving',
                                                          Shoulder='Shoulder'))
        result = bind(row, world, carla)
        self.assertEqual(result['warning_person_actor_id'], 34)
        self.assertFalse(result['newly_laid_status_verified'])
        wrong = SimpleNamespace(road_id=99, lane_id=1, lane_type='Driving')
        mapping.get_waypoint = lambda *args, **kwargs: wrong
        with self.assertRaisesRegex(ValueError, 'surface road'):
            bind(row, world, carla)


if __name__ == '__main__':
    unittest.main()
