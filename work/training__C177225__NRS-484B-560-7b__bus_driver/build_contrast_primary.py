"""Build the paired contrast from the current reference implementation."""
import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT / 'constructions' / 'reference-primary.json'
CONTRAST = ROOT / 'constructions' / 'contrast-primary.json'
REFERENCE_CONTRACT = ROOT / 'constructions' / 'reference-measurement-contract.json'
CONTRAST_CONTRACT = ROOT / 'constructions' / 'contrast-measurement-contract.json'
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    construction = copy.deepcopy(json.loads(REFERENCE.read_text()))
    case_id = construction['case_id'].removesuffix('__reference') + '__contrast'
    construction['case_id'] = case_id
    files = {item['path']: item for item in construction['files']}
    config = json.loads(files['config.json']['content'])
    config.update(case_id=case_id, selected_case_id=case_id,
                  case_suffix='contrast', comparison_requested_value=False)
    files['config.json']['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
    write(CONTRAST, construction)
    contract = json.loads(REFERENCE_CONTRACT.read_text())
    contract['case_id'] = case_id
    write(CONTRAST_CONTRACT, contract)
    manifest = json.loads(MANIFEST.read_text())
    if any(entry['case_id'] == case_id for entry in manifest['cases']):
        raise ValueError('Retain prior contrast entry; do not overwrite receipts')
    manifest['cases'].append({
        'case_id': case_id, 'kind': 'delivery',
        'candidate_risk': {'status': 'physical',
                           'reason': 'Generic rail proxy, officer visibility and continued bus motion need original Native review'},
        'construction': str(CONTRAST.relative_to(ROOT)),
        'construction_sha256': sha(CONTRAST),
        'measurement_contract': str(CONTRAST_CONTRACT.relative_to(ROOT)),
        'fixture_recipe': 'work/' + ROOT.name + '/fixtures/contrast-recipe.json',
        'measurement_procedure': {'entrypoint': 'finalize_direction.py',
                                  'output_schema': 'c177225-saved-analysis-v1'},
        'candidates': []})
    write(MANIFEST, manifest)
    return {'case_id': case_id, 'construction_sha256': sha(CONTRAST)}


if __name__ == '__main__':
    print(json.dumps(build()))
