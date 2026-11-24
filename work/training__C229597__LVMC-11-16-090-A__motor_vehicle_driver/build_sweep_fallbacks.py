"""Materialize one exact alternate spawn for each physical sweep case."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    draft_cases = []
    for entry in manifest['cases']:
        if '__judgment-' not in entry['case_id']:
            continue
        source = json.loads((HERE / entry['construction']).read_text())
        fallback = copy.deepcopy(source)
        fallback['status'] = 'exact_physical_fallback_cpu_pending'
        for file in fallback['files']:
            if file['path'] == 'runner.py':
                old = "or config.get('spawn_point_index') != 0"
                if file['content'].count(old) != 1:
                    raise ValueError('Sweep runner spawn anchor differs')
                file['content'] = file['content'].replace(old, "or config.get('spawn_point_index') != 1")
                file['content'] = file['content'].replace(
                    "or config.get('candidate_id') != 'primary'",
                    "or config.get('candidate_id') != 'fallback1'")
                file['content'] = file['content'].replace(
                    "'candidate_id': 'primary',\n            'sweep_kind'",
                    "'candidate_id': 'fallback1',\n            'sweep_kind'")
            elif file['path'] == 'config.json':
                config = json.loads(file['content'])
                config['spawn_point_index'] = 1
                config['candidate_id'] = 'fallback1'
                file['content'] = json.dumps(config, indent=2) + '\n'
        folder = HERE / 'sweep-cases' / entry['case_id'] / 'fallback1'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'construction.json'
        write(path, fallback)
        entry['candidates'] = [{
            'id': 'fallback1',
            'construction': str(path.relative_to(HERE)),
            'construction_sha256': sha(path),
            'changed_knobs': ['spawn_point_index'],
            'trigger': {'source': 'original Native route review',
                        'metric': 'spawn availability and road projection',
                        'failure_condition': 'Primary spawn occupied or requested route unavailable'},
            'cpu_proof_status': 'offline_and_compatibility_pending'}]
        draft_cases.append({'case_id': entry['case_id'], 'kind': 'draft_not_selected',
                            'construction': str(path.relative_to(HERE / 'sweep-cases')),
                            'construction_sha256': sha(path), 'candidates': []})
    write(manifest_path, manifest)
    original = json.loads((HERE / 'sweep-cases/manifest.json').read_text())
    original['cases'] = draft_cases
    original['status'] = 'fallback_cpu_construction'
    write(HERE / 'sweep-cases/fallback-manifest.json', original)
    print(json.dumps({'fallbacks': len(draft_cases), 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
