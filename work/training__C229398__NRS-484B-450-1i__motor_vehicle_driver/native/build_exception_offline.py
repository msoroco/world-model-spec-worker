"""Build eight separate requested exception comparisons without a legal verdict."""

import hashlib
import json
from pathlib import Path

from rail_exception_context import BRANCHES


PACKAGE = Path(__file__).resolve().parents[1]
NATIVE = PACKAGE / 'native'
FILES = ('rail_native_geometry.py', 'rail_source_contract.py',
         'rail_footprint_meter.py', 'rail_finalize.py',
         'rail_exception_context.py', 'rail_exception_finalize.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build(suffix, candidate='primary'):
    case_id = PACKAGE.name + '__' + suffix
    target = NATIVE / suffix / (candidate if candidate != 'primary' else '')
    target.mkdir(parents=True, exist_ok=True)
    description = {'channels': [{'name': 'rail_footprint', 'unit': 'structured',
        'method': 'Original Native pose, extent and physical rail survey',
        'sampling_rate_hz': 20, 'time_window': 'all 600 original frames',
        'reference_frame': 'C229398 road and both surveyed physical rails',
        'uncertainty': 'Physical rail identity, actual event and legal applicability require original review'}],
        'context_inputs': [{'name': 'exception_context', 'unit': 'structured',
            'method': 'Reviewed, hash-bound traffic or authority source supplied to Native; diagnostic synthetic packet for CPU proof'}],
        'limitations': ['Physical rail identity, distance, pixels, traffic-conflict necessity, legal or officer/device authority and legal application require original review']}
    config = {'case_id': case_id, 'selected_case_id': case_id,
        'law_id': 'NRS-484B-450-1i', 'cell_id': 'C229398',
        'actor': 'motor_vehicle_driver', 'rate_hz': 20,
        'duration_s': 30, 'duration_frames': 600,
        'target_footprint_gap_m': 12.5, 'behavior_variant': 'park',
        'requested_exception_context': suffix.endswith('_2'),
        'approach_distance_m': 7.0 if candidate == 'fallback1' else 10.0,
        'approach_speed_cap_mps': 1.0 if candidate == 'fallback1' else 1.5,
        'rail_source_kind': 'native_survey', 'physical_verified': False,
        'legal_verdict': None,
        'physical_completion': {'criterion': 'travel_progress',
            'minimum_progress_m': 5.0,
            'completion_goal_method': 'At least 5 m of source-joined approach motion before independent rail and exception review; engineering only'},
        'required_atoms': ['kin.extent', 'kin.velocity'],
        'source_packets': [], 'recording_description': description,
        'cameras': [{'name': name,
            'width': 1920 if name == 'overview' else 1280,
            'height': 1080 if name == 'overview' else 720,
            'fps': 20, 'fov': 90}
            for name in ('overview', 'approach', 'reference_corner', 'driver_reference')]}
    test = '''import copy
import json
import unittest
from pathlib import Path
from runner import check

class RailExceptionCaptureContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())
    def test_exact_request(self):
        self.assertEqual(check(self.config)['frames'], 600)
    def test_missing_camera(self):
        wrong = copy.deepcopy(self.config); wrong['cameras'].pop()
        with self.assertRaisesRegex(ValueError, 'Four exact'):
            check(wrong)
    def test_changed_exception_request(self):
        wrong = copy.deepcopy(self.config)
        wrong['requested_exception_context'] = not wrong['requested_exception_context']
        with self.assertRaisesRegex(ValueError, 'Exact exception request changed'):
            check(wrong)
    def test_claimed_physical_result(self):
        wrong = copy.deepcopy(self.config); wrong['physical_verified'] = True
        with self.assertRaisesRegex(ValueError, 'claims an outcome'):
            check(wrong)
'''
    files = [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
             {'path': 'runner.py', 'content': (NATIVE / 'rail_capture_runner.py').read_text()},
             {'path': 'tests/test_offline.py', 'content': test}]
    files += [{'path': name, 'content': (NATIVE / name).read_text()} for name in FILES]
    construction = {'format': 'worker-inline-construction', 'case_id': case_id,
        'cell_id': 'C229398', 'actor': 'motor_vehicle_driver',
        'entrypoint': 'runner.py', 'files': files,
        'recording_description': description,
        'status': 'prospective_selected_construction_cpu_only'}
    path = target / 'construction.json'
    write(path, construction)
    write(target / 'config.json', config)
    return {'case_id': case_id, 'construction': str(path.relative_to(NATIVE)),
            'construction_sha256': sha(path), 'candidate_id': candidate}


if __name__ == '__main__':
    rows = []
    for branch in BRANCHES:
        for index in (1, 2):
            suffix = branch + '_' + str(index)
            primary, fallback = build(suffix), build(suffix, 'fallback1')
            primary['candidate_risk'] = {'status': 'physical',
                'reason': 'Original approach may overshoot or fail to settle; slower approach preserves requested context and gap.'}
            primary['candidates'] = [{'id': 'fallback1',
                'construction': fallback['construction'],
                'construction_sha256': fallback['construction_sha256'],
                'trigger': {'source': 'original Native pose and speed',
                            'metric': 'approach overshoot or missing rest',
                            'failure_condition': 'vehicle passes requested rail target or fails to rest'},
                'changed_knobs': ['approach_distance_m: 10.0 -> 7.0',
                                  'approach_speed_cap_mps: 1.5 -> 1.0']}]
            rows.append(primary)
    write(NATIVE / 'exception-offline-probe-manifest.json', {
        'format': 'worker-selected-offline-probe-manifest',
        'assignment_id': PACKAGE.name, 'status': 'partial',
        'original_native_observed': False, 'delivery_ready': False,
        'cases': [{key: value for key, value in row.items() if key != 'candidate_id'}
                  for row in rows]})
    print(json.dumps({'case_count': len(rows), 'candidate_count': len(rows) * 2}))
