"""Build exact, source-hashed paired Native CPU drafts without promoting readiness."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SIDES = (('controlled_1', 'right'), ('controlled_2', 'left'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    entries = []
    for suffix, side in SIDES:
        case = ASSIGNMENT + '__' + suffix
        config = {
            'case_id': case, 'selected_case_id': case, 'supported_case_ids': [case],
            'candidate_id': 'primary', 'law_id': 'NRS-484B-493', 'cell_id': 'C135709',
            'actor': 'motor_vehicle_driver', 'parking_side': side,
            'rate_hz': 20, 'duration_s': 30, 'required_atoms': [], 'source_packets': [],
            'case': {'case_id': case},
            'cameras': [{'name': name, 'width': 1280, 'height': 720} for name in
                        ('overview', 'sign_approach', 'sign_face', 'parking_side')],
            'recording_description': {'channels': [
                {'name': 'vehicle_footprint', 'unit': 'structured', 'sampling_rate_hz': 20,
                 'method': 'original Native bounding box and transform', 'time_window': '600 frames',
                 'reference_frame': 'directed street centerline', 'uncertainty': '50 ms frame interval'},
                {'name': 'notice_and_street_context', 'unit': 'structured', 'sampling_rate_hz': 20,
                 'method': 'OpenDRIVE readback plus separately sourced official and one-way designation',
                 'time_window': '600 frames', 'reference_frame': 'governed street',
                 'uncertainty': 'legal authority and physical pixels unverified'}],
                'limitations': ['OpenDRIVE signal does not establish official notice authority',
                                'one-way legal designation requires independent source',
                                'standing/parking purpose requires independent source review']},
            'status': 'partial_cpu_draft',
        }
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'tests/test_native.py')]
        files.append({'path': 'one_way_saved_measure.py',
                      'content': (HERE / 'one_way_saved_measure.py').read_text()})
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {
            'case_id': case, 'law_id': config['law_id'], 'cell_id': config['cell_id'],
            'actor': config['actor'], 'entrypoint': 'runner.py', 'files': files,
            'recording_description': config['recording_description'],
            'measurement_plan': {'entrypoint': 'one_way_saved_measure.py',
                                 'required_sources': ['vehicle-pose.jsonl', 'road-context.json',
                                                      'road.xodr', 'video_frames.jsonl'],
                                 'source_review_required': True},
            'static_checks': ['survey-gated 120m one-way draft road',
                              'paired curb shoulder lanes', 'four cameras and 600 original frames'],
            'termination_rules': ['600 original frames', 'restore world and destroy owned actors'],
            'mechanisms': ['Native original vehicle motion toward ' + side + ' curb',
                           'official notice and one-way legal designations remain unverified'],
            'status': 'partial_native_execution_cpu_checked_physical_unverified',
        }
        path = HERE / 'draft-one-way' / suffix / 'primary' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'case_id': case, 'kind': 'delivery',
                        'construction': str(path.relative_to(HERE)),
                        'construction_sha256': sha(path),
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Sign pixels, curb footprint and stopping motion require Native review'},
                        'candidates': [], 'delivery_readiness': 'incomplete'})
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial', 'cases': entries}
    (HERE / 'draft-one-way-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': [{'case_id': e['case_id'], 'construction_sha256': e['construction_sha256']}
                                for e in entries], 'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}))


if __name__ == '__main__':
    main()
