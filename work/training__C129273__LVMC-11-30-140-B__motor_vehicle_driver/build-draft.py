"""Materialize exact primary inline constructions for current runtime offline proof."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = ('probe_1', 'probe_2', 'white_wholly', 'white_partial',
         'assisted', 'early_release')
METHODS = {
    'Driver approaching a blind person carrying a white walking stick tipped in red.':
        ('approach_and_full_stop', 'full_stop'),
    'partial blindness': ('blindness_extent', 'blindness'),
    'white cane or white tipped red': ('cane_marker_form', 'marker'),
    'assisted-by-person wording': ('assisted_person', 'assistance'),
    'post-stop injury avoidance precautions': ('post_stop_precautions', 'precautions'),
}
SOURCES = ['vehicle-person-poses.jsonl', 'video_frames.jsonl',
           'camera-frames.jsonl', 'blind-person-context.json',
           'road-survey.json', 'road.xodr']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial_native_draft', 'cases': []}
    for suffix in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        plan = json.loads((HERE / 'case-plan.json').read_text())
        planned = next(c for c in plan['cases'] if c['case_id'] == case_id)
        cameras = [{'name': name, 'width': width, 'height': height,
                    'pose_strategy': purpose, 'fov_deg': 85}
                   for name, width, height, purpose in (
                       ('overview', 1920, 1080, 'full mountain-road encounter and both actors'),
                       ('approach', 1280, 720, 'ego approach and pedestrian contact region'),
                       ('reference_corner', 1280, 720, 'cane marker or assistant and clearance'),
                       ('driver_reference', 1280, 720, 'driver view of person and stopping region'))]
        source_method = {
            'ru.pedestrian_with_white_cane_or_guide_animal': 'retained original person identity and cane/assistant source context with independent pixel review',
            'drv.approaching': 'same-tick original ego/person pose, speed and longitudinal closure',
            'rel.centre_distance': 'same-tick original ego/person pose and body geometry',
            'drv.stopped': 'same-tick original ego velocity and stop interval',
            'kin.accel_longitudinal': 'finite difference of original ego velocity at 20 Hz',
            'drv.time_to_conflict': 'original relative pose and velocity with stated diagnostic assumptions',
            'ru.subject': 'original actor IDs, roles and driver viewpoint source',
            'rel.contact': 'original body geometry and any original contact event, separately reviewed',
            'rel.surface_gap': 'original ego/person body geometry and lateral/longitudinal clearance',
        }
        channels = [{'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                     'method': method, 'time_window': '600 original frames',
                     'reference_frame': 'surveyed mountain road and original Native frame',
                     'uncertainty': '50 ms sampling; marker appearance and blindness unverified'}
                    for name, method in source_method.items()]
        channels.append({'name': 'vehicle_person_pose', 'unit': 'structured', 'sampling_rate_hz': 20,
                         'method': 'original Native vehicle and pedestrian actor pose and speed',
                         'time_window': '600 original frames',
                         'reference_frame': 'surveyed mountain road and original Native frame',
                         'uncertainty': '50 ms sampling; marker appearance and blindness unverified'})
        description = {'channels': channels,
            'context_inputs': [{'name': 'blind_person_source_context', 'unit': 'structured',
                                'method': 'retained source request with independent review flags'}],
            'limitations': ['White or red-tipped cane and blindness require independent source and pixel review']}
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'supported_case_ids': [ASSIGNMENT + '__' + s for s in CASES],
                  'candidate_id': 'primary', 'law_id': 'LVMC-11-30-140-B',
                  'cell_id': 'C129273', 'actor': 'motor_vehicle_driver',
                  'source_context_request': planned['source_context_request'],
                  'rate_hz': 20, 'duration_s': 30, 'required_atoms': [],
                  'source_packets': [], 'case': {'case_id': case_id,
                    'recording_description': description},
                  'cameras': cameras, 'recording_description': description,
                  'status': 'cpu_draft_physical_marker_unverified'}
        requirements = []
        for index, disposition in enumerate(plan['requirement_dispositions']):
            if case_id in disposition['case_ids']:
                key, method = METHODS[disposition['branch']]
                requirements.append({'disposition_index': index,
                    'requirement': disposition['requirement'],
                    'source': disposition['source'], 'output_key': key,
                    'method': method, 'value_type': 'object',
                    'kind': 'measured' if index in (0, 4) else 'sourced_context',
                    'inputs': SOURCES})
        contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'requirements': requirements,
                    'negative': {'remove': ['blind-person-context.json'],
                                 'error_contains': 'Missing required source: blind-person-context.json'}}
        contract_path = HERE / ('measurement-' + suffix + '.json')
        contract_path.write_text(json.dumps(contract, indent=2) + '\n')
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'geometry.py', 'measure_blind_person.py',
                              'finalize_blind_person.py', 'tests/test_native.py')]
        files.append({'path': 'measurement-contract.json',
                      'content': contract_path.read_text()})
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal = {'case_id': case_id, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': description,
                    'measurement_plan': {'entrypoint': 'finalize_blind_person.py',
                        'required_sources': SOURCES},
                    'static_checks': ['240 m elevated road', 'Native lane survey',
                        '600 frames at 20 Hz', 'four retained RGB source cameras'],
                    'termination_rules': ['600 frames', 'destroy owned actors and restore world'],
                    'mechanisms': ['fixed mountain road and driver route; blind person source and driver stop/release policy vary only as declared',
                                   'authored cane debug strokes or assistant actor require later pixel/source review'],
                    'status': 'partial_native_draft_physical_unverified'}
        path = HERE / 'draft-exact' / suffix / 'primary' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'measurement_contract': str(contract_path.relative_to(HERE)),
            'fixture_recipe': 'work/' + ASSIGNMENT + '/diagnostic-recipe-' + suffix + '.json',
            'candidate_risk': {'status': 'physical',
                'reason': 'Native stop dynamics, cane strokes/assistant and pedestrian crossing need physical inspection'},
            'candidates': [], 'measurement_procedure': {'entrypoint': 'finalize_blind_person.py'},
            'preparation_status': 'incomplete'})
    (HERE / 'draft-execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({c['case_id']: c['construction_sha256'] for c in manifest['cases']}))


if __name__ == '__main__':
    main()
