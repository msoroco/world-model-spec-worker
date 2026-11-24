"""Bind exact current-v2 primary speed construction drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = (('probe_1', 'slow'), ('probe_2', 'at_default'), ('probe_3', 'fast'))
CAMERAS = ('overview', 'ego_front', 'roadside_sign', 'rear')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial_native_draft', 'cases': []}
    for suffix, speed_case in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        description = {'channels': [
            {'name': name, 'unit': unit, 'sampling_rate_hz': 20,
             'method': method, 'time_window': '600 original frames',
             'reference_frame': 'surveyed Native road and original Native frame',
             'uncertainty': '50 ms sampling; street and sign authority unverified'}
            for name, unit, method in (
                ('kin.speed', 'm/s', 'original Native velocity vector magnitude'),
                ('dev.speed_limit_sign', 'structured', 'original sign survey and roadside RGB source'),
                ('dev.governs', 'structured', 'source-hashed sign interval and route position'),
                ('st.roadway', 'structured', 'authored road and Native waypoint readback'),
                ('rel.occupies', 'structured', 'original Native actor position and road waypoint'))],
            'limitations': ['Public-street and posted-sign authority need independent original source review']}
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': [ASSIGNMENT + '__' + s for s, _ in CASES],
                  'candidate_id': 'primary', 'law_id': 'LVMC-11-16-060',
                  'cell_id': 'C179819', 'actor': 'motor_vehicle_driver',
                  'speed_case': speed_case, 'rate_hz': 20, 'duration_s': 30,
                  'required_atoms': [], 'source_packets': [], 'case': {'case_id': case_id},
                  'cameras': [{'name': name, 'width': 640, 'height': 360} for name in CAMERAS],
                  'recording_description': description, 'status': 'cpu_draft_sign_authority_unverified'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'controller.py',
                              'measure_speed.py', 'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal = {'case_id': case_id, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': description,
                    'measurement_plan': {'entrypoint': 'measure_speed.py',
                        'required_sources': ['road.xodr', 'sign-survey.json',
                                             'actor-poses.jsonl', 'video_frames.jsonl']},
                    'static_checks': ['800 m paved road', 'Native roadway readback',
                                      '600 frames at 20 Hz', 'four retained RGB source cameras'],
                    'termination_rules': ['600 frames', 'destroy owned actors and restore world'],
                    'mechanisms': ['same roadway and controller; requested speed varies'],
                    'status': 'partial_native_draft_authority_unverified'}
        path = HERE / 'draft-exact' / suffix / 'primary' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Native speed tracking and public sign governance require original review'},
            'candidates': [], 'measurement_procedure': {'entrypoint': 'measure_speed.py'},
            'preparation_status': 'incomplete'})
    (HERE / 'draft-execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({c['case_id']: c['construction_sha256'] for c in manifest['cases']}))


if __name__ == '__main__':
    main()
