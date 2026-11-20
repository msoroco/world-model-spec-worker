import copy
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from statutory_variants import bind, validate


def survey(kind):
    control_type = ('walker.pedestrian.0001' if kind in
                    ('warning_person', 'employee_exception') else 'static.prop.trafficwarning')
    row = {'map_name': 'surveyed-map', 'road_id': 8,
           'repair_polygon_xy_m': [[-1, -1], [1, -1], [1, 1], [-1, 1]],
           'route_over_xy_m': [[-5, 0], [5, 0]],
           'route_avoid_xy_m': [[-5, 0], [-3, 2], [0, 3], [3, 2], [5, 0]],
           'frames': 600, 'ego_blueprint': 'vehicle.example',
           'weather_profile': 'surveyed-clear', 'anchor_z_m': 0.0,
           'control_kind': kind, 'control_actor_id': 12,
           'control_xy_m': [2, 0], 'control_type_id': control_type}
    if kind in ('warning_sign', 'highway_closed_sign'):
        row['sign_face_source'] = 'original overview and approach camera frames'
    if kind == 'employee_exception':
        row['employee_activity_source'] = 'independent paving-work source review'
        row['nonemployee_activity_source'] = 'independent nonemployee source review'
        row['governing_warning_control'] = {
            'actor_id': 13, 'type_id': 'static.prop.trafficwarning',
            'xy_m': [3, 0], 'source_reference': 'original warning-control pixels'}
    return row


class World:
    def __init__(self, row, *, actor_type=None, actor_x=2, road_id=8):
        self.row = row
        self.actor_type = actor_type or row['control_type_id']
        self.actor_x = actor_x
        self.road_id = road_id

    def get_map(self):
        def waypoint(location, **_):
            return types.SimpleNamespace(road_id=self.road_id, lane_id=1,
                                         lane_type='Driving')
        return types.SimpleNamespace(name='surveyed-map', get_waypoint=waypoint)

    def get_actors(self):
        actor = types.SimpleNamespace(id=12, type_id=self.actor_type,
            get_transform=lambda: types.SimpleNamespace(location=types.SimpleNamespace(
                x=self.actor_x, y=0, z=0)))
        warning = types.SimpleNamespace(id=13, type_id='static.prop.trafficwarning',
            get_transform=lambda: types.SimpleNamespace(location=types.SimpleNamespace(
                x=3, y=0, z=0)))
        return types.SimpleNamespace(find=lambda ident: {12: actor, 13: warning}.get(ident))


CARLA = types.SimpleNamespace(Location=lambda **kwargs: types.SimpleNamespace(**kwargs),
    LaneType=types.SimpleNamespace(Any='Any', Driving='Driving', Shoulder='Shoulder'))


class StatutoryVariantTest(unittest.TestCase):
    def test_each_route_has_exact_crossing_pair_and_no_verdict(self):
        for kind in ('barrier', 'warning_sign', 'highway_closed_sign',
                     'warning_person', 'employee_exception'):
            with self.subTest(kind=kind):
                row = survey(kind)
                plan = validate(row, 'surveyed-map')
                if kind == 'employee_exception':
                    self.assertEqual(set(plan['cases']), {'employee_crossing', 'nonemployee_crossing'})
                    self.assertEqual(plan['cases']['employee_crossing']['route_xy_m'],
                                     plan['cases']['nonemployee_crossing']['route_xy_m'])
                    self.assertNotEqual(plan['cases']['employee_crossing']['operator_activity_source'],
                                        plan['cases']['nonemployee_crossing']['operator_activity_source'])
                else:
                    self.assertTrue(plan['cases']['crossing']['requested_pavement_crossing'])
                    self.assertFalse(plan['cases']['avoidance']['requested_pavement_crossing'])
                receipt = bind(row, World(row), CARLA)
                self.assertEqual(receipt['control_type_id'], row['control_type_id'])
                self.assertFalse(receipt['control_content_verified'])
                self.assertFalse(receipt['employee_exception_verified'])
                if kind == 'employee_exception':
                    self.assertEqual(receipt['governing_warning_control']['actor_id'], 13)

    def test_rejects_unisolated_or_unmeasured_scene(self):
        row = survey('barrier')
        row['route_avoid_xy_m'] = [[-5, 0], [5, 0]]
        with self.assertRaisesRegex(ValueError, 'isolate'):
            validate(row, 'surveyed-map')
        row = survey('barrier')
        row['frames'] = 599
        with self.assertRaisesRegex(ValueError, '30 seconds'):
            validate(row, 'surveyed-map')
        row = survey('barrier')
        row['control_xy_m'] = [100, 100]
        with self.assertRaisesRegex(ValueError, 'not near'):
            validate(row, 'surveyed-map')

    def test_rejects_missing_content_and_exception_sources(self):
        sign = survey('warning_sign')
        del sign['sign_face_source']
        with self.assertRaisesRegex(ValueError, 'sign-face'):
            validate(sign, 'surveyed-map')
        employee = survey('employee_exception')
        del employee['employee_activity_source']
        with self.assertRaisesRegex(ValueError, 'activity source'):
            validate(employee, 'surveyed-map')
        employee = survey('employee_exception')
        del employee['governing_warning_control']
        with self.assertRaisesRegex(ValueError, 'distinct sourced governing'):
            validate(employee, 'surveyed-map')
        employee = survey('employee_exception')
        employee['governing_warning_control']['actor_id'] = 12
        with self.assertRaisesRegex(ValueError, 'distinct sourced governing'):
            validate(employee, 'surveyed-map')

    def test_rejects_live_actor_and_map_mismatch(self):
        row = survey('barrier')
        with self.assertRaisesRegex(ValueError, 'actor differs'):
            bind(row, World(row, actor_type='static.prop.other'), CARLA)
        with self.assertRaisesRegex(ValueError, 'position differs'):
            bind(row, World(row, actor_x=5), CARLA)
        with self.assertRaisesRegex(ValueError, 'road differs'):
            bind(row, World(row, road_id=9), CARLA)


if __name__ == '__main__':
    unittest.main()
