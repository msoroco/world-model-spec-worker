"""Bind all six exact alley cases to the marked diagnostic source recipe."""

import json
from pathlib import Path


root = Path(__file__).resolve().parent
read = lambda path: json.loads(path.read_text())
write = lambda path, value: path.write_text(json.dumps(value, indent=2) + '\n')
primary = read(root / 'construction-probe-manifest.json')
manifest_path = root / 'probe-compatibility-manifest.json'
manifest = read(manifest_path)
first = manifest['cases'][0]
first_contract = read(root / first['measurement_contract'])
entries = {entry['case_id']: entry for entry in manifest['cases']}
for construction in primary['cases']:
    case_id = construction['case_id']
    if case_id in entries:
        continue
    suffix = case_id.split('__')[-1]
    contract = dict(first_contract, case_id=case_id)
    contract_path = root / 'cases' / ('measurement-contract-' + suffix + '.json')
    write(contract_path, contract)
    entries[case_id] = {**construction, 'kind': 'delivery',
        'measurement_contract': str(contract_path.relative_to(root)),
        'measurement_procedure': {'entrypoint': 'alley_finalizer.py'},
        'fixture_recipe': first['fixture_recipe'],
        'acquisition': first['acquisition']}
manifest['cases'] = [entries[construction['case_id']] for construction in primary['cases']]
write(manifest_path, manifest)
print('Bound six exact alley compatibility cases')
