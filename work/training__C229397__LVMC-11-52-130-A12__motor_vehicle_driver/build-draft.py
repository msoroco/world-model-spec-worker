"""Build two exact primary crosswalk-parking CPU constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = (('controlled_1', -14.0), ('controlled_2', -5.0))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial', 'cases': []}
    case_ids = [ASSIGNMENT + '__' + suffix for suffix, _ in CASES]
    for suffix, target_x in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': case_ids, 'candidate_id': 'primary',
                  'law_id': 'LVMC-11-52-130-A12', 'cell_id': 'C229397',
                  'actor': 'motor_vehicle_driver', 'crosswalk_case': suffix,
                  'target_center_x_m': target_x, 'rate_hz': 20, 'duration_s': 30,
                  'required_atoms': [], 'source_packets': [], 'case': {'case_id': case_id},
                  'cameras': [{'name': name, 'width': 1280, 'height': 720}
                              for name in ('overview', 'crosswalk', 'parking_approach', 'subject_side')],
                  'recording_description': {'channels': [
                      {'name': 'subject_vehicle_pose_and_extent', 'unit': 'structured',
                       'sampling_rate_hz': 20, 'method': 'original Native transform, velocity and bounding box',
                       'time_window': '600 frames', 'reference_frame': 'authored road and crosswalk',
                       'uncertainty': '50 ms sampling'},
                      {'name': 'crosswalk_extent', 'unit': 'polygon',
                       'sampling_rate_hz': 20, 'method': 'OpenDRIVE object proposal plus original marking review',
                       'time_window': '600 frames', 'reference_frame': 'authored road and crosswalk',
                       'uncertainty': 'pending Native marking verification'}],
                      'limitations': ['Actual marked paint, jurisdiction, traffic conflict, law and officer/device directions need independent sources']},
                  'status': 'cpu_draft_not_delivery_prepared'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'tests/test_native.py')]
        files.append({'path': 'crosswalk_measure.py', 'content': (HERE / 'crosswalk_measure.py').read_text()})
        files.append({'path': 'finalize_crosswalk.py', 'content': (HERE / 'finalize_crosswalk.py').read_text()})
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal = {'case_id': case_id, 'law_id': config['law_id'], 'cell_id': config['cell_id'],
                    'actor': config['actor'], 'entrypoint': 'runner.py', 'files': files,
                    'recording_description': config['recording_description'],
                    'measurement_plan': {'entrypoint': 'finalize_crosswalk.py',
                                         'required_sources': ['vehicle-poses.jsonl', 'crosswalk-inventory.json',
                                                              'video_frames.jsonl'],
                                         'status': 'source_bound_cpu_draft'},
                    'static_checks': ['100 m road with parking lane', 'crosswalk object proposal',
                                      'two controlled parking centers', 'four cameras', '600 frames at 20 Hz'],
                    'termination_rules': ['600 original frames', 'restore world and destroy owned actors'],
                    'mechanisms': ['subject parks before marked crosswalk proposal',
                                   'exact position compared by measured body and center distances',
                                   'actual marking and exceptions independently reviewed'],
                    'status': 'partial_native_execution_cpu_checked_physical_unverified'}
        path = HERE / 'draft-crosswalk' / suffix / 'primary' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
                                  'construction': str(path.relative_to(HERE)),
                                  'construction_sha256': sha(path),
                                  'candidate_risk': {'status': 'physical',
                                                     'reason': 'painted marking and park position require original Native review'},
                                  'candidates': [],
                                  'measurement_procedure': {'entrypoint': 'finalize_crosswalk.py'},
                                  'delivery_readiness': 'incomplete'})
    (HERE / 'draft-crosswalk-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': {c['case_id']: c['construction_sha256'] for c in manifest['cases']},
                      'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}, sort_keys=True))


if __name__ == '__main__':
    main()
