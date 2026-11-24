"""Bind exact current-v2 primary bus-loading construction drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = (('probe_1', 'near'), ('probe_2', 'far'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial_native_draft', 'cases': []}
    for suffix, bus_case in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        description = {'channels': [
            {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': method, 'time_window': '600 original frames',
             'reference_frame': 'surveyed one-way curb and original Native frame',
             'uncertainty': '50 ms sampling; loading activity and location status unverified'}
            for name, method in (
                ('bus_wheel_and_pose', 'Native bus wheel geometry and original actor pose/velocity'),
                ('curb_and_zone_geometry', 'authored curb face and Native lane survey'),
                ('other_vehicle_motion', 'original Native other-vehicle pose and velocity'),
                ('camera_frame_join', 'four original RGB streams joined to Native frames'))],
            'limitations': ['Qualifying location, public street, non-tour status, actual loading and undue impedance need independent source review']}
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': [ASSIGNMENT + '__' + s for s, _ in CASES],
                  'candidate_id': 'primary', 'law_id': 'LVMC-11-60-030-A4',
                  'cell_id': 'C149507', 'actor': 'bus_driver',
                  'bus_case': bus_case, 'rate_hz': 20, 'duration_s': 30,
                  'required_atoms': [], 'source_packets': [],
                  'case': {'case_id': case_id},
                  'cameras': [{'name': name, 'width': 640, 'height': 360}
                              for name in ('overview', 'bus_front', 'curb_wheel', 'traffic_rear')],
                  'recording_description': description,
                  'status': 'cpu_draft_location_loading_unverified'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'entry.py',
                              'measure_bus.py', 'tests/test_native.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal = {'case_id': case_id, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': description,
                    'measurement_plan': {'entrypoint': 'measure_bus.py',
                        'required_sources': ['road.xodr', 'bus-zone-inventory.json',
                                             'bus-traffic-poses.jsonl', 'video_frames.jsonl']},
                    'static_checks': ['160 m one-way curb lane',
                        'Native lane and bus wheel survey', '600 frames at 20 Hz',
                        'four retained RGB source cameras'],
                    'termination_rules': ['600 frames', 'destroy owned actors and restore world'],
                    'mechanisms': ['same bus/other-vehicle scene; right-front-wheel gap target varies'],
                    'status': 'partial_native_draft_physical_unverified'}
        path = HERE / 'draft-exact' / suffix / 'primary' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'candidate_risk': {'status': 'physical',
                'reason': 'Native bus stop dynamics, wheel geometry and loading visibility require review'},
            'candidates': [], 'measurement_procedure': {'entrypoint': 'measure_bus.py'},
            'preparation_status': 'incomplete'})
    (HERE / 'draft-execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({c['case_id']: c['construction_sha256'] for c in manifest['cases']}))


if __name__ == '__main__':
    main()
