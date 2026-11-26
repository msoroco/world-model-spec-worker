import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from access_aisle import CASES, construct, intersection_area, measure_original, validate_site


def site():
    data = {'cell_id': 'C150072', 'actor': 'motor_vehicle_driver',
            'aisle_polygon_xy': [[0, 0], [3, 0], [3, 6], [0, 6]],
            'adjacent_space_polygon_xy': [[3, 0], [6, 0], [6, 6], [3, 6]],
            'approach_route_xy': [[-5, 3], [-2, 3], [0, 3]],
            'target_footprints': {
                'aisle_full': {'source_sha256': 'full', 'polygon_xy': [[.5, 1], [2.5, 1], [2.5, 5], [.5, 5]]},
                'aisle_partial': {'source_sha256': 'partial', 'polygon_xy': [[2.5, 1], [4.5, 1], [4.5, 5], [2.5, 5]]},
                'adjacent_space': {'source_sha256': 'adjacent', 'polygon_xy': [[3.5, 1], [5.5, 1], [5.5, 5], [3.5, 5]]}}}
    for name in ('jurisdiction', 'map', 'aisle_marking', 'adjacent_designated_space',
                 'accessible_route', 'ingress_egress_design', 'vehicle_blueprint',
                 'approach_route'):
        data[name + '_source_sha256'] = 'fixture-' + name
    data['designation_relies_on_135a'] = True
    for name in ('access_symbol', 'fine_wording', 'sign_bottom_height'):
        data[name + '_source_sha256'] = 'fixture-' + name
    return data


def rows(data, case):
    return [{'original_frame': 500 + i, 'time_s': i / 20,
             'source_sha256': 'fixture-original', 'body_geometry_source_sha256': 'fixture-body',
             'control_source_sha256': 'fixture-control', 'activity_source_sha256': 'fixture-activity',
             'map_source_sha256': data['map_source_sha256'],
             'aisle_marking_source_sha256': data['aisle_marking_source_sha256'],
             'ego_id': 'ego-1', 'ego_speed_mps': 1 if case.requested_activity == 'travel' else 0,
             'observed_activity': case.requested_activity,
             'vehicle_body_polygon_xy': data['target_footprints'][case.target]['polygon_xy']}
            for i in range(900)]


class Adapter:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail

    def spawn_vehicle(self, xy, role):
        self.events.append(('spawn', tuple(xy), role))
        return 'ego-1'

    def set_parking_route(self, ego, route, target_footprint):
        self.events.append(('route', ego))
        if self.fail:
            raise RuntimeError('route failed')

    def request_activity(self, ego, activity):
        self.events.append(('activity', activity))

    def destroy(self, actor):
        self.events.append(('destroy', actor))


class AccessAisleTest(unittest.TestCase):
    def test_geometry_and_all_exact_case_observations(self):
        data = site()
        self.assertEqual(validate_site(data)['planned_aisle_overlap_m2'],
                         {'aisle_full': 8, 'aisle_partial': 2, 'adjacent_space': 0})
        for case in CASES:
            with self.subTest(case=case.case_id):
                adapter = Adapter()
                built = construct(adapter, data, case)
                self.assertIsNone(built['legal_judgment'])
                self.assertEqual(adapter.events[-1], ('activity', case.requested_activity))
                measured = measure_original(rows(data, case), data, case)
                self.assertEqual(measured['frame_count'], 900)
                self.assertEqual(measured['parking_judgment'], 'unresolved')
                self.assertEqual(measured['terminal_mean_aisle_body_overlap_m2'],
                                 0 if case.target == 'adjacent_space' else
                                 2 if case.target == 'aisle_partial' else 8)

    def test_source_designation_and_polygon_rejections(self):
        data = site()
        del data['sign_bottom_height_source_sha256']
        with self.assertRaisesRegex(ValueError, 'sign/designation'):
            validate_site(data)
        data = site()
        data['target_footprints']['aisle_partial']['polygon_xy'] = [[3.5, 1], [5.5, 1], [5.5, 5], [3.5, 5]]
        with self.assertRaisesRegex(ValueError, 'isolate aisle placement'):
            validate_site(data)
        self.assertEqual(intersection_area([[0, 0], [2, 0], [2, 2], [0, 2]],
                                           [[2, 0], [4, 0], [4, 2], [2, 2]]), 0)

    def test_original_join_and_activity_rejections(self):
        data = site()
        case = CASES[0]
        original = rows(data, case)
        original[10]['original_frame'] = 999
        with self.assertRaisesRegex(ValueError, 'frame/time'):
            measure_original(original, data, case)
        original = rows(data, case)
        original[-10]['observed_activity'] = 'loading_stop'
        with self.assertRaisesRegex(ValueError, 'activity differs'):
            measure_original(original, data, case)
        original = rows(data, case)
        original[-1]['vehicle_body_polygon_xy'] = data['target_footprints']['adjacent_space']['polygon_xy']
        self.assertGreater(measure_original(original, data, case)['terminal_mean_aisle_body_overlap_m2'], 0)
        original = rows(data, case)
        for row in original[-20:]:
            row['vehicle_body_polygon_xy'] = data['target_footprints']['adjacent_space']['polygon_xy']
        with self.assertRaisesRegex(ValueError, 'did not occupy'):
            measure_original(original, data, case)

    def test_owned_actor_cleanup(self):
        adapter = Adapter(fail=True)
        with self.assertRaisesRegex(RuntimeError, 'route failed'):
            construct(adapter, site(), CASES[0])
        self.assertEqual(adapter.events[-1], ('destroy', 'ego-1'))


if __name__ == '__main__':
    unittest.main()
