"""Exercise the pinned semantic validator with source-hashed positive and negative inputs."""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'runtime/pipeline'), str(ROOT / 'runtime/pipeline/scenario_pipeline')]
from scenario_pipeline.worker_exchange.semantic_delivery import validate


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def reject(folder, assignment, manifest, expected):
    try:
        validate(folder, assignment, manifest)
    except ValueError as exc:
        if expected not in str(exc):
            raise AssertionError(f'Expected {expected!r}, got {exc!s}') from exc
        return str(exc)
    raise AssertionError(f'Expected rejection: {expected}')


assignment = read(ROOT / 'inputs' / HERE.name / 'assignment.json')
assignment['law'] = assignment['law_record']
manifest = read(HERE / 'execution-manifest.json')
positive = validate(HERE, assignment, manifest)
with tempfile.TemporaryDirectory(prefix='c104538-semantic-') as directory:
    folder = Path(directory)
    shutil.copytree(HERE / 'proposals', folder / 'proposals')
    for entry in manifest['cases']:
        source = HERE / entry['construction']
        target = folder / entry['construction']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    assert validate(folder, assignment, manifest)['selected_cases'] == 3
    template = folder / 'proposals/template.json'
    template.write_text(template.read_text() + '\n')
    stale_hash = reject(folder, assignment, manifest, 'Stage proposal source hash changed')
    write(template, read(HERE / 'proposals/template.json'))
    cases_path = folder / 'proposals/cases.json'
    cases = read(cases_path)
    cases['cases'][1]['recording_description']['limitations'].append('tampered description')
    write(cases_path, cases)
    index_path = folder / 'proposals/semantic-index.json'
    index = read(index_path)
    index['stages']['cases']['sha256'] = hashlib.sha256(cases_path.read_bytes()).hexdigest()
    write(index_path, index)
    changed_capture = reject(folder, assignment, manifest, 'Sweep recording description changed')

proof = {'format': 'c104538-semantic-delivery-cpu-proof-v1',
         'positive': positive,
         'negative': {'stale_source_hash': stale_hash,
                      'changed_capture_contract': changed_capture},
         'scope': 'CPU semantic stage and selected-case contract validation; no local adoption or Native acceptance'}
write(HERE / 'update022-semantic-delivery-proof.json', proof)
print(json.dumps(proof, sort_keys=True))
