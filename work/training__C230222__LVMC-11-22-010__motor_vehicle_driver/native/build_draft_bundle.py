"""Rebuild the unselected C230222 reference bundle from worker-owned sources."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native'
CASE = 'training__C230222__LVMC-11-22-010__motor_vehicle_driver__reference'
TESTS = '''import copy
import json
import unittest
from pathlib import Path
from runner import FRAMES, RATE, check, phase_at


class CaptureContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_complete_source_window(self):
        receipt = check(self.config)
        self.assertEqual((receipt['frames'], receipt['rate_hz']), (600, 20))
        self.assertFalse(receipt['attention_observed'])
        self.assertEqual([phase_at(self.config, i)['name'] for i in
                          (0, 199, 200, 479, 480, 599)],
                         ['approach', 'approach', 'travel', 'travel',
                          'departure', 'departure'])
        self.assertEqual(len([phase_at(self.config, i) for i in range(FRAMES)]), FRAMES)
        with self.assertRaises(ValueError):
            phase_at(self.config, FRAMES)

    def test_reject_missing_camera_and_short_window(self):
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaises(ValueError):
            check(bad)
        bad = copy.deepcopy(self.config)
        bad['control_phases'][-1]['last_frame'] = 598
        with self.assertRaises(ValueError):
            check(bad)

    def test_reject_invented_attention(self):
        bad = copy.deepcopy(self.config)
        bad['driver_attention_to_operation'] = True
        with self.assertRaises(ValueError):
            check(bad)

    def test_source_files_present(self):
        self.assertTrue(Path('attention_observation.py').is_file())
        self.assertEqual(RATE, 20)
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    config = json.loads((NATIVE / 'config.json').read_text())
    assert config['case_id'] == CASE
    construction = {
        'actor': config['actor'], 'case_id': CASE,
        'cell_id': config['cell_id'], 'law_id': config['law_id'],
        'entrypoint': 'runner.py',
        'files': [
            {'path': 'runner.py', 'content': (NATIVE / 'native_runner.py').read_text()},
            {'path': 'attention_observation.py',
             'content': (NATIVE / 'attention_observation.py').read_text()},
            {'path': 'config.json', 'content': (NATIVE / 'config.json').read_text()},
            {'path': 'tests/test_offline.py', 'content': TESTS},
        ],
        'measurement_plan': 'Retain 600 original Native ego frames, frame joins, and four camera streams; independently review driver attention from original evidence.',
        'mechanisms': ['20 Hz synchronous 30-second source capture',
                       'four original source cameras',
                       'source-derived driving cues with no attention inference'],
        'recording_description': {
            'channels': [{'name': 'driving_cues', 'unit': 'structured',
                          'sampling_rate_hz': 20,
                          'method': 'derive from original Native trace and synchronized source cameras',
                          'time_window': '600 frames'}],
            'limitations': ['Vehicle motion alone does not establish driver attention.']},
        'static_checks': ['exact reference identity', '600 frames',
                          'four cameras', 'no invented attention verdict'],
        'status': 'draft_cpu_offline_only',
        'termination_rules': ['600 synchronized Native frames or explicit failure'],
    }
    source = ROOT / 'draft-primary' / 'reference' / 'primary' / 'construction.json'
    write(source, construction)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {
        'assignment_id': ROOT.name,
        'format': 'worker-unselected-draft-construction-manifest-v1',
        'status': 'draft_cpu_offline_only',
        'cases': [{'case_id': CASE, 'kind': 'draft_not_selected',
                   'construction': str(source.relative_to(ROOT)),
                   'construction_sha256': digest,
                   'candidate_risk': {
                       'status': 'physical',
                       'reason': 'Driver attention requires original Native evidence and independent review.'}}],
    }
    write(ROOT / 'draft-primary-manifest.json', manifest)
    print(json.dumps({'case_id': CASE, 'construction_sha256': digest,
                      'source': str(source.relative_to(ROOT))}))


if __name__ == '__main__':
    main()
