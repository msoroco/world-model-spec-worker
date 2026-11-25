"""Construct the exact contrast case using its retained Native runner."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    root = json.loads((PACKAGE / 'construction.json').read_text())
    contrast = json.loads((PACKAGE / 'draft-contrast/contrast/primary/construction.json').read_text())
    selected = PACKAGE / 'selected/contrast'
    selected.mkdir(parents=True, exist_ok=True)
    files = {item['path']: item for item in contrast['files']}
    config = json.loads(files['config.json']['content'])
    config['supported_case_ids'] = [PACKAGE.name + '__reference', PACKAGE.name + '__contrast']
    config['recording_description'] = root['recording_description']
    config['case'] = {'case_id': config['case_id'],
                      'requested_setting': 'contrast',
                      'recording_description': root['recording_description']}
    runner = files['runner.py']['content']
    tests = files['tests/test_offline.py']['content']
    (selected / 'runner.py').write_text(runner)
    write(selected / 'config.json', config)
    (selected / 'tests').mkdir(exist_ok=True)
    (selected / 'tests/test_offline.py').write_text(tests)
    construction = dict(root)
    construction['case_id'] = config['case_id']
    construction['files'] = [dict(item) for item in root['files']]
    for item in construction['files']:
        if item['path'] == 'runner.py':
            item['content'] = runner
        elif item['path'] == 'config.json':
            item['content'] = (selected / 'config.json').read_text()
        elif item['path'] == 'tests/test_offline.py':
            item['content'] = tests
    write(selected / 'construction.json', construction)
    manifest_path = PACKAGE / 'selected-probe-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'] = [entry for entry in manifest['cases']
                         if not entry['case_id'].endswith('__contrast')]
    manifest['cases'].append({
        'case_id': config['case_id'], 'kind': 'draft_not_selected',
        'construction': 'selected/contrast/construction.json',
        'construction_sha256': sha(selected / 'construction.json'),
        'measurement_contract': 'measurement-contract-contrast.json',
        'measurement_procedure': {'entrypoint': 'selected_finalize.py',
                                  'output_schema': 'c230241-selected-saved-analysis-v1'},
        'fixture_recipe': 'work/' + PACKAGE.name + '/selected-recipe-contrast.json',
        'candidates': [],
    })
    write(manifest_path, manifest)
    return {'case_id': config['case_id'],
            'construction_sha256': sha(selected / 'construction.json')}


if __name__ == '__main__':
    print(json.dumps(build()))
