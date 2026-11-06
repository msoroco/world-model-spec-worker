"""Self-contained CPU preflight for each exact materialized C10052 bundle."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engineering import NAMES, TRIGGERS, parameters
from geometry import body, check, route
from measure_facility import measure, overlap_area
from fallback_triggers import evaluate as evaluate_triggers, sha as trigger_sha
from measure_entry import measure as measure_entry
from runner import check as runner_check


class ExactBundleTests(unittest.TestCase):
    def test_exact_runner_preflight(self):
        config = json.loads((ROOT/'config.json').read_text())
        result = runner_check(config)
        self.assertFalse(result['native_imported'])
        self.assertFalse(result['physical_success_claimed'])
        self.assertEqual(result['camera_count'], 4)

    def test_map_route_and_distinct_fallbacks(self):
        self.assertEqual(check()['roads'], [1, 2])
        self.assertEqual(route('probe_a')[:151], route('probe_b')[:151])
        base = parameters('probe_b', 'primary')
        changed = [{key for key in base if base[key] != parameters('probe_b', name)[key]}
                   for name in NAMES[1:]]
        self.assertEqual(len({frozenset(s) for s in changed}), 3)
        self.assertTrue(all(TRIGGERS[name]['source'] and TRIGGERS[name]['metric']
                            for name in NAMES[1:]))

    def test_original_source_positive_and_missing_context_negative(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            geometry = {'road_id': 1, 'driving_lane_id': -1, 'bicycle_lane_id': -2,
                        'bicycle_facility_native_xy_bounds_m': [-60, -5, 60, -3],
                        'alley_entrance_native_xy_bounds_m': [-3, -14, 3, -5],
                        'native_facility_design_verified': False}
            (folder/'road_geometry.json').write_text(json.dumps(geometry))
            rows = [{'native_frame': 100+i, 'time_s': (i+1)/20,
                     'native_center_xy_m': [-12, -4], 'native_forward_xy': [1, 0],
                     'native_body_xy_m': body(-12, -4), 'native_road_id': 1,
                     'native_lane_id': -2, 'speed_mps': 0.0} for i in range(40)]
            (folder/'native_samples.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError, 'Missing required source: exception_context.json'):
                measure(folder/'native_samples.jsonl', folder/'road_geometry.json',
                        folder/'exception_context.json')
            flags = {key: False for key in ('entering_or_exiting_alley_or_driveway',
                'disabled_vehicle', 'avoiding_traffic_conflict', 'official_duties',
                'police_direction', 'emergency')}
            (folder/'exception_context.json').write_text(json.dumps({
                'source_kind': 'synthetic_scene_request', 'exceptions': flags}))
            value = measure(folder/'native_samples.jsonl', folder/'road_geometry.json',
                            folder/'exception_context.json')
            self.assertEqual(value['max_stopped_overlap_m2'], 9.36)
            self.assertEqual(value['observed_exception_status'], 'unresolved')

    def test_rotated_body_clipping(self):
        forward = (math.cos(math.radians(20)), math.sin(math.radians(20)))
        self.assertGreater(overlap_area(body(-12, -4, forward), (-60, -5, 60, -3)), 0)
        self.assertEqual(overlap_area(body(-12, -1.5), (-60, -5, 60, -3)), 0)

    def test_saved_trigger_source_join_and_changed_hash(self):
        config=json.loads((ROOT/'config.json').read_text())
        target_y=-1.5 if config['case_suffix']=='probe_a' else -4.0
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            (folder/'config.json').write_text(json.dumps(config))
            samples=[];images=[]
            for i in range(480):
                x=-45+(33*i/40) if i<40 else -12
                y=target_y
                frame=100+i;time=round((i+1)/20,5)
                samples.append({'native_frame':frame,'time_s':time,
                    'native_center_xy_m':[x,y],'speed_mps':5 if i<40 else 0,
                    'synthetic_diagnostic':True})
                images.append({'native_frame':frame,'time_s':time,
                    'synthetic_diagnostic':True,'views':{
                        view:{'full_body':True,'facility_edge':True}
                        for view in ('overview','facility')}})
            for name,values in (('native_samples.jsonl',samples),
                                ('camera_visibility.jsonl',images)):
                (folder/name).write_text(''.join(json.dumps(value)+'\n' for value in values))
            manifest={'format':'c10052-trigger-sources-v1',
                'source_kind':'synthetic_cpu_fixture','route_survey_passed':True,
                'sha256':{name:trigger_sha(folder/name) for name in
                    ('native_samples.jsonl','camera_visibility.jsonl','config.json')}}
            (folder/'trigger-sources.json').write_text(json.dumps(manifest))
            measured=evaluate_triggers(folder)
            self.assertEqual(measured['frames'],480)
            self.assertFalse(any(measured[f'fallback{i}_trigger_measured'] for i in range(1,4)))
            (folder/'camera_visibility.jsonl').write_text(
                (folder/'camera_visibility.jsonl').read_text()+' ')
            with self.assertRaisesRegex(ValueError,'Trigger source hash differs'):
                evaluate_triggers(folder)

    def test_moving_entry_saved_source_and_missing_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            road={'road_id':1,'driving_lane_id':-1,'bicycle_lane_id':-2,
                  'bicycle_facility_native_xy_bounds_m':[-60,-5,60,-3],
                  'alley_entrance_native_xy_bounds_m':[-3,-14,3,-5],
                  'native_facility_design_verified':False}
            (folder/'road_geometry.json').write_text(json.dumps(road))
            samples=[]
            for i in range(480):
                x=-45+min(i,132)*.25
                y=-1.5 if i<80 else -1.5-2.5*min(1,(i-80)/60)
                samples.append({'native_frame':100+i,'time_s':round((i+1)/20,5),
                    'native_center_xy_m':[x,y],'native_body_xy_m':body(x,y),
                    'native_road_id':1,'native_lane_id':-2 if y<=-3 else -1,
                    'speed_mps':5 if i<132 else 0,'synthetic_diagnostic':True})
            (folder/'native_samples.jsonl').write_text(
                ''.join(json.dumps(row)+'\n' for row in samples))
            with self.assertRaises(FileNotFoundError):
                measure_entry(folder)
            (folder/'entry-sources.json').write_text(json.dumps({
                'format':'c10052-entry-sources-v1','source_kind':'synthetic_cpu_fixture',
                'sha256':{name:trigger_sha(folder/name) for name in
                          ('native_samples.jsonl','road_geometry.json')}}))
            result=measure_entry(folder)
            self.assertTrue(result['moving_entry_measured'])
            self.assertGreater(result['first_entry_alley_footprint_gap_m'],0)
            self.assertEqual(result['moving_facility_alley_footprint_overlap_frames'],0)
            self.assertFalse(result['facility_designation_verified'])
            self.assertFalse(result['legal_verdict_claimed'])


if __name__ == '__main__':
    unittest.main()
