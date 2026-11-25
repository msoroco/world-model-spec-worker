from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import encounter as module


class Adapter:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail
    def spawn_vehicle(self, waypoint, role):
        self.calls.append(('vehicle', role, waypoint))
        return None if self.fail == role else role
    def register_occupant(self, vehicle, descriptor):
        self.calls.append(('occupant', vehicle))
        return None if self.fail == 'occupant' else 'person-1'
    def spawn_property(self, anchor, offset_m):
        self.calls.append(('property', offset_m))
        return None if self.fail == 'property' else 'property-1'
    def set_route(self, actor, route, **kwargs):
        self.calls.append(('route', actor, route, kwargs))
    def destroy(self, actor):
        self.calls.append(('destroy', actor))


def site():
    return {'cell_id': 'C111304', 'layout': 'intersection', 'public_access_basis': 'highway',
            'public_access_source_sha256': 'a',
            'lanes': {k: {'source_sha256': 'b', 'lane_id': k, 'waypoints': [k+'0', k+'1']}
                      for k in ('northbound', 'southbound', 'crossing')},
            'conflict_zone': {'source_sha256': 'c'}, 'property_anchor': {'source_sha256': 'd'},
            'crossing_occupant': {'source_sha256': 'e'}}


class EncounterTests(unittest.TestCase):
    def test_both_approaches_use_distinct_sourced_lanes(self):
        for case in (module.CASES[0], module.CASES[2]):
            adapter = Adapter()
            result = module.build_case(adapter, site(), case)
            self.assertEqual(result['occupant'], 'person-1')
            self.assertIn(('vehicle', 'ego', case.approach+'0'), adapter.calls)
            self.assertTrue(any(c[0] == 'route' and c[1] == 'crossing' for c in adapter.calls))
    def test_property_offset_is_actual_spawn_parameter(self):
        offsets = []
        for case in module.CASES[4:6]:
            adapter = Adapter()
            module.build_case(adapter, site(), case)
            offsets.append([c[1] for c in adapter.calls if c[0] == 'property'][0])
        self.assertEqual(offsets, [0.0, 8.0])
    def test_premises_requires_independent_site_basis(self):
        case = module.CASES[6]
        with self.assertRaisesRegex(ValueError, 'site basis differs from case'):
            module.build_case(Adapter(), site(), case)
        premises = site(); premises['public_access_basis'] = 'public_access_premises'
        self.assertEqual(module.build_case(Adapter(), premises, case)['case_id'], case.case_id)
    def test_fail_closed_site_and_cleanup(self):
        invalid = site(); invalid['public_access_source_sha256'] = ''
        with self.assertRaisesRegex(ValueError, 'public access source missing'):
            module.build_case(Adapter(), invalid, module.CASES[0])
        adapter = Adapter(fail='property')
        with self.assertRaisesRegex(ValueError, 'property spawn failed'):
            module.build_case(adapter, site(), module.CASES[0])
        self.assertEqual([c for c in adapter.calls if c[0] == 'destroy'],
                         [('destroy', 'crossing'), ('destroy', 'ego')])
    def test_original_history_and_negative_source(self):
        rows = []
        for i in (10, 11):
            rows.append({'original_frame': i, 'source_sha256': 's', 'map_source_sha256': 'm',
                         'ego_id': 'e', 'crossing_vehicle_id': 'v', 'occupant_id': 'p',
                         'property_id': 'q', 'occupant_vehicle_id': 'v', 'ego_xy': [i-10, 0],
                         'occupant_xy': [2, 0], 'property_xy': [8, 0],
                         'ego_speed_mps': 8, 'crossing_speed_mps': 6})
        result = module.measure_history(rows, module.CASES[0])
        self.assertEqual(result['min_ego_occupant_center_distance_m'], 1)
        self.assertIsNone(result['legal_judgment'])
        bad = [dict(x) for x in rows]; bad[1]['occupant_vehicle_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'not in crossing vehicle'):
            module.measure_history(bad, module.CASES[0])
        bad = [dict(x) for x in rows]; bad[1].pop('source_sha256')
        with self.assertRaisesRegex(ValueError, 'original source missing'):
            module.measure_history(bad, module.CASES[0])
    def test_comparison_rejects_missing_and_changed_fixed(self):
        base = {k: 's' for k in ('site_sha256','map_sha256','public_access_basis',
               'ego_route_sha256','crossing_route_sha256','ego_blueprint','crossing_blueprint',
               'occupant_id','property_blueprint','weather_sha256','camera_plan_sha256',
               'original_history_sha256')}
        base.update(case_id='a', duration_frames=900, min_ego_occupant_center_distance_m=2,
                    min_ego_property_center_distance_m=4, crossing_release_s=1)
        other = dict(base, case_id='b', original_history_sha256='t', crossing_release_s=4,
                     min_ego_occupant_center_distance_m=5)
        module.audit_pair(base, other, {'crossing_release_s'})
        with self.assertRaisesRegex(ValueError, 'deliberate difference absent'):
            module.audit_pair(base, other, {'ego_route_sha256'})
        bad = dict(other, weather_sha256='different')
        with self.assertRaisesRegex(ValueError, 'fixed condition changed'):
            module.audit_pair(base, bad, {'crossing_release_s'})
        bad = dict(other); bad.pop('original_history_sha256')
        with self.assertRaisesRegex(ValueError, 'comparison source missing'):
            module.audit_pair(base, bad, {'crossing_release_s'})

if __name__ == '__main__':
    unittest.main()
