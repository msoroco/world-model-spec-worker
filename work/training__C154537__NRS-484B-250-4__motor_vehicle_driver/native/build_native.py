"""Bundle the authored one-way Native junction over source-bound exact requests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE_DIR = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    base = json.loads((CASE_DIR / 'draft-request-manifest.json').read_text())
    entries = []
    for old in base['cases']:
        proposal = json.loads((CASE_DIR / old['construction']).read_text())
        if sha(CASE_DIR / old['construction']) != old['construction_sha256']:
            raise ValueError('Source-bound request changed')
        proposal['entrypoint'] = 'runner.py'
        proposal['files'].extend([
            {'path': 'runner.py', 'content': (HERE / 'runner.py').read_text()},
            {'path': 'crossroads.xodr', 'content': (HERE / 'crossroads.xodr').read_text()},
            {'path': 'road.xodr', 'content': (HERE / 'crossroads.xodr').read_text()},
            {'path': 'finalize.py', 'content': (HERE / 'finalize.py').read_text()},
            {'path': 'measure_saved.py', 'content': (HERE / 'measure_saved.py').read_text()}])
        proposal['static_checks'] = ['one-way two-roadway OpenDRIVE junction',
            'authored two uncovered signal heads', 'four 600-frame original camera encoders',
            'Native actor motion and world restoration']
        proposal['status'] = 'selected_native_cpu_draft_not_delivery_prepared'
        proposal['recording_description']['channels'] = [
            {'name': name, 'unit': unit, 'method': method,
             'sampling_rate_hz': 20, 'time_window': '30 s / 600 frames',
             'reference_frame': 'original Native frame/time',
             'uncertainty': '50 ms frame bracket; physical and legal review pending'}
            for name, unit, method in (
                ('ego_front', 'm', 'original ego body vertices'),
                ('ego_speed', 'm/s', 'original Native velocity vector'),
                ('governing_signal', 'structured', 'original CARLA head/lane/state readback'),
                ('other_vehicle', 'structured', 'original actor body and motion history'),
                ('driver_view_rays', 'structured', 'sampled original Native world.cast_ray'))]
        proposal['recording_description']['context_inputs'] = []
        proposal['recording_description']['limitations'] = [
            'Authored OpenDRIVE and imported lane/device survey require physical review',
            'Through-highway and official-device source review pending']
        for old_key in ('rate_hz', 'duration_s', 'cameras_required',
                        'required_original_sources'):
            proposal['recording_description'].pop(old_key, None)
        suffix = old['case_id'].rsplit('__', 1)[-1]
        config_item = next(item for item in proposal['files'] if item['path'] == 'config.json')
        config = json.loads(config_item['content'])
        config['spawn_z_m'] = 1.5
        config['selected_case_id'] = old['case_id']
        config['case'] = {'case_id': old['case_id']}
        config['candidate_id'] = 'primary'
        config['frames'] = 600
        config['required_atoms'] = []
        config['source_packets'] = []
        config['cameras'] = [{'name': name, 'fps': 20} for name in
                             ('overview', 'approach', 'reference_corner', 'driver_reference')]
        config['supported_case_ids'] = [old['case_id']]
        config_item['content'] = json.dumps(config, indent=2) + '\n'
        path = HERE / 'native-bundles' / suffix / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        fallback = json.loads(json.dumps(proposal))
        fallback_config = next(item for item in fallback['files'] if item['path'] == 'config.json')
        altered = json.loads(fallback_config['content'])
        altered['spawn_z_m'] = 1.8
        altered['candidate_id'] = 'fallback1'
        fallback_config['content'] = json.dumps(altered, indent=2) + '\n'
        fallback_path = HERE / 'native-bundles' / suffix / 'fallback1.json'
        fallback_path.write_text(json.dumps(fallback, indent=2) + '\n')
        entries.append({'case_id': old['case_id'], 'kind': 'delivery',
            'construction': str(path.relative_to(CASE_DIR)),
            'construction_sha256': sha(path),
            'fixture_recipe': str((HERE / f'diagnostic-{suffix}-fixture-recipe.json').relative_to(CASE_DIR.parents[1])),
            'measurement_contract': str((HERE / f'{suffix}-measurement-contract.json').relative_to(CASE_DIR)),
            'candidate_risk': {'status': 'physical',
                'reason': 'The primary actor spawn may intersect imported road surface'},
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'candidates': [{'id': 'fallback1',
                'construction': str(fallback_path.relative_to(CASE_DIR)),
                'construction_sha256': sha(fallback_path),
                'trigger': {'source': 'original Native spawn result',
                            'metric': 'try_spawn_actor returns None or actor body overlaps imported road surface',
                            'failure_condition': 'primary actor spawn fails or overlaps surface'},
                'changed_knobs': ['both initial actor spawn heights from 1.5 m to 1.8 m']}],
            'delivery_readiness': 'incomplete'})
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
        'assignment_id': CASE_DIR.name, 'status': 'partial', 'cases': entries,
        'runtime_manifest_sha256': sha(CASE_DIR.parents[1] / 'runtime/SOURCE-MANIFEST.json'),
        'physical_acceptance_claimed': False}
    (CASE_DIR / 'draft-native-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_ids': [e['case_id'] for e in entries],
                      'construction_sha256': [e['construction_sha256'] for e in entries]}))


if __name__ == '__main__':
    build()
