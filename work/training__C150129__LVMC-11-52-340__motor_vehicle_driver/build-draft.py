"""Materialize two exact, source-bound municipal parking CPU constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = (('controlled_1', 'outside_city_space'), ('controlled_2', 'inside_city_space'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial', 'cases': []}
    case_ids = [ASSIGNMENT + '__' + suffix for suffix, _ in CASES]
    for suffix, parking_case in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': case_ids, 'candidate_id': 'primary',
                  'law_id': 'LVMC-11-52-340', 'cell_id': 'C150129',
                  'actor': 'motor_vehicle_driver', 'parking_case': parking_case,
                  'rate_hz': 20, 'duration_s': 30, 'required_atoms': [],
                  'source_packets': [], 'case': {'case_id': case_id},
                  'cameras': [{'name': name, 'width': 1280, 'height': 720}
                              for name in ('overview', 'city_space', 'other_space', 'subject_side')],
                  'recording_description': {'channels': [
                      {'name': 'subject_vehicle_pose_and_speed', 'unit': 'structured',
                       'sampling_rate_hz': 20, 'method': 'original Native vehicle transform and velocity',
                       'time_window': '600 frames', 'reference_frame': 'authored one-way street',
                       'uncertainty': '50 ms sampling'},
                      {'name': 'space_geometry', 'unit': 'polygon',
                       'sampling_rate_hz': 20, 'method': 'authored OpenDRIVE and Native lane readback',
                       'time_window': '600 frames', 'reference_frame': 'authored one-way street',
                       'uncertainty': 'pending Native readback'}],
                      'limitations': ['City Council designation, due posting, City-street status and subject vehicle classification need independent source records; geometry and blueprint cannot prove them']},
                  'status': 'cpu_draft_not_delivery_prepared'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'tests/test_native.py')]
        files.append({'path': 'parking_measure.py', 'content': (HERE / 'parking_measure.py').read_text()})
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal = {'case_id': case_id, 'law_id': config['law_id'], 'cell_id': config['cell_id'],
                    'actor': config['actor'], 'entrypoint': 'runner.py', 'files': files,
                    'recording_description': config['recording_description'],
                    'measurement_plan': {'entrypoint': 'parking_measure.py',
                                         'required_sources': ['vehicle-poses.jsonl', 'parking-inventory.json',
                                                              'video_frames.jsonl'],
                                         'status': 'source_bound_cpu_draft'},
                    'static_checks': ['one-way OpenDRIVE driving and parking lanes',
                                      'two distinct curb segments', 'four source cameras',
                                      '600 frames at 20 Hz'],
                    'termination_rules': ['600 original frames', 'restore world and destroy owned actors'],
                    'mechanisms': ['non-City subject drives toward ' + parking_case,
                                   'original pose and speed measured each frame',
                                   'independent designation and posting source required'],
                    'status': 'partial_native_execution_cpu_checked_physical_unverified'}
        path = HERE / 'draft-parking' / suffix / 'primary' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
                                  'construction': str(path.relative_to(HERE)),
                                  'construction_sha256': sha(path),
                                  'candidate_risk': {'status': 'physical',
                                                     'reason': 'parking dynamics and sign legibility require original Native review'},
                                  'candidates': [],
                                  'measurement_procedure': {'entrypoint': 'parking_measure.py'},
                                  'delivery_readiness': 'incomplete'})
    (HERE / 'draft-parking-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': {c['case_id']: c['construction_sha256'] for c in manifest['cases']},
                      'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}, sort_keys=True))


if __name__ == '__main__':
    main()
