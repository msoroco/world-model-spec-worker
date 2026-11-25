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
                  'cameras': [{'name': name, 'width': width, 'height': height,
                               'fov_deg': 85, 'pose_strategy': pose}
                              for name, width, height, pose in (
                                  ('overview', 1920, 1080, 'overhead all-space context'),
                                  ('approach', 1280, 720, 'posted City space and subject approach'),
                                  ('reference_corner', 1280, 720, 'other curb space and boundary'),
                                  ('driver_reference', 1280, 720, 'subject body and parking pose'))],
                  'recording_description': {'channels': [
                      {'name': 'parking-inventory.json', 'unit': 'structured',
                       'sampling_rate_hz': 20, 'method': 'per-frame join to retained authored geometry and original Native lane survey with authority fields unresolved',
                       'time_window': '600 captured frames', 'reference_frame': 'authored one-way street',
                       'uncertainty': 'City Council designation, posting and City-street jurisdiction require independent records'},
                      {'name': 'vehicle-poses.jsonl', 'unit': 'structured',
                       'sampling_rate_hz': 20, 'method': 'original Native actor transform, velocity and bounding box',
                       'time_window': '600 frames', 'reference_frame': 'authored one-way street',
                       'uncertainty': '50 ms sampling; vehicle legal classification requires independent source'},
                      {'name': 'video_frames.jsonl', 'unit': 'structured',
                       'sampling_rate_hz': 20, 'method': 'original four-view Native camera frame join',
                       'time_window': '600 frames', 'reference_frame': 'original Native frame',
                       'uncertainty': 'pixel visibility unverified until actual capture'},
                      {'name': 'subject_vehicle_pose_and_speed', 'unit': 'structured',
                       'sampling_rate_hz': 20, 'method': 'original Native vehicle transform and velocity',
                       'time_window': '600 frames', 'reference_frame': 'authored one-way street',
                       'uncertainty': '50 ms sampling'},
                      {'name': 'space_geometry', 'unit': 'polygon',
                       'sampling_rate_hz': 20, 'method': 'authored OpenDRIVE and Native lane readback',
                       'time_window': '600 frames', 'reference_frame': 'authored one-way street',
                       'uncertainty': 'pending Native readback'}],
                      'context_inputs': [],
                      'limitations': ['City Council designation, due posting, City-street status and subject vehicle classification need independent source records; geometry and blueprint cannot prove them']},
                  'status': 'cpu_draft_not_delivery_prepared'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'tests/test_native.py',
                              'tests/test_source_review.py', 'tests/test_finalize.py')]
        files.append({'path': 'parking_measure.py', 'content': (HERE / 'parking_measure.py').read_text()})
        files.append({'path': 'source_review.py', 'content': (HERE / 'source_review.py').read_text()})
        files.append({'path': 'finalize.py', 'content': (HERE / 'native' / 'finalize.py').read_text()})
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal = {'case_id': case_id, 'law_id': config['law_id'], 'cell_id': config['cell_id'],
                    'actor': config['actor'], 'entrypoint': 'runner.py', 'files': files,
                    'recording_description': config['recording_description'],
                    'measurement_plan': {'entrypoint': 'finalize.py',
                                         'required_sources': ['vehicle-poses.jsonl', 'parking-inventory.json',
                                                              'review.json', 'video_frames.jsonl',
                                                              'trace.jsonl', 'capture/evidence.jsonl'],
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
