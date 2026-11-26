"""Assemble the selected taxi package without regenerating bound CPU proofs."""
import copy
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    selected = json.loads((BASE / 'selected-draft-manifest.json').read_text())
    plan = json.loads((BASE / 'case-plan.json').read_text())
    case_ids = [entry['case_id'] for entry in selected['cases']]
    construction = copy.deepcopy(json.loads((BASE / selected['cases'][0]['construction']).read_text()))
    for item in construction['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['supported_case_ids'] = case_ids
            item['content'] = json.dumps(config, indent=2, allow_nan=False) + '\n'
        path = BASE / item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['content'])
    construction['measurement_plan'] = {
        'entrypoint': 'selected_finalize.py',
        'required_sources': ['trace.jsonl', 'video_frames.jsonl',
                             'observed-activity.jsonl',
                             'participant-activity-review.json',
                             'taxi-license-review.json',
                             'stand-designation-review.json',
                             'other-regulations-review.json',
                             'overview.mkv', 'approach.mkv',
                             'reference_corner.mkv', 'driver_reference.mkv']}
    construction['static_checks'] = [
        'Exact C394327 non-stand curb and taxi request identity',
        'Passenger and merchandise activity requested in separate cases',
        '600 original frames at 20 Hz with four RGB camera sources',
        'Original authority, activity and pixels remain independent review']
    construction['termination_rules'] = [
        'Stop after 600 frame-joined ticks',
        'Close four encoders, destroy owned actors and restore Native world']
    construction['mechanisms'] = [
        'Stationary taxi brake controller and source-hashed participant request',
        'Frame-joined original activity and independent authority review']
    write(BASE / 'construction.json', construction)
    manifest = copy.deepcopy(selected)
    manifest['status'] = 'delivery_prepared'
    manifest['delivery_ready'] = True
    for entry in manifest['cases']:
        entry['native_handoff'] = {
            'python_env_var': 'CARLA_PYTHON',
            'host_env_var': 'CARLA_HOST',
            'port_env_var': 'CARLA_PORT'}
        selected_construction = json.loads((BASE / entry['construction']).read_text())
        files = {item['path'] for item in selected_construction['files']}
        source_names = set(json.loads(next(item['content'] for item in selected_construction['files']
                                           if item['path'] == 'config.json')).get('required_atoms', []))
        source_names |= {channel['name'] for channel in selected_construction['recording_description']['channels']}
        entry['acquisition'] = {
            name: {'entrypoint': 'selected_finalize.py',
                   'method': 'frame-joined observed-activity source and reviewed original context',
                   'evidence': plan['source_observation_mapping'][name]['evidence']}
            for name in sorted(source_names)}
        if 'selected_finalize.py' not in files:
            raise ValueError('Selected finalizer missing from construction')
    write(BASE / 'execution-manifest.json', manifest)
    result_path = BASE / 'result.json'
    result = json.loads(result_path.read_text())
    result['selected_draft_cpu_proof']['manifest_sha256'] = sha(BASE / 'selected-draft-manifest.json')
    write(result_path, result)


if __name__ == '__main__':
    main()
