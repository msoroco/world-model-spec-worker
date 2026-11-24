"""Build four exact, unselected NRS 484B.497 Native construction drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = (('witness_1', True), ('witness_2', False),
         ('exception_1_1', False), ('exception_1_2', True))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assignment = ROOT / 'inputs' / ASSIGNMENT / 'assignment.json'
    plan = HERE / 'case-plan.json'
    source = json.loads(assignment.read_text())
    assert source['law']['text'] == json.loads(plan.read_text())['source_law']['text']
    entries = []
    for suffix, permission in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        config = {
            'case_id': case_id, 'selected_case_id': case_id,
            'supported_case_ids': [case_id], 'candidate_id': 'primary',
            'law_id': 'NRS-484B-497', 'cell_id': 'C150129',
            'actor': 'motor_vehicle_driver',
            'assignment_sha256': sha(assignment), 'case_plan_sha256': sha(plan),
            'permission_device_requested': permission,
            'parking_side': 'left', 'rate_hz': 20, 'duration_s': 30,
            'required_atoms': [], 'source_packets': [], 'case': {'case_id': case_id},
            'cameras': [{'name': name, 'width': 1280, 'height': 720} for name in
                        ('overview', 'sign_approach', 'sign_face', 'parking_side')],
            'recording_description': {
                'channels': [
                    {'name': 'vehicle_footprint', 'unit': 'structured',
                     'sampling_rate_hz': 20, 'method': 'original Native bounding box and transform',
                     'time_window': '600 frames', 'reference_frame': 'directed road centerline',
                     'uncertainty': '50 ms sampling'},
                    {'name': 'device_and_road_context', 'unit': 'structured',
                     'sampling_rate_hz': 20,
                     'method': 'OpenDRIVE readback plus separately sourced official permission and one-way designation',
                     'time_window': '600 frames', 'reference_frame': 'governed road',
                     'uncertainty': 'authority and image review pending'}],
                'limitations': ['map signal does not prove official status or erection',
                                'one-way legal designation needs independent source',
                                'standing/parking purpose and actual pixels need independent review']},
            'status': 'partial_cpu_draft',
        }
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'tests/test_native.py')]
        files.append({'path': 'parking_saved_measure.py',
                      'content': (HERE / 'parking_saved_measure.py').read_text()})
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {
            'case_id': case_id, 'law_id': 'NRS-484B-497', 'cell_id': 'C150129',
            'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py', 'files': files,
            'recording_description': config['recording_description'],
            'measurement_plan': {'entrypoint': 'parking_saved_measure.py',
                                 'required_sources': ['vehicle-pose.jsonl',
                                                       'video_frames.jsonl', 'road.xodr',
                                                       'road-context.json'],
                                 'source_review_required': True},
            'static_checks': ['120 m laned one-way road request',
                              'permission device present or absent by case',
                              'four 1280x720 cameras at 20 Hz for 600 frames'],
            'termination_rules': ['600 original frames',
                                  'restore Native world and destroy owned actors'],
            'status': 'partial_native_execution_cpu_checked_physical_unverified',
        }
        path = HERE / 'draft-permission' / suffix / 'primary' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': str(path.relative_to(HERE)),
                        'construction_sha256': sha(path),
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Sign pixels, left curb footprint and stopping motion require Native review'},
                        'candidates': [], 'delivery_readiness': 'incomplete'})
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': ASSIGNMENT, 'input_sha256': sha(assignment),
                'case_plan_sha256': sha(plan), 'status': 'partial', 'cases': entries}
    destination = HERE / 'draft-permission-manifest.json'
    destination.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(destination),
                      'cases': {entry['case_id']: entry['construction_sha256']
                                for entry in entries}}))


if __name__ == '__main__':
    main()
