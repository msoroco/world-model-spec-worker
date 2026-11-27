"""Build exact inline CPU constructions and draft selection manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native'
ASSIGNMENT = ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


plan = json.loads((ROOT / 'case-plan.json').read_text())
prior_path = ROOT / 'execution-manifest.json'
prior_cases = {entry['case_id']: entry for entry in json.loads(prior_path.read_text()).get('cases', [])} if prior_path.is_file() else {}
channels = [
    'st.railway_crossing', 'drv.approaching', 'st.sight_distance',
    'rel.visible', 'kin.speed', 'ru.rail_vehicle',
    'dev.human_direction', 'dev.railway_signal_or_gate', 'rel.centre_distance',
]
description = {
    'channels': [{
        'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
        'time_window': '600 original Native frames',
        'method': 'original body, reviewed railway, same-tick world.cast_ray and saved exception review',
        'reference_frame': 'original Native frame and source-hashed grade crossing',
        'uncertainty': 'virtual observer proxy, collision rays and original device review require physical confirmation',
    } for name in channels],
    'context_inputs': [{
        'name': 'original_crossing_source_review', 'unit': 'structured',
        'method': 'source-hashed original railway, jurisdiction, flagman and signal reviews',
        'reference_frame': 'original Native map and actor identities',
        'uncertainty': 'physical railway and exception qualification require independent review',
    }],
    'limitations': [
        'Collision ray proxy does not establish actual driver perception or legal clear visibility.',
        'Requested speed is not achieved speed or prima facie legal outcome.',
        'Flagman duty and crossing signal semantics need independent saved review of original evidence.',
    ],
}
camera_data = [
    ('overview', 1920, 1080, [-15, -18, 22], 35, -30),
    ('approach', 1280, 720, [-30, 5, 9], -10, -14),
    ('reference_corner', 1280, 720, [3, -9, 10], 25, -20),
    ('driver_reference', 1280, 720, [12, 10, 11], -145, -20),
]
cameras = [{'name': name, 'width': width, 'height': height, 'fps': 20,
            'fov_deg': 85, 'mount_xyz_relative_to_crossing_m': xyz,
            'yaw_deg': yaw, 'pitch_deg': pitch,
            'pose_strategy': 'fixed surveyed crossing-relative viewpoint; verify original lane and rail coverage before dispatch'} for
           name, width, height, xyz, yaw, pitch in camera_data]

source_names = ('runner.py', 'controller.py', 'rail_native_rays.py',
                'rail_sight.py', 'source_review.py', 'rail_join.py',
                'frame_capture.py', 'finalize.py')
source_inputs = ['road.xodr', 'rail-body.jsonl', 'rail-rays.jsonl',
                 'reviewed-exceptions.jsonl', 'reviewed-exceptions-review.json',
                 'video_frames.jsonl', 'trace.jsonl'] + [
                     'original-source-review/' + role + ending for role in
                     ('railway', 'approach', 'flagman', 'signal') for ending in
                     ('.json', '.source.txt')]
measure_methods = [('rail_sight_and_speed', 'measure_rail_geometry'),
                   ('crossing_exceptions', 'measure_exception'),
                   ('selected_witness', 'measure_selected_witness')]
manifest_cases = []
for case in plan['cases']:
    case_id = case['case_id']
    suffix = case_id.split('__')[-1]
    requirements = []
    for index, disposition in enumerate(plan['requirement_dispositions']):
        if case_id in disposition['case_ids']:
            key, method = measure_methods[index]
            requirements.append({'disposition_index': index,
                                 'requirement': disposition['requirement'],
                                 'source': disposition['source'],
                                 'output_key': key, 'method': method,
                                 'value_type': 'object', 'kind': 'measured',
                                 'inputs': source_inputs})
    write(ROOT / 'selected-measurements' / suffix / 'measurement-contract.json', {
        'format': 'worker-measurement-contract', 'case_id': case_id,
        'requirements': requirements,
        'negative': {'remove': ['rail-rays.jsonl'],
                     'error_contains': 'Missing required source: rail-rays.jsonl'},
    })
    candidates = []
    for candidate, gain in (('primary', 1.0), ('fallback1', 1.25)):
        config = {
            'case_id': case_id, 'selected_case_id': case_id,
            'law_id': plan['law_id'], 'cell_id': plan['cell_id'], 'actor': plan['actor'],
            'rate_hz': 20, 'duration_s': 30, 'duration_frames': 600,
            'candidate_id': candidate, 'speed_mode': case['construction_design']['speed_mode'],
            'sight_mode': case['construction_design']['sight_mode'],
            'exception_state': case['construction_design']['exception_state'],
            'feedback_gain': gain, 'ego_blueprint_filter': 'vehicle.*',
            'required_atoms': [], 'source_packets': [], 'cameras': cameras,
            'case': {'case_id': case_id, 'recording_description': description},
            'recording_description': description,
        }
        files = [{'path': name, 'source': 'work/' + ASSIGNMENT + '/native/' + name,
                  'content': (NATIVE / name).read_text()} for name in source_names]
        files += [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                  {'path': 'tests/test_native.py',
                   'source': 'work/' + ASSIGNMENT + '/native/test_native.py',
                   'content': (NATIVE / 'test_native.py').read_text()}]
        construction = {
            'format': 'worker-inline-construction', 'case_id': case_id,
            'law_id': plan['law_id'], 'cell_id': plan['cell_id'], 'actor': plan['actor'],
            'entrypoint': 'runner.py', 'files': files,
            'recording_description': description,
            'measurement_plan': 'Original 600-frame body, signed 400-foot rail rays and four-camera capture; saved exception duty and signal review pending.',
            'static_checks': ['exact law/cell/actor', 'four 20 Hz cameras',
                              '600 original frames', 'source-hashed original railway and railway traffic',
                              'no physical or legal preclaim'],
            'termination_rules': ['600 original Native frames or explicit failure with world restoration'],
            'mechanisms': ['original surveyed at-grade railway and preexisting rail vehicles',
                           'world.cast_ray through 400 feet in two directions from moving ego',
                           'source-hashed original exception review',
                           'measured-speed feedback for selected contrast'],
            'status': 'draft_cpu_construction',
        }
        path = (ROOT / 'native' / suffix / 'construction.json') if candidate == 'primary' else (ROOT / 'fallbacks' / suffix / 'fallback1' / 'construction.json')
        write(path, construction)
        candidates.append((candidate, path.relative_to(ROOT).as_posix(), sha(path)))
        if suffix == 'condition_a' and candidate == 'primary':
            write(ROOT / 'config.json', config)
            write(ROOT / 'construction.json', construction)
            (ROOT / 'runner.py').write_text((NATIVE / 'runner.py').read_text())
    manifest_cases.append({
        'case_id': case_id, 'kind': 'delivery', 'construction': candidates[0][1],
        'construction_sha256': candidates[0][2],
        'measurement_procedure': {'entrypoint': 'finalize.py'},
        'measurement_contract': 'selected-measurements/' + suffix + '/measurement-contract.json',
        'fixture_recipe': 'work/' + ASSIGNMENT + '/diagnostic-' + suffix + '-recipe.json',
        'candidate_risk': {'status': 'physical',
                           'reason': 'Measured approach and rail traffic may not realize the requested sight or speed contrast.'},
        'candidates': [{'id': 'fallback1', 'construction': candidates[1][1],
                        'construction_sha256': candidates[1][2],
                        'trigger': {'source': 'original Native body and four-camera trace',
                                    'metric': 'crossing traversal speed and realized sight',
                                    'failure_condition': 'primary controller misses requested traversal speed'},
                        'changed_knobs': ['feedback_gain 1.0 to 1.25']}],
    })

root_config = json.loads((ROOT / 'config.json').read_text())
root_config['supported_case_ids'] = [entry['case_id'] for entry in manifest_cases]
write(ROOT / 'config.json', root_config)

runtime_sha = sha(Path('runtime/SOURCE-MANIFEST.json'))
write(ROOT / 'proposals/cases.json', {
    'status': 'draft', 'cell_id': plan['cell_id'], 'actor': plan['actor'],
    'sweep_specs': [], 'sweeps_expanded': True,
    'cases': [{
        'case_id': case['case_id'], 'target_law_id': plan['law_id'],
        'target_type': 'delivery',
        'rationale': case['claim'],
        'variable_assignments': case['construction_design'],
        'unresolved_judgment_calls': [
            'Actual clear unobstructed view and qualification of railway, flagman and signal require independent original review.',
            'Prima facie legal effect is not computed by this worker.'
        ],
        'recording_description': description,
    } for case in plan['cases']],
})
for entry in manifest_cases:
    old = prior_cases.get(entry['case_id'], {})
    if old.get('construction_sha256') == entry['construction_sha256'] and old.get('offline'):
        entry['offline'] = old['offline']
    old_fallbacks = {candidate['id']: candidate for candidate in old.get('candidates', [])}
    for candidate in entry['candidates']:
        earlier = old_fallbacks.get(candidate['id'], {})
        if earlier.get('construction_sha256') == candidate['construction_sha256'] and earlier.get('offline'):
            candidate['offline'] = earlier['offline']
write(ROOT / 'execution-manifest.json', {
    'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
    'runtime_manifest_sha256': runtime_sha, 'status': 'draft_offline_only',
    'cases': manifest_cases,
})
print('built', len(manifest_cases), 'cases with primary and fallback1 constructions')
