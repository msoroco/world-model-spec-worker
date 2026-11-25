"""Bind unselected 30-second construction to public diagnostic recipes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = json.loads((HERE / 'extended-primary/manifest.json').read_text())
    old = json.loads((HERE / 'native/measurement-contract.json').read_text())
    old['format'] = 'worker-measurement-contract'
    contract = HERE / 'extended-primary/measurement-contract.json'
    contract.write_text(json.dumps(old, indent=2) + '\n')
    cases = []
    for row in source['cases']:
        case = row['case_id'].rsplit('__', 1)[1]
        item = {key: row[key] for key in ('case_id', 'id', 'construction',
                                          'construction_sha256', 'candidates', 'candidate_risk')}
        item.update(kind='draft_not_selected', measurement_contract='extended-primary/measurement-contract.json',
                    measurement_procedure={'entrypoint': 'finalize.py',
                                           'output_schema': 'c422978-sidewalk-analysis-v1'},
                    fixture_recipe=(HERE / 'extended-primary' / (case + '-recipe.json')).relative_to(ROOT).as_posix())
        item['construction'] = 'extended-primary/' + item['construction']
        for candidate in item['candidates']:
            candidate['construction'] = 'extended-primary/' + candidate['construction']
        cases.append(item)
    manifest = {'format': 'worker-unselected-draft-compatibility-manifest-v1',
                'assignment_id': AID, 'status': 'draft_not_selected',
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'cases': cases, 'delivery_ready': False}
    target = HERE / 'current-30s-compatibility-manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(target),
                      'measurement_contract_sha256': sha(contract)}))


if __name__ == '__main__':
    main()
