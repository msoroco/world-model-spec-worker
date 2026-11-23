"""Bind the second synthetic comparison condition to current saved-source analysis."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def main():
    manifest_path = HERE / 'current-diagnostic-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = manifest['cases'][1]
    case_id = entry['case_id']
    construction = json.loads((HERE / 'draft-candidates/condition_b/primary/construction.json').read_text())
    source = json.loads((HERE / 'current-fixture/condition_a-primary-construction.json').read_text())
    current_finalizer = next(item['content'] for item in source['files'] if item['path'] == 'finalize.py')
    for item in construction['files']:
        if item['path'] == 'finalize.py':
            item['content'] = current_finalizer
    construction_path = HERE / 'current-fixture/condition_b-primary-construction.json'
    write(construction_path, construction)
    contract = json.loads((HERE / 'current-fixture/condition_a-measurement-contract.json').read_text())
    contract['case_id'] = case_id
    contract_path = HERE / 'current-fixture/condition_b-measurement-contract.json'
    write(contract_path, contract)
    entry['construction'] = 'current-fixture/condition_b-primary-construction.json'
    entry['construction_sha256'] = sha(construction_path)
    entry['measurement_contract'] = 'current-fixture/condition_b-measurement-contract.json'
    entry['fixture_recipe'] = 'work/' + HERE.name + '/current-fixture/condition_b-recipe.json'
    write(manifest_path, manifest)
    print(json.dumps({'case_id': case_id, 'construction_sha256': sha(construction_path),
                      'contract_sha256': sha(contract_path),
                      'recipe_sha256': sha(HERE / 'current-fixture/condition_b-recipe.json'),
                      'manifest_sha256': sha(manifest_path)}, sort_keys=True))


if __name__ == '__main__':
    main()
