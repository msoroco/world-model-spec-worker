"""Bind the retained source finalizer and Native runner to the exact contrast case."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name+'__contrast'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')


def build():
    plan = json.loads((HERE/'case-plan.json').read_text())
    reference = json.loads((HERE/'draft-reference-manifest.json').read_text())
    entry = copy.deepcopy(reference['cases'][0])
    primary = json.loads((HERE/entry['construction']).read_text())
    if sha(HERE/entry['construction']) != entry['construction_sha256']:
        raise ValueError('Reference construction hash differs')
    primary['case_id'] = CASE
    primary['measurement_plan']['per_case_contracts'][0]['case_id'] = CASE
    primary['static_checks'] = [item.replace('reference', 'contrast') for item in primary['static_checks']]
    config_file = next(item for item in primary['files'] if item['path'] == 'config.json')
    config = json.loads(config_file['content'])
    config.update(case_id=CASE, selected_case_id=CASE, case_suffix='contrast',
                  comparison_requested_value=False)
    config_file['content'] = json.dumps(config, sort_keys=True, indent=2)+'\n'
    construction = HERE/'draft-contrast-construction.json'
    write(construction, primary)
    contract = json.loads((HERE/'draft-reference-measurement-contract.json').read_text())
    contract['case_id'] = CASE
    write(HERE/'draft-contrast-measurement-contract.json', contract)
    entry.update(case_id=CASE, construction=construction.name,
                 construction_sha256=sha(construction),
                 measurement_contract='draft-contrast-measurement-contract.json',
                 fixture_recipe=str((HERE/'draft-contrast-diagnostic-recipe.json').relative_to(ROOT)))
    reference['cases'] = [entry]
    write(HERE/'draft-contrast-manifest.json', reference)
    proposal = copy.deepcopy(next(row for row in plan['cases'] if row['case_id'] == CASE))
    proposal['recording_description'] = config['recording_description']
    proposal['variable_assignments'] = {}
    proposals_path = HERE/'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    proposals['cases'] = [row for row in proposals['cases'] if row['case_id'] != CASE] + [proposal]
    write(proposals_path, proposals)
    return {'construction_sha256': sha(construction),
            'manifest_sha256': sha(HERE/'draft-contrast-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
