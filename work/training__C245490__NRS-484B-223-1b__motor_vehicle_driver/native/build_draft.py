"""Build one unselected exact 30-second Native construction for CPU review."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
CASE = PACKAGE.name + '__signal_before_draft'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    config = json.loads((HERE / 'draft_config_template.json').read_text())
    config.update(case_id=CASE, selected_case_id=CASE, cell_id='C245490',
                  law_id='NRS-484B-223-1b', signal_start_frame=100,
                  target_vehicle_ahead_m=30.0)
    config['cameras'][2]['name'] = 'target_lane'
    config['control_phases'] = [
        {'name': 'approach', 'first_frame': 0, 'last_frame': 179,
         'throttle': 0.22, 'steer': 0.0, 'brake': 0.0},
        {'name': 'lane_change_left', 'first_frame': 180, 'last_frame': 229,
         'throttle': 0.18, 'steer': -0.08, 'brake': 0.0},
        {'name': 'lane_change_countersteer', 'first_frame': 230, 'last_frame': 279,
         'throttle': 0.18, 'steer': 0.08, 'brake': 0.0},
        {'name': 'follow_target_lane', 'first_frame': 280, 'last_frame': 599,
         'throttle': 0.05, 'steer': 0.0, 'brake': 0.25},
    ]
    tests = '''import copy
import json
import unittest
from pathlib import Path
from runner import FRAMES, RATE, check, phase_at

class DraftConstruction(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_window_signal_and_source_views(self):
        result = check(self.config)
        self.assertEqual((result['frames'], result['rate_hz']), (600, 20))
        self.assertEqual(len(result['camera_views']), 4)
        self.assertLess(self.config['signal_start_frame'],
                        self.config['control_phases'][1]['first_frame'])
        self.assertEqual(len([phase_at(self.config, i) for i in range(FRAMES)]), 600)
        self.assertIsNone(result['legal_verdict'])

    def test_reject_short_schedule(self):
        bad = copy.deepcopy(self.config)
        bad['control_phases'][-1]['last_frame'] = 598
        with self.assertRaises(ValueError):
            check(bad)

    def test_reject_missing_camera(self):
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaises(ValueError):
            check(bad)

    def test_reject_invented_verdict(self):
        bad = copy.deepcopy(self.config)
        bad['legal_verdict'] = 'lawful'
        with self.assertRaises(ValueError):
            check(bad)
'''
    runner = (HERE / 'draft_runner.py').read_text()
    proposal = {
        'case_id': CASE, 'law_id': 'NRS-484B-223-1b', 'cell_id': 'C245490',
        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
        'files': [
            {'path': 'runner.py', 'content': runner},
            {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
            {'path': 'tests/test_draft.py', 'content': tests},
        ],
        'measurement_plan': '600 original Native rows and four 20 Hz source cameras; compare signal onset to occupied-lane body departure and measured target-lane gap.',
        'mechanisms': ['synchronous Native capture', 'turn-indicator request',
                       'same-direction target-lane vehicle', 'source-hashed geometry and motion'],
        'recording_description': {'channels': [
            {'name': 'signal_lane_gap_sources', 'unit': 'structured',
             'sampling_rate_hz': 20, 'time_window': '600 frames',
             'method': 'measure retained original Native rows and four videos'}],
            'limitations': ['A requested signal does not prove observed indicator pixels.',
                            'Gap does not prove driver ascertainment or legal safety.']},
        'static_checks': ['exact case', '600 frames', 'four cameras',
                          'continuous control schedule', 'no legal verdict'],
        'status': 'draft_cpu_offline_only',
        'termination_rules': ['600 source frames or explicit capture failure'],
    }
    directory = HERE / 'draft-primary'
    directory.mkdir(exist_ok=True)
    construction = directory / 'construction.json'
    construction.write_text(json.dumps(proposal, indent=2) + '\n')
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': PACKAGE.name, 'status': 'draft_not_selected',
                'cases': [{'case_id': CASE, 'construction': 'draft-primary/construction.json',
                           'construction_sha256': sha(construction), 'candidates': [],
                           'candidate_risk': {'status': 'physical',
                               'reason': 'Native map lane alignment and target gap require original capture review.'}}],
                'original_native_observed': False, 'delivery_ready': False}
    path = HERE / 'draft-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'construction_sha256': sha(construction),
                      'manifest_sha256': sha(path)}, indent=2))


if __name__ == '__main__':
    main()
