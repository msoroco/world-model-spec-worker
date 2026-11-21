"""Translate the synthetic straight diagnostic to a road segment clear of the junction."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OFFSET_X = 13.0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vertices(values):
    return [[round(v[0] + OFFSET_X, 5), *v[1:]] for v in values]


def build():
    original = json.loads((HERE / 'selected-diagnostic-condition_a.json').read_text())
    spec = copy.deepcopy(original)
    files = spec['files']
    for name in ('native_samples.jsonl', 'trace.jsonl', 'body_history.jsonl',
                 'capture/evidence.jsonl'):
        rows = [json.loads(line) for line in files[name].splitlines()]
        for row in rows:
            if name == 'native_samples.jsonl':
                row['native_center_xy_m'][0] = round(row['native_center_xy_m'][0] + OFFSET_X, 8)
                row['native_body_xy_m'] = vertices(row['native_body_xy_m'])
                row['body_xy_m'] = vertices(row['body_xy_m'])
            elif name == 'trace.jsonl':
                row['position']['x'] = round(row['position']['x'] + OFFSET_X, 8)
                row['position_m'][0] = round(row['position_m'][0] + OFFSET_X, 8)
            elif name == 'body_history.jsonl':
                row['body_vertices_m'] = vertices(row['body_vertices_m'])
            else:
                row['ego']['body_vertices_m'] = vertices(row['ego']['body_vertices_m'])
                row['ego']['position_m'][0] = round(row['ego']['position_m'][0] + OFFSET_X, 8)
        files[name] = ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n'
                              for row in rows)
    capture = json.loads(files['capture/manifest.json'])
    capture['sources']['trace.jsonl'] = hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()
    files['capture/manifest.json'] = json.dumps(capture, separators=(',', ':'))
    destination = HERE / 'selected-diagnostic-condition_c.json'
    destination.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
    if destination.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Control fixture exceeds return size limit')
    assignment = ROOT / 'inputs' / HERE.name / 'assignment.json'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input-assignment.json',
                           'source': 'inputs/' + HERE.name + '/assignment.json',
                           'sha256': sha(assignment)}],
              'generator': {'source': 'work/' + HERE.name + '/' + destination.name,
                            'sha256': sha(destination)}}
    (HERE / 'selected-diagnostic-condition_c-recipe.json').write_text(
        json.dumps(recipe, indent=2) + '\n')
    contract = json.loads((HERE / 'draft-candidates/condition_a/measurement-contract.json').read_text())
    contract['case_id'] = HERE.name + '__control'
    contract_path = HERE / 'cases/condition_c/measurement-contract.json'
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(json.dumps(contract, indent=2) + '\n')
    print(json.dumps({'fixture_size': destination.stat().st_size, 'sha256': sha(destination),
                      'recipe': recipe['generator']['source']}))


if __name__ == '__main__':
    build()
