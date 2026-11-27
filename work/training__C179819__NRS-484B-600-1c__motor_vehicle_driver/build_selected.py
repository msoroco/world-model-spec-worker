"""Build three exact posted-speed Native bundles and source-bound contracts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
TARGETS = {'below_posted': 25.0, 'at_posted': 30.0, 'above_posted': 35.0}
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))
SOURCES = ('native_motion.jsonl', 'road_context.json', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl', 'road.xodr',
           'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def build(slug, target, plan, assignment):
    cid = AID + '__' + slug
    channels = [
        {'name': 'ego_pose', 'unit': 'm', 'sampling_rate_hz': 20,
         'method': 'Original Native actor position after each tick',
         'time_window': '600 frames / 30 s', 'reference_frame': 'reviewed highway portion',
         'uncertainty': '50 ms sampling and original map review'},
        {'name': 'measured_speed_vs_posted_limit', 'unit': 'mph', 'sampling_rate_hz': 20,
         'method': 'Norm of original Native three-axis velocity with sourced posting context',
         'time_window': '600 frames / 30 s', 'reference_frame': 'original sign passage and governed portion',
         'uncertainty': '50 ms sampling; original authority and posting review pending'}]
    description = {'channels': channels, 'context_inputs': [
        {'name': name, 'unit': 'structured', 'method': 'original source with independent review'}
        for name in ('public_authority_posting', 'governed_highway_portion', 'sign_position', 'native_map')],
        'limitations': ['Requested speed does not establish measured speed.',
                        'Authored sign does not establish a public-authority posting.',
                        'No legal outcome is inferred from CPU diagnostics.']}
    cfg = {'assignment_id': AID, 'law_id': assignment['law_id'], 'cell_id': assignment['cell_id'],
           'actor': assignment['actor'], 'selected_case_id': cid,
           'case': {'case_id': cid, 'recording_description': description},
           'supported_case_ids': [AID+'__'+item for item in TARGETS],
           'required_atoms': [], 'source_packets': [], 'rate_hz': 20, 'duration_s': 30,
           'frames': 600, 'requested_speed_mph': target, 'posted_speed_request_mph': 30,
           'physical_completion': {'criterion': 'travel_progress', 'minimum_progress_m': 100.0,
                'engineering_tolerances_not_legal': True,
                'completion_goal_method': 'Original Native roadway travel through sourced posted zone'},
           'cameras': [{'name': name, 'width': width, 'height': height, 'fps': 20,
                        'fov_deg': 85, 'pose_strategy': 'ego_attached' if name == 'driver_reference' else 'surveyed_world'}
                       for name, width, height in CAMERAS],
           'recording_description': description, 'physical_acceptance_claimed': False,
           'legal_verdict': None}
    contract = {'format': 'worker-measurement-contract', 'case_id': cid,
                'status': 'selected_cpu_draft', 'negative': {'remove': ['road_context.json'],
                    'error_contains': 'Missing required source: road_context.json'},
                'requirements': [{'disposition_index': i, 'requirement': item['requirement'],
                    'source': item['source'], 'kind': 'measured', 'method': 'measure_speed',
                    'output_key': 'posted_speed_observation_' + str(i), 'value_type': 'object',
                    'inputs': list(SOURCES)} for i, item in enumerate(plan['requirement_dispositions'])
                    if cid in item['case_ids']], 'legal_compliance': 'unassessed'}
    contract_path = HERE / ('measurement-' + slug + '.json')
    put(contract_path, contract)
    modules = ('runner.py', 'road.py', 'speed_measure.py', 'finalize.py',
               'tests/test_selected.py')
    files = [{'path': name, 'source': str((HERE/name).relative_to(REPO)),
              'content': (HERE/name).read_text()} for name in modules]
    files.append({'path': 'config.json', 'content': json.dumps(cfg, indent=2, ensure_ascii=False)+'\n'})
    frozen = REPO / 'inputs' / AID / 'assignment.json'
    files.append({'path': str(frozen.relative_to(REPO)), 'source': str(frozen.relative_to(REPO)),
                  'content': frozen.read_text()})
    construction = {'case_id': cid, 'law_id': assignment['law_id'], 'cell_id': assignment['cell_id'],
        'actor': assignment['actor'], 'entrypoint': 'runner.py', 'files': files,
        'status': 'selected_cpu_prepared_original_unverified',
        'recording_description': description,
        'measurement_plan': {'method': 'source-bound measured velocity in independently reviewed posted highway portion',
                             'duration_s': 30, 'legal_tolerance_claimed': False},
        'static_checks': ['OpenDRIVE authored 30 mph signal and 1800 m road',
                          'ego and separate other actor creation', 'four original 20 Hz cameras',
                          '600-frame Native/Core/video/source joins'],
        'termination_rules': ['600 original frames', 'abort on lane or camera frame mismatch',
                              'encoder closure and world restore'],
        'mechanisms': ['CARLA OpenDRIVE posting geometry',
                       'Native velocity feedback controller; actual speed separately measured',
                       'source-reviewed public authority and governed extent']}
    path = HERE / 'selected' / slug / 'construction.json'
    put(path, construction)
    return {'case_id': cid, 'kind': 'delivery',
            'construction': str(path.relative_to(HERE)), 'construction_sha256': sha(path),
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'measurement_contract': contract_path.name,
            'fixture_recipe': 'work/'+AID+'/diagnostic/'+slug+'/fixture-recipe.json',
            'recording_description': description,
            'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                               'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {'status': 'none',
                'reason': 'Actual speed and sign visibility need original review; no primary failure has been measured to define a distinct fallback trigger'},
            'candidates': []}


def main():
    plan = json.loads((HERE/'case-plan.json').read_text())
    assignment = json.loads((REPO/'inputs'/AID/'assignment.json').read_text())
    if (assignment['law']['text'] != plan['source_law_text'] or
            any(assignment['cell'].get(key) != value for key, value in
                {'layout': 'paved_road', 'maneuver': 'travel', 'control': 'speed_limit_sign'}.items())):
        raise ValueError('Frozen posted-speed law or cell changed')
    entries = [build(slug, target, plan, assignment) for slug, target in TARGETS.items()]
    batch = json.loads((REPO/'batch.json').read_text())
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
        'status': 'draft_incomplete_proofs',
        'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
        'physical_acceptance_claimed': False, 'cases': entries}
    put(HERE/'draft-native-manifest.json', manifest)
    first = json.loads((HERE/'selected/below_posted/construction.json').read_text())
    put(HERE/'config.json', json.loads(next(item['content'] for item in first['files'] if item['path'] == 'config.json')))
    put(HERE/'construction.json', json.loads((HERE/entries[0]['construction']).read_text()))
    return {'cases': len(entries), 'manifest_sha256': sha(HERE/'draft-native-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
