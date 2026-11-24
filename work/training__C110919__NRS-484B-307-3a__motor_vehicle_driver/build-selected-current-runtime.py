"""Bind current source-proven candidates to two exact right-arrow deliveries."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P = HERE / 'proposals'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    source = json.loads((HERE / 'current-v2-probe-manifest.json').read_text())
    matrix = json.loads((HERE / 'current-runtime-candidate-matrix.json').read_text())
    rows = {(row['case_id'], row['candidate']): row for row in matrix['cases']}
    if len(rows) != 6 or source['runtime_manifest_sha256'] != sha(ROOT / 'runtime/SOURCE-MANIFEST.json'):
        raise ValueError('Current proof matrix or runtime differs')
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': source['runtime_manifest_sha256'],
                'status': 'selected_cpu_preparation_incomplete', 'cases': []}
    for old in source['cases']:
        entry = {key: value for key, value in old.items() if key != 'compatibility'}
        entry['kind'] = 'delivery'
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Original route drift or signal/body pixel clipping may prevent a usable right-arrow turn capture.'}
        entry['candidates'] = [candidate for candidate in old['candidates']
                               if candidate['id'] in ('fallback1', 'fallback3')]
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        primary_bundle = json.loads((HERE / entry['construction']).read_text())
        primary_config = json.loads(next(item['content'] for item in primary_bundle['files'] if item['path'] == 'config.json'))
        channels = primary_config['mandatory_channels']
        entry['acquisition'] = {
            name: {'entrypoint': 'runner.py' if name in ('native_body_pose_control', 'camera_frame_join') else 'finalize.py',
                   'method': 'Frame-joined original Native signal, actor, road and camera sources; authored command retained separately',
                   'evidence': 'Synthetic CPU fixture only; actual arrow glyph and yield require original pixels and Native readback'}
            for name in channels}
        for candidate_id, object_ in [('primary', entry)] + [(c['id'], c) for c in entry['candidates']]:
            proof = rows[(entry['case_id'], candidate_id)]
            folder = HERE / 'current-runtime-proofs' / entry['case_id'].rsplit('__', 1)[-1] / candidate_id
            relative = folder.relative_to(HERE)
            object_['offline'] = {
                'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/current-v2-probe-manifest.json --case {entry["case_id"]} --candidate {candidate_id} --output .runtime-work/c110919-3a-owner/matrix/{entry["case_id"].rsplit("__", 1)[-1]}-{candidate_id}/offline',
                'exit_code': 0, 'construction_sha256': proof['construction_sha256'],
                'log': (relative / 'offline.log').as_posix(),
                'log_sha256': proof['offline_log_sha256']}
            object_['compatibility'] = {
                'receipt': (relative / 'compatibility.json').as_posix(),
                'sha256': proof['receipt_sha256'],
                'log': (relative / 'analysis.log').as_posix(),
                'negative_log': (relative / 'negative-analysis.log').as_posix()}
        manifest['cases'].append(entry)
    write(HERE / 'execution-manifest.json', manifest)
    source_bundle = json.loads((HERE / 'draft-candidates/witness_1/primary/construction.json').read_text())
    bundle = json.loads(json.dumps(source_bundle))
    bundle['status'] = 'root_cpu_delivery_interface_original_unverified'
    bundle['measurement_plan'] = []
    bundle['static_checks'] = []
    ids = [entry['case_id'] for entry in manifest['cases']]
    for item in bundle['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['supported_case_ids'] = ids
            for camera in config['cameras']:
                camera['pose_strategy'] = {
                    'overview': 'fixed_world_intersection',
                    'approach': 'fixed_world_stop_line',
                    'reference_corner': 'fixed_world_signal_corner',
                    'driver_reference': 'subject_attachment'}[camera['name']]
                camera['fov_deg'] = 90 if camera['name'] != 'reference_corner' else 85
            item['content'] = json.dumps(config, indent=2, allow_nan=False) + '\n'
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    write(HERE / 'construction.json', bundle)
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for case in plan['cases']:
        case['kind'] = 'delivery'
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'circular green, right arrow, opposing red, body and turn', 'interval': '0-30 s'},
            {'view': 'approach', 'subject': 'stop line and adjacent pedestrian conflict', 'interval': '0-30 s'},
            {'view': 'reference_corner', 'subject': 'governing arrow head and opposing signal', 'interval': '0-30 s'},
            {'view': 'driver_reference', 'subject': 'driver sight line and crossing users', 'interval': '0-30 s'}]}
    channels = {row['name'] for row in bundle['recording_description']['channels']}
    plan['observations'] = [{'name': name, 'mandatory': True,
                             'purpose': 'Original Native source and reconstructed law observation'}
                            for name in sorted(channels)]
    input_ref = f'inputs/{HERE.name}/assignment.json'
    channel_map = {
        'dev.traffic_signal': ['dev.traffic_signal'],
        'dev.governs': ['dev.traffic_signal'],
        'drv.turning': ['native_body_pose_control'],
        'drv.entering_intersection': ['native_body_pose_control'],
        'st.crosswalk': ['st.crosswalk'],
        'ru.pedestrian': ['drv.yields_to'],
        'drv.in_intersection': ['native_body_pose_control'],
        'drv.yields_to': ['drv.yields_to'],
        'rel.oncoming': ['dev.traffic_signal']}
    mapping = plan.setdefault('source_observation_mapping', {name: {} for name in channel_map})
    if set(mapping) != set(channel_map):
        raise ValueError('Frozen observation terms changed')
    for name, row in mapping.items():
        row['channels'] = [value for value in channel_map[name] if value in channels]
        row['source_refs'] = [input_ref] if not row['channels'] else []
        row['evidence'] = ('Selected original Native and four-view source plan with current 600-frame CPU fixture; '
                           'physical truth, lawful-user status and arrow pixels require local review.')
    plan['readiness'] = 'selected_cpu_preparation_original_native_pending'
    write(plan_path, plan)
    proposal = json.loads((P / 'cases.json').read_text())
    proposal.update({'format': 'worker-draft-proposals-v1', 'cell_id': assignment['cell_id'],
                     'actor': assignment['actor'], 'status': 'draft',
                     'sweep_specs': [], 'sweeps_expanded': True})
    for case in proposal['cases']:
        case.update({'target_law_id': assignment['law_id'],
                     'rationale': 'Controlled same-cell right-arrow pedestrian yield contrast; physical and legal status unverified.',
                     'variable_assignments': {'yielded_to_pedestrian': {
                         'kind': 'subject_behavior', 'value': None}},
                     'unresolved_judgment_calls': ["'lawfully within' is rule composition"]})
    write(P / 'cases.json', proposal)
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(HERE / 'execution-manifest.json'),
                      'root_sha256': sha(HERE / 'construction.json')}))


if __name__ == '__main__':
    build()
