"""Materialize eight exact, unselected signed-road construction drafts."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
NATIVE = FOLDER / 'native'
ASSIGNMENT = FOLDER.name
RUNTIME_MANIFEST = '391baee19ccece687c5632aa2cc64ba3b958c8b492045b30e4bfc4caa131c235'
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')
FILES = ('runner.py', 'geometry.py', 'controller.py', 'engineering.py',
         'measure_u_turn.py', 'pixel_review.py', 'finalize.py', 'cameras.py')
TESTS = ('test_geometry.py', 'test_measure_u_turn.py', 'test_engineering.py', 'test_runner.py')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def recording_description():
    methods = {
        'dev.regulatory_sign': 'Original sign pixels, Native landmark readback and reviewed official designation',
        'dev.governs': 'Original sign pixels and lane/region applicability review',
        'dev.position': 'Native landmark coordinate and original sign pixel location',
        'drv.u_turn': 'Joined original Native body and heading trace across governed region',
        'kin.heading': 'Original Native forward vector at every joined frame',
        'rel.occupies': 'Original Native full body relative to reviewed governed region',
        'native_body_pose_control': 'Original Native pose, full body, lane ID and controller request',
        'camera_frame_join': 'Every original camera frame joined to Native frame and time',
    }
    return {'channels': [{'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': method, 'time_window': 'entire 24 s / 480 frame attempt',
             'reference_frame': 'Native map and original video frame',
             'uncertainty': '50 ms samples, finite body/map precision, original pixel review pending'}
             for name, method in methods.items()],
            'context_inputs': [{'name': 'signed_hill_crest', 'unit': 'structured',
             'method': 'Native road/lane/landmark readback and original pixel review'}],
            'limitations': ['Official sign meaning, original pixel visibility and physical movement require review',
                            'Requested route is not observed behavior or a legal verdict']}


def build():
    shared = {name: (NATIVE / name).read_text() for name in FILES}
    shared.update({'tests/' + name: (NATIVE / name).read_text() for name in TESTS})
    for fixture in (FOLDER / 'draft-u-turn-saved').glob('*/*'):
        if fixture.is_file():
            shared[str(fixture.relative_to(FOLDER))] = fixture.read_text()
    recording = recording_description()
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': ASSIGNMENT, 'runtime_manifest_sha256': RUNTIME_MANIFEST,
                'status': 'draft_not_selected', 'cases': []}
    risks = {
        'fallback1': {'metric': 'maximum_approach_route_error_m',
                      'failure_condition': 'Source-measured error >0.35 m',
                      'changed_knobs': ['target_speed_mps 5.0 to 3.5']},
        'fallback2': {'metric': 'requested_movement_completed',
                      'failure_condition': 'Source-measured requested movement incomplete by frame 480',
                      'changed_knobs': ['lookahead_m 4.0 to 5.5']},
        'fallback3': {'metric': 'sign_and_body_visible_fraction',
                      'failure_condition': 'Source-reviewed visibility <0.95',
                      'changed_knobs': ['sign camera [-12,9,5] to [-12,11,6]']},
    }
    for suffix in ('witness_1', 'witness_2'):
        case_id = ASSIGNMENT + '__' + suffix
        contract_path = FOLDER / ('draft-measurement-contract-' + suffix + '.json')
        entry = {'case_id': case_id, 'kind': 'draft_not_selected',
                 'candidate_risk': {'status': 'physical',
                     'reason': 'Native lane/sign readback, route tracking and original pixels require an actual attempt'},
                 'measurement_contract': str(contract_path.relative_to(FOLDER)),
                 'measurement_procedure': {'entrypoint': 'finalize.py',
                     'output_schema': 'signed-u-turn-original-frame-measurement-v1'},
                 'candidates': []}
        for candidate in NAMES:
            config = {'case_id': case_id, 'selected_case_id': case_id,
                'supported_case_ids': [case_id], 'case_suffix': suffix,
                'candidate_id': candidate, 'cell_id': 'C104538',
                'law_id': 'NRS-484B-403-2', 'actor': 'motor_vehicle_driver',
                'rate_hz': 20, 'duration_s': 24,
                'required_atoms': ['dev.regulatory_sign', 'dev.governs', 'dev.position',
                                   'drv.u_turn', 'kin.heading', 'rel.occupies'],
                'source_packets': [], 'mandatory_channels': [],
                'case': {'case_id': case_id}, 'recording_description': recording,
                'cameras': [{'name': name, 'width': w, 'height': h,
                    'pose_strategy': 'candidate-specific Native mount in cameras.py',
                    'fov_deg': fov} for name, w, h, fov in
                    (('overview',1920,1080,75), ('approach',1280,720,92),
                     ('sign_reference',1280,720,90), ('driver_reference',1280,720,105))],
                'status': 'unselected_native_capture_draft'}
            files = [{'path': name, 'content': value} for name, value in shared.items()]
            files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
            construction = {'case_id': case_id, 'cell_id': 'C104538',
                'law_id': 'NRS-484B-403-2', 'actor': 'motor_vehicle_driver',
                'entrypoint': 'runner.py', 'files': files,
                'measurement_plan': {'method': 'source-hashed original Native full-body and heading reversal with reviewed applicable sign',
                                     'status': 'prototype_not_delivery_compatible'},
                'recording_description': recording,
                'static_checks': ['authored map/route', 'controller/camera preflight',
                                  'source-bound synthetic measurement'],
                'termination_rules': ['480 original frames', 'failure retained on capture/restoration error'],
                'mechanisms': ['authored hill-crest and proposed sign',
                               'observed-pose path controller', 'four FFV1 original cameras'],
                'status': 'unselected_cpu_draft'}
            relative = f'draft-candidates/{suffix}/{candidate}/construction.json'
            path = FOLDER / relative
            write(path, construction)
            ref = {'id': candidate, 'construction': relative, 'construction_sha256': digest(path)}
            if candidate == 'primary':
                entry.update(ref)
            else:
                risk = risks[candidate]
                ref.update({'trigger': {'source': 'source-hashed original Native samples, frame map, sign review and approach video',
                                        'evaluator': 'engineering.py:evaluate_fallbacks',
                                        'metric': risk['metric'],
                                        'failure_condition': risk['failure_condition']},
                            'changed_knobs': risk['changed_knobs']})
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(FOLDER / 'draft-execution-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    value = build()
    print(json.dumps({'cases': len(value['cases']),
                      'candidates': sum(1+len(c['candidates']) for c in value['cases']),
                      'status': value['status']}))
