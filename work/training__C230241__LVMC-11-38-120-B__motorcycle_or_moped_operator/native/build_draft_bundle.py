"""Build one unselected exact lighting capture bundle for pinned offline proof."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native'
CASE = ROOT.name + '__reference'
TESTS = '''import copy
import json
import unittest
from pathlib import Path
from runner import FRAMES, RATE, check, phase_at


class CaptureContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_full_source_window(self):
        result = check(self.config)
        self.assertEqual((result['frames'], result['rate_hz']), (600, 20))
        self.assertEqual(result['source_views'],
                         ['overview', 'approach', 'reference_corner', 'driver_reference'])
        self.assertFalse(result['physical_visibility_verified'])
        self.assertEqual([phase_at(self.config, i)['name'] for i in
                          (0, 399, 400, 499, 500, 599)],
                         ['travel', 'travel', 'braking', 'braking', 'hold', 'hold'])
        self.assertEqual((FRAMES, RATE), (600, 20))
        with self.assertRaises(ValueError):
            phase_at(self.config, 600)

    def test_missing_camera_and_window_rejected(self):
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaises(ValueError):
            check(bad)
        bad = copy.deepcopy(self.config)
        bad['control_phases'][-1]['last_frame'] = 598
        with self.assertRaises(ValueError):
            check(bad)

    def test_wrong_actor_and_lamp_request_rejected(self):
        bad = copy.deepcopy(self.config)
        bad['actor'] = 'motor_vehicle_driver'
        with self.assertRaises(ValueError):
            check(bad)
        bad = copy.deepcopy(self.config)
        bad['requested_light_state'] = 'Off'
        with self.assertRaises(ValueError):
            check(bad)

    def test_no_fabricated_physical_outcome(self):
        bad = copy.deepcopy(self.config)
        bad['physical_visibility_verified'] = True
        with self.assertRaises(ValueError):
            check(bad)
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    config = json.loads((NATIVE / 'config.json').read_text())
    assert config['case_id'] == CASE
    construction = {
        'actor': config['actor'], 'case_id': CASE, 'cell_id': config['cell_id'],
        'law_id': config['law_id'], 'entrypoint': 'runner.py',
        'files': [
            {'path': 'runner.py', 'content': (NATIVE / 'native_runner.py').read_text()},
            {'path': 'config.json', 'content': (NATIVE / 'config.json').read_text()},
            {'path': 'tests/test_offline.py', 'content': TESTS}],
        'recording_description': {
            'channels': [
                {'name': 'native_lighting_frames', 'unit': 'structured',
                 'sampling_rate_hz': 20,
                 'method': 'original Native same-tick light state and motion',
                 'time_window': '600 frames'},
                {'name': 'four_camera_video', 'unit': 'lossless pixels',
                 'sampling_rate_hz': 20,
                 'method': 'four synchronized source cameras',
                 'time_window': '600 frames'}],
            'context_inputs': [
                {'name': 'independent_lamp_range_review', 'unit': 'ft',
                 'method': 'calibrated original camera and site review'},
                {'name': 'sunset_sunrise', 'unit': 'UTC seconds',
                 'method': 'source-documented site/date clock'}],
            'limitations': [
                'A requested light state does not prove lit colour or range.',
                'Sun altitude request does not prove statutory civil time.',
                'Candidate vendor blueprint and site geometry need Native review.']},
        'measurement_plan': 'Join 600 original lighting frames to the original frame map; independently source clock, lamp placement, calibrated 300/500 ft ranges and discernibility.',
        'mechanisms': ['same-tick motion and light-state capture',
                       '20 Hz full 30-second capture',
                       'four source camera streams',
                       'owned world restoration and capture seal'],
        'static_checks': ['frozen cell and actor', '600-frame controller',
                          'lamp request', 'four camera profiles',
                          'no invented physical/legal outcome'],
        'termination_rules': ['600 synchronized frames or explicit failure',
                              'release sensors/actors and restore world'],
        'status': 'draft_cpu_offline_only'}
    source = ROOT / 'draft-primary' / 'reference' / 'primary' / 'construction.json'
    write(source, construction)
    manifest = {
        'assignment_id': ROOT.name,
        'format': 'worker-unselected-draft-construction-manifest-v1',
        'status': 'draft_cpu_offline_only',
        'cases': [{'case_id': CASE, 'kind': 'draft_not_selected',
                   'construction': str(source.relative_to(ROOT)),
                   'construction_sha256': sha(source),
                   'candidate_risk': {
                       'status': 'physical',
                       'reason': 'Lamp model, mounted tail lamp, calibrated range, vendor identity and site geometry require original Native review.'}}]}
    write(ROOT / 'draft-primary-manifest.json', manifest)
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(source)}))


if __name__ == '__main__':
    main()
