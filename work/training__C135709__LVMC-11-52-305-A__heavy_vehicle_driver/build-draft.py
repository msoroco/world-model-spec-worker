"""Bind source-grounded heavy-vehicle parking Native drafts to exact cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = (('probe_1', 'away'), ('probe_2', 'beside'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial_native_draft', 'cases': []}
    for suffix, parking_case in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        description = {'channels': [
            {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': method, 'time_window': '600 original frames',
             'reference_frame': 'surveyed narrow road and original Native frame',
             'uncertainty': '50 ms sampling; public-park status and vehicle class unverified'}
            for name, method in (
                ('vehicle_pose_and_speed', 'original Native actor pose, velocity and bounding box'),
                ('park_frontage_geometry', 'authored bounds and Native lane survey'),
                ('source_camera_frame_join', 'four original RGB streams joined to Native frames'))],
            'limitations': ['Public-park designation, posted permission, commercial vehicle specifications, loading and service exceptions need independent source review']}
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': [ASSIGNMENT + '__' + s for s, _ in CASES],
                  'candidate_id': 'primary', 'law_id': 'LVMC-11-52-305-A',
                  'cell_id': 'C135709', 'actor': 'heavy_vehicle_driver',
                  'parking_case': parking_case, 'rate_hz': 20, 'duration_s': 30,
                  'required_atoms': [], 'source_packets': [],
                  'case': {'case_id': case_id},
                  'cameras': [{'name': name, 'width': 640, 'height': 360}
                              for name in ('overview', 'ego_front', 'curb', 'rear')],
                  'recording_description': description,
                  'status': 'cpu_draft_external_status_unverified'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'controller.py',
                              'measure_parking.py', 'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal = {'case_id': case_id, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': description,
                    'measurement_plan': {'entrypoint': 'measure_parking.py',
                        'required_sources': ['road.xodr', 'frontage-inventory.json',
                                             'vehicle-poses.jsonl', 'video_frames.jsonl']},
                    'static_checks': ['200 m two-way narrow road',
                        'Native lane and frontage survey', '600 frames at 20 Hz',
                        'four retained RGB source cameras'],
                    'termination_rules': ['600 frames', 'destroy owned actors and restore world'],
                    'mechanisms': ['common feedback controller, varied target station'],
                    'status': 'partial_native_draft_physical_unverified'}
        path = HERE / 'draft-exact' / suffix / 'primary' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Native heavy-vehicle dimensions, parking motion and frontage view require review'},
            'candidates': [], 'measurement_procedure': {'entrypoint': 'measure_parking.py'},
            'preparation_status': 'incomplete'})
    (HERE / 'draft-execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({c['case_id']: c['construction_sha256'] for c in manifest['cases']}))


if __name__ == '__main__':
    main()
