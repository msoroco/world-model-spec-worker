"""Bind exact current-v2 primary sidewalk-fixture construction drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = (('probe_1', 'outside'), ('probe_2', 'side_band'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial_native_draft', 'cases': []}
    for suffix, stop_case in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        description = {'channels': [
            {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': method, 'time_window': '600 original frames',
             'reference_frame': 'surveyed one-way street and original Native frame',
             'uncertainty': '50 ms sampling; sidewalk fixture identity unverified'}
            for name, method in (
                ('vehicle_footprint', 'original Native body vertices, pose and velocity'),
                ('sidewalk_fixture', 'authored bounds and original proxy actor readback'),
                ('camera_frame_join', 'four original RGB streams joined to Native frames'))],
            'limitations': ['Sidewalk elevator/chute identity, traffic conflict and officer/device direction need independent source review']}
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': [ASSIGNMENT + '__' + s for s, _ in CASES],
                  'candidate_id': 'primary', 'law_id': 'LVMC-11-52-130-A5',
                  'cell_id': 'C150668', 'actor': 'motor_vehicle_driver',
                  'stop_case': stop_case, 'rate_hz': 20, 'duration_s': 30,
                  'required_atoms': [], 'source_packets': [],
                  'case': {'case_id': case_id},
                  'cameras': [{'name': name, 'width': 640, 'height': 360}
                              for name in ('overview', 'ego_front', 'fixture_side', 'traffic_rear')],
                  'recording_description': description,
                  'status': 'cpu_draft_fixture_identity_unverified'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'stop_route.py',
                              'measure_fixture.py', 'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal = {'case_id': case_id, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': description,
                    'measurement_plan': {'entrypoint': 'measure_fixture.py',
                        'required_sources': ['road.xodr', 'fixture-inventory.json',
                                             'vehicle-poses.jsonl', 'video_frames.jsonl']},
                    'static_checks': ['160 m one-way street and sidewalk bounds',
                        'Native lane/fixture proxy survey', '600 frames at 20 Hz',
                        'four retained RGB source cameras'],
                    'termination_rules': ['600 frames', 'destroy owned actors and restore world'],
                    'mechanisms': ['same feedback stop policy; requested station varies'],
                    'status': 'partial_native_draft_physical_unverified'}
        path = HERE / 'draft-exact' / suffix / 'primary' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Native stop position, fixture identity and camera view require review'},
            'candidates': [], 'measurement_procedure': {'entrypoint': 'measure_fixture.py'},
            'preparation_status': 'incomplete'})
    (HERE / 'draft-execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({c['case_id']: c['construction_sha256'] for c in manifest['cases']}))


if __name__ == '__main__':
    main()
