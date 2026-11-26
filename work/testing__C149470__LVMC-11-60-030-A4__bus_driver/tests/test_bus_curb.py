import importlib.util
from pathlib import Path
import sys
import unittest
from math import radians, tan


path = Path(__file__).resolve().parents[1] / 'bus_curb.py'
spec = importlib.util.spec_from_file_location('bus_curb', path)
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


def scene(case):
    s = dict(cell_id='C149470', actor='bus_driver',
             operator_controls_bus=True, bus_qualifies=True,
             tour_bus=False, public_street=True,
             location_kind=case.location, activity=case.activity,
             target_distance_m=case.target_distance_m,
             heading_request_deg=case.heading_request_deg,
             traffic_lateral_request_m=case.traffic_lateral_request_m,
             location_designated=True, location_governs_bus=True,
             location_boundary_xy=[[0, 0], [10, 0]],
             curb_segment_xy=[[0, 0], [10, 0]],
             bus_route_xy=[[-5, case.target_distance_m + 10*tan(radians(case.heading_request_deg))],
                           [5, case.target_distance_m]],
             traffic_route_xy=[[-5, case.traffic_lateral_request_m],
                               [20, case.traffic_lateral_request_m]],
             loading_actor_ids=['passenger-or-baggage-1'])
    for field in ('jurisdiction', 'bus_class', 'tour_exclusion',
                  'operator', 'location_boundary', 'location_designation',
                  'signs', 'curb_geometry', 'right_front_wheel',
                  'bus_route', 'loading_activity', 'traffic_route'):
        s[field + '_source_sha256'] = 'a' * 64
    return s


def rows(case, s):
    output = []
    for i in range(900):
        row = dict(original_frame=100+i, time_s=i/20,
                   bus_id='bus', traffic_id='traffic', activity=case.activity,
                   bus_speed_mps=2 if i < 100 else 0,
                   traffic_speed_mps=3,
                   right_front_wheel_xy=[5,case.target_distance_m],
                   wheel_position_uncertainty_m=.001,
                   bus_curb_angle_deg=case.heading_request_deg,
                   loading_active=i>=150,
                   curb_geometry_source_sha256=s['curb_geometry_source_sha256'])
        for field in ('frame', 'bus_motion', 'traffic_motion',
                      'right_front_wheel', 'curb_geometry',
                      'location_designation', 'loading_activity'):
            row[field + '_source_sha256'] = 'a' * 64
        output.append(row)
    return output


class Adapter:
    def __init__(self, fail=False):
        self.calls=[];self.fail=fail

    def __getattr__(self,name):
        def invoke(*args):
            self.calls.append((name,args))
            if name=='spawn_traffic' and self.fail: return None
            if name.startswith('spawn_'): return name
        return invoke


class BusTests(unittest.TestCase):
    def test_engineering_requests_require_route_geometry(self):
        heading = next(case for case in probe.CASES
                       if case.name == 'parallel_source_review-0002')
        angled = scene(heading)
        angled['bus_route_xy'][0][1] = heading.target_distance_m
        with self.assertRaisesRegex(ValueError, 'heading request'):
            probe.validate_scene(angled, heading)
        traffic = next(case for case in probe.CASES
                       if case.name == 'traffic_impediment_source_review-0002')
        offset = scene(traffic)
        offset['traffic_route_xy'][0][1] = 3.0
        with self.assertRaisesRegex(ValueError, 'lateral request'):
            probe.validate_scene(offset, traffic)

    def test_all_cases_construct_and_measure(self):
        for case in probe.CASES:
            with self.subTest(case=case.name):
                s=scene(case);adapter=Adapter()
                probe.construct(adapter,s,case)
                self.assertIn('set_loading_activity',[x[0] for x in adapter.calls])
                result=probe.measure_original(rows(case,s),s,case)
                self.assertAlmostEqual(result['maximum_right_front_wheel_curb_m'],
                                       case.target_distance_m)
                self.assertEqual(result['statutory_limit_m'],.4572)
                self.assertIsNone(result['parallel_judgment'])
                expected = ('within' if case.target_distance_m < .4572 else
                            'beyond' if case.target_distance_m > .4572 else
                            'indeterminate')
                self.assertEqual(result['distance_interval_relation_to_18_in'],
                                 expected)
                self.assertEqual(result['longest_continuous_stopped_loading_frames'],
                                 750)

    def test_missing_source_and_activity_rejected(self):
        case=probe.CASES[0];s=scene(case);data=rows(case,s)
        del data[5]['right_front_wheel_source_sha256']
        with self.assertRaisesRegex(ValueError,'source missing'):
            probe.measure_original(data,s,case)
        data=rows(case,s)
        for row in data: row['loading_active']=False
        with self.assertRaisesRegex(ValueError,'stopped loading'):
            probe.measure_original(data,s,case)

    def test_continuous_loading_and_source_binding(self):
        case=probe.CASES[0];s=scene(case);data=rows(case,s)
        for i,row in enumerate(data): row['loading_active']=(i>=100 and i%2==0)
        with self.assertRaisesRegex(ValueError,'stopped loading'):
            probe.measure_original(data,s,case)
        data=rows(case,s)
        data[160]['right_front_wheel_source_sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'context changed'):
            probe.measure_original(data,s,case)

    def test_measurement_excludes_preloading_stop(self):
        case=probe.CASES[0];s=scene(case);data=rows(case,s)
        for i in range(100,150): data[i]['right_front_wheel_xy'][1]=2
        result=probe.measure_original(data,s,case)
        self.assertAlmostEqual(result['maximum_right_front_wheel_curb_m'],
                               case.target_distance_m)

    def test_tour_bus_and_spawn_rejected(self):
        case=probe.CASES[0];s=scene(case);s['tour_bus']=True
        with self.assertRaisesRegex(ValueError,'non-tour bus'):
            probe.validate_scene(s,case)
        adapter=Adapter(fail=True)
        with self.assertRaisesRegex(ValueError,'traffic spawn failed'):
            probe.construct(adapter,scene(case),case)
        self.assertEqual(adapter.calls[-1][0],'destroy')


if __name__=='__main__':
    unittest.main()
