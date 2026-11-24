"""Materialize exact primary inline constructions for current runtime offline proof."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = ('probe_1', 'probe_2')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial_native_draft', 'cases': []}
    for suffix in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        cameras = [{'name': name, 'width': 640, 'height': 360}
                   for name in ('overview', 'approach', 'person', 'driver_side')]
        description = {'channels': [
            {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': method, 'time_window': '600 original frames',
             'reference_frame': 'surveyed mountain road and original Native frame',
             'uncertainty': '50 ms sampling; physical marker appearance unverified'}
            for name, method in (
                ('vehicle_person_pose', 'original Native actor transform, velocity and bbox'),
                ('camera_frame_join', 'four original RGB source frames per Native frame'))],
            'limitations': ['White or red-tipped cane and blindness require independent source and pixel review']}
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': [ASSIGNMENT + '__' + s for s in CASES],
                  'candidate_id': 'primary', 'law_id': 'LVMC-11-30-140-B',
                  'cell_id': 'C129273', 'actor': 'motor_vehicle_driver',
                  'rate_hz': 20, 'duration_s': 30, 'required_atoms': [],
                  'source_packets': [], 'case': {'case_id': case_id},
                  'cameras': cameras, 'recording_description': description,
                  'status': 'cpu_draft_physical_marker_unverified'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal = {'case_id': case_id, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': description,
                    'measurement_plan': {'required_sources': ['road-survey.json',
                        'vehicle-person-poses.jsonl', 'video_frames.jsonl']},
                    'static_checks': ['240 m elevated road', 'Native lane survey',
                        '600 frames at 20 Hz', 'four retained RGB source cameras'],
                    'termination_rules': ['600 frames', 'destroy owned actors and restore world'],
                    'mechanisms': ['fixed pedestrian approach; driver stop policy varies'],
                    'status': 'partial_native_draft_physical_unverified'}
        path = HERE / 'draft-exact' / suffix / 'primary' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Native stop dynamics and marker visibility require physical inspection'},
            'candidates': [], 'measurement_procedure': {'entrypoint': 'measure_blind_person.py'},
            'preparation_status': 'incomplete'})
    (HERE / 'draft-execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({c['case_id']: c['construction_sha256'] for c in manifest['cases']}))


if __name__ == '__main__':
    main()
