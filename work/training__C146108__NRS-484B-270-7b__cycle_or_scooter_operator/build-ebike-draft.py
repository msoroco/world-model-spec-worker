"""Build the exact electric-bicycle witness CPU draft from authored sources."""
import hashlib
import json
from pathlib import Path
from native.observation_channels import channels

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__electric_bicycle_pass_wide'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    batch = json.loads((ROOT / 'batch.json').read_text())
    config = {'case_id': CASE, 'selected_case_id': CASE, 'supported_case_ids': [CASE],
        'case_suffix': 'electric_bicycle_pass_wide', 'candidate_id': 'primary',
        'cell_id': 'C146108', 'law_id': 'NRS-484B-270-7b',
        'actor': 'cycle_or_scooter_operator', 'rider_class': 'electric_bicycle',
        'rider_y_m': -1.75,
        'class_one_assist': {'carrier_blueprint': 'vehicle.bh.crossbike',
            'wheels': 2, 'operable_pedals': True, 'saddle': True,
            'rated_motor_watts': 500, 'pedal_power_watts': 175,
            'assist_only_while_pedaling': True, 'assist_cutoff_mph': 20,
            'moped': False, 'electric_scooter': False,
            'source': 'authored ebike.py kinematic surrogate; physical asset unverified'},
        'rate_hz': 20, 'duration_s': 30, 'required_atoms': ['ru.bicycle', 'ru.motor_vehicle',
            'kin.position', 'kin.heading', 'kin.speed', 'rel.occupies'],
        'source_packets': [], 'case': {'case_id': CASE},
        'physical_completion': {'criterion': 'overtake_pass',
            'motion_source': 'participant-poses.jsonl',
            'body_key': 'rider_body_xy_m', 'other_body_key': 'motor_body_xy_m',
            'lateral_transition_m': 0, 'minimum_progress_m': 1},
        'cameras': [{'name': name, 'width': width, 'height': height,
                     'pose_strategy': 'survey-gated fixed view along complete pass corridor',
                     'fov_deg': 85}
                    for name, width, height, *_ in (
            ('overview', 1920, 1080, 0), ('approach', 1280, 720, 0),
            ('reference_corner', 1280, 720, 0), ('driver_reference', 1280, 720, 0))],
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
            'limitations': ['Authored drivetrain does not certify rendered pedals or physical motor',
                            'Generated CPU pass fixtures do not establish safety']},
        'status': 'selected_electric_bicycle_cpu_draft_not_delivery_prepared'}
    config['recording_description']['channels'].extend(channels())
    files = [{'path': 'runner.py', 'content': (HERE / 'native/runner_ebike.py').read_text()}]
    files.extend({'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('ebike.py', 'geometry_ebike.py', 'pass_measure.py', 'finalize.py', 'tests/test_ebike.py'))
    files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
    proposal = {'case_id': CASE, 'law_id': 'NRS-484B-270-7b', 'cell_id': 'C146108',
        'actor': 'cycle_or_scooter_operator', 'entrypoint': 'runner.py', 'files': files,
        'recording_description': config['recording_description'],
        'measurement_plan': {'entrypoint': 'finalize.py',
                             'required_sources': ['participant-poses.jsonl', 'pass-context.json'],
                             'status': 'source_bound_cpu_draft'},
        'static_checks': ['authored one-way two-lane OpenDRIVE', 'four original camera plans',
                          '30-second 20 Hz Native actor/camera loop',
                          '500-watt pedal-only assist command with 20-mph cutoff'],
        'termination_rules': ['600 original frames', 'restore world and destroy owned actors'],
        'mechanisms': ['authored electric-bicycle assist command passes motor vehicle on separate through lane',
                       'original actor poses and four camera streams',
                       'sourced behind-to-clear-ahead full-pass measurement'],
        'status': 'selected_cpu_draft_physical_and_saved_delivery_unverified'}
    path = HERE / 'draft-ebike/electric_bicycle_pass_wide/primary/construction.json'
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
                   'candidates': [], 'measurement_procedure': {'entrypoint': 'finalize.py'},
                   'delivery_readiness': 'incomplete'}]}
    (HERE / 'draft-ebike-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(path),
                      'runtime_manifest_sha256': manifest['runtime_manifest_sha256']}))


if __name__ == '__main__':
    build()
