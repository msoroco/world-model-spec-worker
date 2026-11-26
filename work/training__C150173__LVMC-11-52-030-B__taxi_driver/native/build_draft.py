"""Build two unselected, exact 30-second taxi curb request bundles."""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from yellow_plan import check, measure_requested

PACKAGE = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
PREFIX = PACKAGE.name
CAMERAS = [
    {'name': 'overview', 'width': 1920, 'height': 1080, 'fps': 20,
     'fov_deg': 90, 'location_xyz_m': [20, -12, 35],
     'rotation_pyr_deg': [-45, 0, 135], 'pose_strategy': 'fixed yellow zone overhead'},
    {'name': 'approach', 'width': 1280, 'height': 720, 'fps': 20,
     'fov_deg': 85, 'location_xyz_m': [0, -20, 8],
     'rotation_pyr_deg': [-15, 0, 90], 'pose_strategy': 'fixed one-way approach'},
    {'name': 'reference_corner', 'width': 1280, 'height': 720, 'fps': 20,
     'fov_deg': 80, 'location_xyz_m': [14, 13, 8],
     'rotation_pyr_deg': [-15, 0, 225], 'pose_strategy': 'fixed curb and sign'},
    {'name': 'driver_reference', 'width': 1280, 'height': 720, 'fps': 20,
     'fov_deg': 85, 'location_xyz_m': [1, 0, 1.5],
     'rotation_pyr_deg': [0, 0, 0], 'pose_strategy': 'attached taxi forward'},
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def main():
    cases = []
    road = (HERE / 'yellow-road.xodr').read_text()
    for suffix, hour, purpose in (('probe_a', 10, 'waiting_for_passengers'),
                                  ('probe_b', 18, 'waiting_for_passengers'),
                                  ('probe_c', 10, 'loading_passengers'),
                                  ('probe_d', 10, 'unloading_passengers')):
        case_id = PREFIX + '__' + suffix
        start = datetime(2026, 11, 26, hour)
        config = {'case_id': case_id, 'cell_id': 'C150173',
                  'law_id': 'LVMC-11-52-030-B', 'actor': 'taxi_driver',
                  'duration_s': 30, 'rate_hz': 20, 'frames': 600,
                  'civil_start_local': start.isoformat(),
                  'timezone': 'America/Los_Angeles',
                  'taxi_blueprint_filter': 'vehicle.*',
                  'requested_purpose': purpose,
                  'sign_source_status': 'authored_proposal_unverified',
                  'ordinary_rules_outside_hours': 'unresolved',
                  'legal_verdict': None, 'cameras': CAMERAS,
                  'required_atoms': [], 'source_packets': []}
        check(config, road)
        rows = [{'video_frame': i, 'time_s': (i + 1) / 20,
                 'source_kind': 'authored_native_request',
                 'civil_time_local': (start + timedelta(seconds=(i + 1) / 20)).isoformat(timespec='milliseconds'),
                 'requested_taxi_role': 'taxi_unverified',
                 'requested_purpose': purpose,
                 'requested_stop_xy_m': [5.25, 10.0],
                 'requested_speed_mps': 0} for i in range(600)]
        expected = 600 if hour == 10 else 0
        if measure_requested(rows, config)['sign_active_request_frames'] != expected:
            raise ValueError('Controlled posted-hours contrast differs')
        track = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows)
        test = '''import json\nimport unittest\nfrom pathlib import Path\nfrom runner import offline_check\nfrom yellow_plan import check, read_requested\n\nclass TaxiYellowZone(unittest.TestCase):\n def test_exact_request(self):\n  r=offline_check(Path('.'))\n  self.assertEqual(r['frames'],600)\n  self.assertFalse(r['sign_authority_verified'])\n  self.assertEqual(r['request_measure']['requested_frames'],600)\n def test_missing_source(self):\n  config=json.loads(Path('config.json').read_text())\n  bad={**config,'sign_source_status':'verified_without_source'}\n  with self.assertRaises(ValueError):check(bad,Path('yellow-road.xodr').read_text())\n'''
        construction = {'case_id': case_id, 'cell_id': 'C150173',
                        'law_id': 'LVMC-11-52-030-B', 'actor': 'taxi_driver',
                        'entrypoint': 'runner.py',
                        'files': [{'path': name, 'content': (HERE / source).read_text()}
                                  for source, name in (('runner.py', 'runner.py'),
                                                       ('yellow_plan.py', 'yellow_plan.py'),
                                                       ('yellow-road.xodr', 'yellow-road.xodr'))] +
                                 [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                                  {'path': 'requested-track.jsonl', 'content': track},
                                  {'path': 'tests/test_offline.py', 'content': test}],
                        'recording_description': {
                            'duration_s': 30, 'rate_hz': 20,
                            'source_cameras': [camera['name'] for camera in CAMERAS],
                            'yellow_curb_and_sign_source_required': True,
                            'taxicab_identity_and_passenger_waiting_source_required': True,
                            'outside_hours_ordinary_rules_unresolved': True,
                            'legal_verdict': None},
                        'status': 'unselected_native_cpu_draft'}
        path = PACKAGE / 'native-draft' / suffix / 'construction.json'
        write(path, construction)
        cases.append({'case_id': case_id,
                      'construction': str(path.relative_to(PACKAGE)),
                      'construction_sha256': sha(path),
                      'requested_sign_active_frames': expected,
                      'status': 'unselected_native_cpu_draft'})
    write(PACKAGE / 'native-draft-manifest.json', {
        'format': 'c150173-unselected-native-draft-v1',
        'assignment_id': PREFIX, 'cases': cases,
        'comparison_variable': 'civil clock hour for waiting; waiting/loading/unloading purpose within hours',
        'fixed_conditions': ['taxi-role vehicle request', 'yellow curb and authored sign',
                             'passenger waiting request', 'taxi stop', 'four cameras',
                             '30 seconds at 20 Hz'],
        'original_native_observed': False, 'delivery_ready': False})


if __name__ == '__main__':
    main()
