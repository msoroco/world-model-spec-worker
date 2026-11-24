"""Bind all three exact cases to one authored intersection and source policy."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    third = json.loads((HERE / 'draft-exact/probe_3/primary/construction.json').read_text())
    manifest = json.loads((HERE / 'v2-three-case-manifest.json').read_text())
    for number, crossing in ((1, 'crosswalk'), (2, 'outside')):
        case_id = HERE.name + f'__probe_{number}'
        construction = json.loads(json.dumps(third))
        construction['case_id'] = case_id
        for file in construction['files']:
            if file['path'] == 'config.json':
                config = json.loads(file['content'])
                config['case_id'] = case_id
                config['selected_case_id'] = case_id
                config['case']['case_id'] = case_id
                config['crossing_case'] = crossing
                file['content'] = json.dumps(config, indent=2) + '\n'
        path = HERE / f'draft-exact/common_intersection/probe_{number}/primary/construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2) + '\n')
        entry = manifest['cases'][number - 1]
        entry['construction'] = str(path.relative_to(HERE))
        entry['construction_sha256'] = sha(path)
        entry['fixture_recipe'] = f'work/{HERE.name}/v2-common{number}-fixture-recipe.json'
        entry['measurement_contract'] = f'v2-common{number}-measurement-contract.json'
        contract = json.loads((HERE / 'v2-probe3-measurement-contract.json').read_text())
        contract['case_id'] = case_id
        (HERE / entry['measurement_contract']).write_text(json.dumps(contract, indent=2) + '\n')
    manifest['status'] = 'partial_common_intersection_cpu'
    (HERE / 'v2-common-intersection-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(HERE / 'v2-common-intersection-manifest.json'),
                      'constructions': [entry['construction_sha256'] for entry in manifest['cases']]}))


if __name__ == '__main__':
    main()
