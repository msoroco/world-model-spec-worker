"""Build two unselected exact 30-second curbside Native proposals."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native'
PREFIX = ROOT.name + '__'

CAMERAS = [
    {'name': 'overview', 'width': 1920, 'height': 1080, 'fov_deg': 90,
     'location_xyz_m': [-12, 0, 12], 'rotation_pyr_deg': [-35, 0, 0]},
    {'name': 'approach', 'width': 1280, 'height': 720, 'fov_deg': 90,
     'location_xyz_m': [8, -12, 5], 'rotation_pyr_deg': [-10, 35, 0]},
    {'name': 'curb_reference', 'width': 1280, 'height': 720, 'fov_deg': 90,
     'location_xyz_m': [-8, 10, 5], 'rotation_pyr_deg': [-10, -35, 0]},
    {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fov_deg': 90,
     'location_xyz_m': [0.4, 0, 1.5], 'rotation_pyr_deg': [0, 0, 0]},
]

TESTS = '''import copy
import json
import unittest
from pathlib import Path
from runner import FRAMES, RATE, check, phase_at

class ExactCaptureContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_window_and_cameras(self):
        result = check(self.config)
        self.assertEqual((result['frames'], result['rate_hz']), (600, 20))
        self.assertEqual(len(result['camera_views']), 4)
        self.assertEqual(len([phase_at(self.config, i) for i in range(FRAMES)]), 600)
        self.assertIsNone(result['legal_verdict'])

    def test_reject_missing_camera(self):
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaisesRegex(ValueError, 'Four named'):
            check(bad)

    def test_reject_short_or_discontinuous_schedule(self):
        bad = copy.deepcopy(self.config)
        bad['control_phases'][-1]['last_frame'] = 598
        with self.assertRaises(ValueError):
            check(bad)
        bad = copy.deepcopy(self.config)
        bad['control_phases'][1]['first_frame'] += 1
        with self.assertRaises(ValueError):
            check(bad)

    def test_reject_invented_legal_verdict(self):
        bad = copy.deepcopy(self.config)
        bad['legal_verdict'] = 'careless'
        with self.assertRaises(ValueError):
            check(bad)

    def test_endpoint_rejection(self):
        with self.assertRaises(ValueError):
            phase_at(self.config, FRAMES)
'''


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def config(case_id, erratic):
    return {
        'case_id': case_id, 'selected_case_id': case_id,
        'cell_id': 'C230222', 'law_id': 'LVMC-11-22-020',
        'actor': 'motor_vehicle_driver', 'candidate_id': 'primary',
        'spawn_point_index': 0, 'duration_s': 30, 'rate_hz': 20,
        'vehicle_blueprint': 'vehicle.tesla.model3',
        'required_atoms': ['kin.position', 'kin.speed', 'kin.accel_longitudinal'],
        'cameras': CAMERAS,
        'control_phases': [
            {'name': 'approach', 'first_frame': 0, 'last_frame': 199,
             'throttle': 0.24, 'steer': 0, 'brake': 0},
            {'name': 'curbside_travel', 'first_frame': 200, 'last_frame': 479,
             'throttle': 0.14 if erratic else 0.20,
             'steer': 0.12 if erratic else 0, 'brake': 0},
            {'name': 'departure', 'first_frame': 480, 'last_frame': 599,
             'throttle': 0.10, 'steer': 0, 'brake': 0},
        ],
        'legal_verdict': None,
    }


def main():
    entries = []
    runner = (NATIVE / 'native_runner.py').read_text()
    for label, erratic in (('controlled_draft', False), ('erratic_draft', True)):
        case_id = PREFIX + label
        proposal = {
            'actor': 'motor_vehicle_driver', 'case_id': case_id,
            'cell_id': 'C230222', 'law_id': 'LVMC-11-22-020',
            'entrypoint': 'runner.py',
            'files': [
                {'path': 'runner.py', 'content': runner},
                {'path': 'config.json', 'content': json.dumps(config(case_id, erratic), indent=2) + '\n'},
                {'path': 'tests/test_offline.py', 'content': TESTS},
            ],
            'measurement_plan': 'Retain 600 original Native motion/frame-map rows and four synchronized source cameras. Original geometry and collision review remain necessary.',
            'mechanisms': ['synchronous 20 Hz Native capture',
                           'four source-camera encodes', 'source-bound motion trace'],
            'recording_description': {
                'channels': [{'name': 'curbside_driving_cues', 'unit': 'structured',
                              'sampling_rate_hz': 20, 'time_window': '600 frames',
                              'method': 'measure original Native trace and context'}],
                'limitations': ['Control requests do not establish observed motion or legal carelessness.']},
            'static_checks': ['exact assignment', '600 frames', 'four cameras',
                              'continuous control schedule', 'no legal verdict'],
            'status': 'draft_cpu_offline_only',
            'termination_rules': ['600 source frames or explicit capture failure'],
        }
        source = ROOT / 'draft-native' / label / 'primary' / 'construction.json'
        write(source, proposal)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        entries.append({'case_id': case_id, 'kind': 'draft_not_selected',
                        'construction': str(source.relative_to(ROOT)),
                        'construction_sha256': digest,
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Actual curbside course and camera visibility require Native observation.'}})
    manifest = {'assignment_id': ROOT.name,
                'format': 'worker-unselected-draft-construction-manifest-v1',
                'status': 'draft_cpu_offline_only', 'cases': entries}
    write(ROOT / 'draft-native-manifest.json', manifest)
    print(json.dumps({'manifest': 'draft-native-manifest.json',
                      'cases': {entry['case_id']: entry['construction_sha256'] for entry in entries}}))


if __name__ == '__main__':
    main()
