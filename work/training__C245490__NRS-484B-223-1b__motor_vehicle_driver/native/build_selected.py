"""Materialize the four controlled C245490 Native constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
CASES = ('signal_before_safe', 'signal_after_safe',
         'signal_before_unsafe', 'signal_before_no_check')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def build():
    template = json.loads((HERE / 'draft_config_template.json').read_text())
    template.update(cell_id='C245490', law_id='NRS-484B-223-1b',
                    actor='motor_vehicle_driver', duration_s=30, rate_hz=20,
                    target_vehicle_ahead_m=35.0, check_frame=170,
                    legal_verdict=None, required_atoms=[])
    template['cameras'][2]['name'] = 'reference_corner'
    template['control_phases'] = [
        {'name': 'approach', 'first_frame': 0, 'last_frame': 179,
         'throttle': 0.22, 'steer': 0.0, 'brake': 0.0},
        {'name': 'lane_change_left', 'first_frame': 180, 'last_frame': 229,
         'throttle': 0.18, 'steer': -0.08, 'brake': 0.0},
        {'name': 'lane_change_countersteer', 'first_frame': 230, 'last_frame': 279,
         'throttle': 0.18, 'steer': 0.08, 'brake': 0.0},
        {'name': 'follow_target_lane', 'first_frame': 280, 'last_frame': 599,
         'throttle': 0.05, 'steer': 0.0, 'brake': 0.25},
    ]
    template['supported_case_ids'] = [PACKAGE.name + '__' + suffix for suffix in CASES]
    tests = '''import json
import unittest
from pathlib import Path
from runner import FRAMES, RATE, check, phase_at

class SelectedConstruction(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_window_and_source_views(self):
        result = check(self.config)
        self.assertEqual((result['frames'], result['rate_hz']), (600, 20))
        self.assertEqual(len(result['camera_views']), 4)
        self.assertEqual(len([phase_at(self.config, i) for i in range(FRAMES)]), 600)
        self.assertLess(self.config['check_frame'], 180)
        self.assertIsNone(result['legal_verdict'])

    def test_exact_case_controls(self):
        suffix = self.config['case_id'].split('__')[-1]
        self.assertEqual(self.config['signal_start_frame'] < 180,
                         suffix != 'signal_after_safe')
        self.assertEqual(self.config['target_vehicle_behind_m'] < 12,
                         suffix == 'signal_before_unsafe')
        self.assertEqual(self.config['check_action'] == 'skipped',
                         suffix == 'signal_before_no_check')
'''
    entries = []
    for suffix in CASES:
        case_id = PACKAGE.name + '__' + suffix
        config = dict(template, case_id=case_id, selected_case_id=case_id,
                      candidate_id='primary',
                      signal_start_frame=260 if suffix == 'signal_after_safe' else 100,
                      target_vehicle_behind_m=8.0 if suffix == 'signal_before_unsafe' else 30.0,
                      check_action='skipped' if suffix == 'signal_before_no_check' else 'evaluated')
        description = {
            'channels': [{'name': name, 'unit': 'structured',
                          'sampling_rate_hz': 20, 'time_window': '600 frames',
                          'method': 'original Native source and four camera frames'}
                         for name in ('ego_lane', 'front_actor', 'rear_actor',
                                      'observed_indicator', 'controller_check')],
            'limitations': ['Controller gap rule is engineering, not statutory.',
                            'A controller check is not proof of a human mental state.',
                            'Pixels and physical completion require later local review.'],
        }
        config['recording_description'] = description
        proposal = {
            'case_id': case_id, 'cell_id': 'C245490', 'law_id': 'NRS-484B-223-1b',
            'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
            'files': [
                {'path': 'runner.py', 'content': (HERE / 'draft_runner.py').read_text()},
                {'path': 'measure_lane_change.py', 'content': (HERE / 'measure_lane_change.py').read_text()},
                {'path': 'finalize_lane_change.py', 'content': (HERE / 'finalize_lane_change.py').read_text()},
                {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                {'path': 'tests/test_selected.py', 'content': tests},
            ],
            'measurement_plan': {
                'method': '600 original same-tick Native ego, front and rear actor, observed lamp and independent controller check rows',
                'output': 'source-hashed signal/departure/gap/check order; no legal verdict',
                'legal_cutoff_defined': False,
            },
            'mechanisms': ['two same-direction marked lanes',
                           'source-recorded occupied-lane body departure',
                           'separate target-lane front and rear actors',
                           'source-recorded check action and decision',
                           'requested and observed signal kept separate',
                           'four synchronized RGB cameras'],
            'recording_description': description,
            'static_checks': ['exact frozen cell, law and role', '600 frames at 20 Hz',
                              'four cameras', 'front and rear actor construction',
                              'distinct signal, gap and check variables'],
            'status': 'selected_native_cpu_draft_not_delivery_prepared',
            'termination_rules': ['600 synchronized frames or explicit capture failure',
                                  'stop sensors, encoders and restore world before sealing'],
        }
        path = HERE / 'selected' / suffix / 'construction.json'
        write(path, proposal)
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': str(path.relative_to(PACKAGE)),
                        'construction_sha256': sha(path),
                        'candidate_risk': {'status': 'none',
                                           'reason': 'No original Native motion/camera failure measured; primary capture first.'},
                        'candidates': [], 'delivery_readiness': 'incomplete'})
    write(PACKAGE / 'selected-draft-manifest.json',
          {'format': 'worker-selected-cpu-draft-manifest-v1',
           'assignment_id': PACKAGE.name, 'status': 'partial', 'cases': entries,
           'physical_acceptance_claimed': False})
    return entries


if __name__ == '__main__':
    print(json.dumps({'constructions': [x['construction_sha256'] for x in build()]}))
