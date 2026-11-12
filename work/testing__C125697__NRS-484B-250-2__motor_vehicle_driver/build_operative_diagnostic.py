"""Build source-shaped Red/Green diagnostic for the operative-device case."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'cases/operative_signal'
CASE = HERE.name + '__operative_signal'


def lines(rows):
    return ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows)


def build():
    spec = json.loads((HERE / 'diagnostic.json').read_text())
    files = spec['files']
    rows = [json.loads(line) for line in files['crossing_history.jsonl'].splitlines()]
    for row in rows:
        if [head['actor_id'] for head in row['entrance_signal_states']] != [17, 18]:
            raise ValueError('Two stable synthetic head identities required')
        row['governing_signal_state'] = 'Red'
        row['entrance_signal_states'][0]['state'] = 'Red'
        row['entrance_signal_states'][1]['state'] = 'Green'
    files['crossing_history.jsonl'] = lines(rows)
    context = json.loads(files['junction_context.json'])
    context['official_device_operating'] = True
    files['junction_context.json'] = json.dumps(context, allow_nan=False) + '\n'
    spec['graphs'] = []
    OUT.mkdir(parents=True, exist_ok=True)
    diagnostic = OUT / 'diagnostic.json'
    diagnostic.write_text(json.dumps(spec, indent=2, allow_nan=False) + '\n')
    source = str(diagnostic.relative_to(HERE.parents[1]))
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': source, 'sha256': ''}],
              'generator': {'source': source, 'sha256': ''}}
    (OUT / 'diagnostic-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    module_spec = importlib.util.spec_from_file_location('augment_operative',
                                                        HERE / 'augment_diagnostic_capture.py')
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    module.HERE = OUT
    module.CASE = CASE
    generated = module.build()
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if not any(CASE in row.get('case_ids', []) for row in plan['requirement_dispositions']):
        for original in plan['requirement_dispositions'][:6]:
            row = copy.deepcopy(original)
            row['case_ids'] = [CASE]
            if row['requirement'].startswith('All entrance heads are Off'):
                row['requirement'] = ('All inventoried entrance heads are operative Red/Green while '
                                      'official-device and subsection-4 qualification remain open')
                row['evidence_or_gap'] = ('Synthetic original-frame Red/Green readbacks are retained; '
                                          'physical operation, device authority and subsection-4 remain open.')
            plan['requirement_dispositions'].append(row)
        plan_path.write_text(json.dumps(plan, indent=2, allow_nan=False) + '\n')
    contract = json.loads((HERE / 'measurement-contract.json').read_text())
    for index, row in enumerate(contract['requirements']):
        row['disposition_index'] = index + 18
        if row['requirement'].startswith('All entrance heads are Off'):
            row['requirement'] = ('All inventoried entrance heads are operative Red/Green while '
                                  'official-device and subsection-4 qualification remain open')
    (OUT / 'measurement-contract.json').write_text(json.dumps(contract, indent=2, allow_nan=False) + '\n')
    proposal_path = HERE / 'proposals/cases.json'
    proposals = json.loads(proposal_path.read_text())
    if not any(row['case_id'] == CASE for row in proposals['cases']):
        proposal = copy.deepcopy(proposals['cases'][0])
        proposal['case_id'] = CASE
        proposal['rationale'] = ('Operative Red/Green device comparison at the same synthetic crossing; '
                                 'physical device authority unverified')
        proposal['variable_assignments']['official_device_status']['value'] = (
            'Operative ego Red / other Green commanded; physical state unverified')
        proposal['paired_probe_id'] = 'c125697-device-state'
        proposal['deliberate_differences'] = ['operative Red/Green rather than all-Off entrance signal state']
        proposal['probe']['target_value_or_branch'] = 'operative_signal'
        proposals['cases'].append(proposal)
        proposal_path.write_text(json.dumps(proposals, indent=2, allow_nan=False) + '\n')
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    if entry.get('compatibility'):
        raise ValueError('Operative compatibility already bound; retain proof')
    entry['fixture_recipe'] = str((OUT / 'diagnostic-recipe.json').relative_to(HERE.parents[1]))
    entry['acquisition'] = manifest['cases'][0]['acquisition']
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return {'case_id': CASE, **generated}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
