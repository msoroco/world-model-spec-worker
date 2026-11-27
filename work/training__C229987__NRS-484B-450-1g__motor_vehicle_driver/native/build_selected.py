"""Build exact inline Native roadside-signal approach constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
AID = ROOT.name
TARGETS = {'25': 25.0, '30': 30.0, '35': 35.0}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def main():
    entries = []
    for suffix, feet in TARGETS.items():
        case = AID+'__'+suffix
        bundle = HERE/suffix
        bundle.mkdir(exist_ok=True)
        config = {
            'assignment_id': AID, 'case_id': case, 'selected_case_id': case,
            'supported_case_ids': [AID+'__'+key for key in TARGETS],
            'cell_id': 'C229987', 'law_id': 'NRS-484B-450-1g',
            'actor': 'motor_vehicle_driver', 'candidate_id': 'primary',
            'frozen_cell': {'layout': 'road', 'maneuver': 'stop_stand',
                            'control': 'traffic_light'},
            'required_atoms': [], 'source_packets': [], 'rate_hz': 20,
            'duration_s': 30, 'frames': 600, 'requested_front_gap_ft': feet,
            'physical_acceptance_claimed': False, 'legal_verdict': None,
            'cameras': [
                {'name': name, 'width': width, 'height': height,
                 'pose_strategy': 'ego_attached' if name == 'driver_reference' else 'surveyed_world',
                 'fov_deg': 85}
                for name, width, height in (
                    ('overview', 1920, 1080), ('approach', 1280, 720),
                    ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))],
        }
        channels = [
            ('ego_pose', 'm', 'original Native pose and four-corner body footprint'),
            ('stop_distance_on_signal_approach', 'm', 'footprint projection onto surveyed approach'),
            ('kin.speed', 'm/s', 'post-tick Native velocity norm'),
            ('drv.standing_or_parked', 'boolean proxy', 'per-frame low speed, cause separately reviewed'),
            ('dev.traffic_signal', 'identifier', 'Native signal actor and governed lane readback'),
            ('dev.position', 'm', 'Native roadside signal transform'),
            ('rel.centre_distance', 'm', 'vehicle centre projection to signal station'),
            ('drv.approaching', 'classification', 'front/rear approach-side geometry'),
            ('rel.occupies', 'm', 'front edge projection to signal station'),
            ('drv.forced_halt', 'review source', 'traffic conflict in original survey'),
            ('dev.human_direction', 'review source', 'officer direction in original survey'),
        ]
        description = {
            'channels': [{'name': name, 'unit': unit, 'method': method,
                          'reference_frame': 'authored roadside-signal approach, Native map readback',
                          'sampling_rate_hz': 20, 'time_window': '600 frames / 30 s',
                          'uncertainty': '50 ms sampling; 0.05 m synthetic geometry allowance is not legal tolerance'}
                         for name, unit, method in channels],
            'context_inputs': [],
            'limitations': ['Requested 25/30/35 ft controller settings are not observed distances',
                            'Signal official/highway status and every statutory exception require original source review',
                            'No legal, physical or pixel acceptance from CPU fixtures'],
        }
        config['recording_description'] = description
        write(bundle/'config.json', config)
        tests = bundle/'tests'
        tests.mkdir(exist_ok=True)
        (tests/'test_bundle.py').write_text('''import json
import unittest
from pathlib import Path
import road
import runner

class BundleTest(unittest.TestCase):
    def test_signal_actor_contract_and_exact_target(self):
        self.assertTrue(road.check()['signal_specified'])
        self.assertTrue(runner.check()['passed'])
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(config['selected_case_id'], config['case_id'])
        self.assertIn(config['requested_front_gap_ft'], (25.0, 30.0, 35.0))
        self.assertEqual(len(config['cameras']), 4)

    def test_missing_case_rejected(self):
        self.assertNotIn('40', runner.TARGETS_FT)
''')
        for name, source in [('runner.py', HERE/'runner.py'), ('road.py', HERE/'road.py'),
                             ('signal_approach.py', ROOT/'analysis/signal_approach.py'),
                             ('finalize.py', HERE/'finalize.py')]:
            (bundle/name).write_text(source.read_text())
        files = [{'path': name, 'content': (bundle/name).read_text()}
                 for name in ('runner.py', 'road.py', 'signal_approach.py',
                              'finalize.py', 'config.json', 'tests/test_bundle.py')]
        construction = {
            'format': 'worker-construction', 'assignment_id': AID,
            'case_id': case, 'cell_id': 'C229987', 'law_id': 'NRS-484B-450-1g',
            'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
            'measurement_plan': {'method': 'saved original Native footprint and roadside signal station',
                                 'requested_front_gap_ft': feet, 'statutory_boundary_ft': 30,
                                 'legal_tolerance_claimed': False},
            'static_checks': ['roadside signal XML and unique Native actor readback',
                              'governed approach lane and four-corner subject footprint',
                              '20 Hz synchronized four-view 600-frame capture'],
            'termination_rules': ['600 original frames', 'abort on wrong approach lane',
                                  'abort on absent/duplicate signal or camera frame mismatch'],
            'mechanisms': ['authored OpenDRIVE signal approach',
                           'Native traffic-light actor and governed lane check',
                           'pure requested position stopping controller',
                           'original context survey required before saved-only finalization'],
            'recording_description': description, 'files': files,
        }
        path = HERE/f'{suffix}-construction.json'
        write(path, construction)
        entries.append({'case_id': case, 'construction': path.name,
                        'construction_sha256': sha(path),
                        'candidate_risk': {'status': 'none',
                                           'reason': 'Original stopping position and official-signal status require source review; no distinct engineering fallback is yet justified.'},
                        'candidates': []})
    write(HERE/'selected-offline-manifest.json', {'assignment_id': AID, 'cases': entries})
    print(json.dumps({'constructions': {e['case_id']: e['construction_sha256']
                                         for e in entries}}, sort_keys=True))


if __name__ == '__main__':
    main()
