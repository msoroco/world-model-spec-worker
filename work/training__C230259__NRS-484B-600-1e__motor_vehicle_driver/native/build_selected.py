"""Bind the three speed attempts to distinct inline Native constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C230259__NRS-484B-600-1e__motor_vehicle_driver'
TARGETS = {'probe_01': 75.0, 'probe_02': 80.0, 'probe_03': 85.0}


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def main():
    source = HERE/'selected_primary'
    entries = []
    for probe, target in TARGETS.items():
        case = AID + '__' + probe
        bundle = HERE/probe
        bundle.mkdir(exist_ok=True)
        (bundle/'tests').mkdir(exist_ok=True)
        config = json.loads((source/'config.json').read_text())
        config['case_id'] = case
        config['selected_case_id'] = case
        config['supported_case_ids'] = [AID+'__'+name for name in TARGETS]
        config['requested_speed_mph'] = target
        config['recording_description'] = {'channels': [
            {'name': name, 'unit': unit, 'method': method,
             'reference_frame': 'authored two-lane 1,800 m corridor',
             'sampling_rate_hz': 20, 'time_window': '600 frames / 30 s',
             'uncertainty': '50 ms Native sampling; physical source review pending'}
            for name, unit, method in (
                ('kin.velocity', 'm/s', 'three-axis post-tick Native vehicle velocity'),
                ('kin.speed', 'mph', 'norm of original Native velocity divided by 0.44704'),
                ('ru.subject', 'identifier', 'Native actor ID and reviewed vehicle identity'))],
            'context_inputs': [],
            'limitations': ['Controller request is not measured speed',
                            'CPU diagnostics do not establish physical speed or pixels']}
        config['cameras'] = [{'name': name, 'width': width, 'height': height,
                              'pose_strategy': 'ego_attached' if name == 'driver_reference' else 'surveyed_world',
                              'fov_deg': 85} for name, width, height in
                             (('overview', 1920, 1080), ('approach', 1280, 720),
                              ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))]
        (bundle/'runner.py').write_text((HERE/'standard_runner.py').read_text())
        (bundle/'road.py').write_text((HERE/'road.py').read_text())
        (bundle/'speed_measure.py').write_text((HERE/'measure_absolute_speed.py').read_text())
        (bundle/'finalize.py').write_text((HERE/'finalize.py').read_text())
        write(bundle/'config.json', config)
        (bundle/'tests/test_bundle.py').write_text('''import json
import unittest
from pathlib import Path
import road
import runner

class BundleTest(unittest.TestCase):
    def test_corridor_and_exact_case(self):
        self.assertEqual(road.check()['clear_corridor_m'], 1800.0)
        self.assertTrue(runner.check()['passed'])
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(config['selected_case_id'], config['case_id'])
        self.assertIn(config['requested_speed_mph'], (75.0, 80.0, 85.0))

    def test_missing_case_rejected(self):
        self.assertNotIn('probe_04', runner.TARGETS_MPH)
''')
        names = ('runner.py', 'road.py', 'speed_measure.py', 'finalize.py',
                 'config.json', 'tests/test_bundle.py')
        files = [{'path': name, 'content': (bundle/name).read_text()} for name in names]
        construction = {'format': 'worker-construction', 'assignment_id': AID,
                        'case_id': case, 'cell_id': 'C230259', 'law_id': 'NRS-484B-600-1e',
                        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
                        'measurement_plan': {'method': 'saved three-axis Native velocity and actor identity',
                                             'boundary_mph': 80.0, 'requested_speed_mph': target,
                                             'legal_tolerance_claimed': False},
                        'static_checks': ['two distinct vehicles', '1800 m two-lane route',
                                          '20 Hz synchronized four-view capture'],
                        'termination_rules': ['600 original frames', 'abort if ego leaves surveyed lane',
                                              'abort on camera frame mismatch'],
                        'mechanisms': ['generated OpenDRIVE corridor', 'separate other-vehicle actor',
                                       'Native velocity feedback controller'],
                        'recording_description': json.loads((bundle/'config.json').read_text())['recording_description'],
                        'files': files}
        path = HERE/f'{probe}-construction.json'
        write(path, construction)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({'case_id': case, 'construction': path.name,
                        'construction_sha256': digest,
                        'candidate_risk': {'status': 'physical' if probe == 'probe_03' else 'none',
                                           'reason': 'Requested speed may not be achieved on a reviewed clear route' if probe == 'probe_03' else 'Lower speed attempt has no identified additional construction risk'},
                        'candidates': []})
    manifest = {'assignment_id': AID, 'cases': entries}
    write(HERE/'selected-offline-manifest.json', manifest)
    print(json.dumps({'constructions': {entry['case_id']: entry['construction_sha256'] for entry in entries}}, sort_keys=True))


if __name__ == '__main__':
    main()
