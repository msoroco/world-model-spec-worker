"""Build the exact bicycle statutory-alternative draft from authored Native sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__bicycle_pass_wide'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    batch = json.loads((ROOT / 'batch.json').read_text())
    config = {'case_id': CASE, 'selected_case_id': CASE, 'supported_case_ids': [CASE],
        'case_suffix': 'bicycle_pass_wide', 'candidate_id': 'primary',
        'cell_id': 'C146108', 'law_id': 'NRS-484B-270-7b',
        'actor': 'cycle_or_scooter_operator', 'rider_class': 'bicycle',
        'rate_hz': 20, 'duration_s': 30, 'required_atoms': ['ru.bicycle', 'ru.motor_vehicle',
            'kin.position', 'kin.heading', 'kin.speed', 'rel.occupies'],
        'source_packets': [], 'case': {'case_id': CASE},
        'cameras': [{'name': name, 'width': width, 'height': height}
                    for name, width, height, *_ in (
            ('overview', 1920, 1080, 0), ('approach', 1280, 720, 0),
            ('passing_side', 1280, 720, 0), ('clear_ahead', 1280, 720, 0))],
        'recording_description': {'channels': [
            {'name': 'rider_pose', 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': 'original Native actor transform and body corners',
             'time_window': 'entire 600-frame 30-second pass',
             'reference_frame': 'Native road and frame', 'uncertainty': '50 ms sampling'},
            {'name': 'motor_pose', 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': 'original Native actor transform and body corners',
             'time_window': 'entire 600-frame 30-second pass',
             'reference_frame': 'Native road and frame', 'uncertainty': '50 ms sampling'}],
            'context_inputs': [{'name': 'motor_occupants', 'unit': 'count',
                                'method': 'independent original vehicle and driver review'}],
            'limitations': ['Electric-bicycle witness branch remains unconstructed',
                            'Generated CPU pass fixtures do not establish safety']},
        'status': 'selected_bicycle_cpu_draft_not_delivery_prepared'}
    files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
             for name in ('runner.py', 'geometry.py', 'pass_measure.py', 'tests/test_native.py')]
    files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
    proposal = {'case_id': CASE, 'law_id': 'NRS-484B-270-7b', 'cell_id': 'C146108',
        'actor': 'cycle_or_scooter_operator', 'entrypoint': 'runner.py', 'files': files,
        'recording_description': config['recording_description'],
        'measurement_plan': {'entrypoint': 'pass_measure.py',
                             'required_sources': ['participant-poses.jsonl', 'pass-context.json'],
                             'status': 'source_bound_cpu_draft'},
        'static_checks': ['authored one-way two-lane OpenDRIVE', 'four original camera plans',
                          '30-second 20 Hz Native actor/camera loop'],
        'termination_rules': ['600 original frames', 'restore world and destroy owned actors'],
        'mechanisms': ['bicycle accelerates past motor vehicle on separate through lane',
                       'original actor poses and four camera streams',
                       'sourced behind-to-clear-ahead full-pass measurement'],
        'status': 'selected_cpu_draft_physical_and_saved_delivery_unverified'}
    path = HERE / 'draft-bicycle/bicycle_pass_wide/primary/construction.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proposal, indent=2) + '\n')
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
        'assignment_id': HERE.name,
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'status': 'partial',
        'cases': [{'case_id': CASE, 'kind': 'delivery',
                   'construction': str(path.relative_to(HERE)),
                   'construction_sha256': sha(path),
                   'candidate_risk': {'status': 'physical',
                                      'reason': 'Pass clearance and camera visibility may fail on original Native motion'},
                   'candidates': [], 'measurement_procedure': {'entrypoint': 'pass_measure.py'},
                   'delivery_readiness': 'incomplete'}]}
    (HERE / 'draft-bicycle-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(path),
                      'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}))


if __name__ == '__main__':
    build()
