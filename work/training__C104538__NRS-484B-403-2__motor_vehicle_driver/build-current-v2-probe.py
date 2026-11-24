"""Bind existing source recipes to current unselected public runtime probes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    original = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    cases = []
    for entry in original['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        contract = json.loads((HERE / entry['measurement_contract']).read_text())
        contract['format'] = 'worker-measurement-contract'
        contract['status'] = 'unselected_diagnostic'
        contract_path = HERE / f'current-v2-{case}-measurement-contract.json'
        contract_path.write_text(json.dumps(contract, indent=2) + '\n')
        cases.append({
            'case_id': entry['case_id'],
            'kind': 'draft_not_selected',
            'id': 'primary',
            'construction': entry['construction'],
            'construction_sha256': entry['construction_sha256'],
            'candidate_risk': entry['candidate_risk'],
            'candidates': entry['candidates'],
            'measurement_contract': contract_path.name,
            'measurement_procedure': entry['measurement_procedure'],
            'fixture_recipe': f'work/{HERE.name}/v2-{case}-recipe.json',
        })
    manifest = {
        'format': 'worker-unselected-current-v2-probe-manifest',
        'assignment_id': HERE.name,
        'runtime_manifest_sha256': original['runtime_manifest_sha256'],
        'status': 'draft_not_selected',
        'cases': cases,
    }
    target = HERE / 'current-v2-probe-manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(target),
                      'contracts': {c['case_id']: sha(HERE / c['measurement_contract']) for c in cases}}))


if __name__ == '__main__':
    main()
