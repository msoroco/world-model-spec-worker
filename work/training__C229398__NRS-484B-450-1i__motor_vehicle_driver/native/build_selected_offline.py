"""Build two prospective exact Native rail constructions; no simulation."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native'
AID = ROOT.name
FILES = ('rail_capture_runner.py', 'rail_native_geometry.py',
         'rail_source_contract.py', 'rail_footprint_meter.py', 'rail_finalize.py')
TARGETS = {'condition_a': 12.5, 'condition_b': 16.5,
           'stop_1': 12.5, 'stop_2': 16.5,
           'stand_1': 12.5, 'stand_2': 16.5}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(suffix, target, candidate_id="primary"):
    case_id = AID + ('__selected_98183a3f__' if suffix.startswith('condition_') else '__') + suffix
    folder = NATIVE / suffix / (candidate_id if candidate_id != 'primary' else '')
    folder.mkdir(exist_ok=True)
    channels = [{'name': 'rail_footprint', 'unit': 'structured',
                 'method': 'Original Native pose, extent and physical rail survey',
                 'sampling_rate_hz': 20, 'time_window': 'all 600 original frames',
                 'reference_frame': 'C229398 road and both surveyed physical rails',
                 'uncertainty': 'Physical rail identity, actual event and legal applicability require original review'}]
    config = {'case_id': case_id, 'selected_case_id': case_id,
              'law_id': 'NRS-484B-450-1i', 'cell_id': 'C229398',
              'actor': 'motor_vehicle_driver', 'rate_hz': 20,
              'duration_s': 30, 'duration_frames': 600,
              'target_footprint_gap_m': target,
              'behavior_variant': 'park' if suffix.startswith('condition_') else
                  ('stop_depart' if suffix.startswith('stop_') else 'stand_depart'),
              'approach_distance_m': 7.0 if candidate_id == 'fallback1' else 10.0,
              'approach_speed_cap_mps': 1.0 if candidate_id == 'fallback1' else 1.5,
              'rail_source_kind': 'native_survey',
              'physical_verified': False, 'legal_verdict': None,
              'physical_completion': {'criterion': 'travel_progress',
                  'minimum_progress_m': 5.0,
                  'completion_goal_method': 'At least 5 m of source-joined approach motion before independently reviewed parking/rest assessment; engineering only, not legal threshold or full maneuver acceptance'},
              'required_atoms': ['kin.extent', 'kin.velocity'],
              'recording_description': {'channels': channels, 'context_inputs': [],
                  'limitations': ['Physical rail identity, distance, pixels, traffic-conflict necessity, legal or officer/device authority and legal application require original review']},
              'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                           'height': 1080 if name == 'overview' else 720,
                           'fps': 20, 'fov': 90}
                          for name in ('overview', 'approach', 'reference_corner', 'driver_reference')]}
    test = '''import copy
import json
import unittest
from pathlib import Path
from runner import check

class RailCaptureContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())
    def test_exact_request(self):
        self.assertEqual(check(self.config)['frames'], 600)
    def test_missing_camera(self):
        wrong = copy.deepcopy(self.config); wrong['cameras'].pop()
        with self.assertRaisesRegex(ValueError, 'Four exact'):
            check(wrong)
    def test_changed_rail_gap(self):
        wrong = copy.deepcopy(self.config); wrong['target_footprint_gap_m'] = 14.5
        with self.assertRaisesRegex(ValueError, 'target changed'):
            check(wrong)
    def test_claimed_physical_result(self):
        wrong = copy.deepcopy(self.config); wrong['physical_verified'] = True
        with self.assertRaisesRegex(ValueError, 'claims an outcome'):
            check(wrong)
'''
    files = [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
             {'path': 'runner.py', 'content': (NATIVE / 'rail_capture_runner.py').read_text()},
             {'path': 'tests/test_offline.py', 'content': test}]
    files += [{'path': name, 'content': (NATIVE / name).read_text()}
              for name in FILES if name != 'rail_capture_runner.py']
    construction = {'format': 'worker-inline-construction', 'case_id': case_id,
                    'cell_id': 'C229398', 'actor': 'motor_vehicle_driver',
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': config['recording_description'],
                    'status': 'prospective_selected_construction_cpu_only'}
    path = folder / 'construction.json'
    path.write_text(json.dumps(construction, indent=2) + '\n')
    (folder / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    return {'case_id': case_id, 'construction': str(path.relative_to(NATIVE)),
            'construction_sha256': sha(path)}


if __name__ == '__main__':
    cases = []
    for suffix, target in TARGETS.items():
        primary = build(suffix, target)
        fallback = build(suffix, target, 'fallback1')
        primary['candidate_risk'] = {'status': 'physical',
            'reason': 'Ten-meter approach can overshoot or fail to settle at the rail event target; a slower seven-meter approach preserves the exact gap and capture contract.'}
        primary['candidates'] = [{'id': 'fallback1',
            'construction': fallback['construction'],
            'construction_sha256': fallback['construction_sha256'],
            'trigger': {'source': 'original Native speed/pose trace',
                        'metric': 'target approach overshoot or no requested rest interval',
                        'failure_condition': 'vehicle passes requested rail event target or does not remain at rest during its requested hold phase'},
            'changed_knobs': ['approach_distance_m: 10.0 -> 7.0',
                              'approach_speed_cap_mps: 1.5 -> 1.0']} ]
        cases.append(primary)
    manifest = {'format': 'worker-selected-offline-probe-manifest',
                'assignment_id': AID, 'status': 'partial', 'cases': cases,
                'original_native_observed': False, 'delivery_ready': False}
    path = ROOT / 'native/selected-offline-probe-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'manifest_sha256': sha(path)}))
