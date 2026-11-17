"""Bind the frozen armored clause to saved Native proxy observations."""
import hashlib
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slug', choices=(
        'armored_car_signed_business', 'armored_car_signed_no_business',
        'armored_car_unsigned_business', 'armored_car_unsigned_no_business'),
        default='armored_car_signed_business')
    slug = parser.parse_args().slug
    case_id = ROOT.name + '__' + slug
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    row = plan['requirement_dispositions'][6]
    if row['requirement'] != 'text-6' or case_id not in row['case_ids']:
        raise ValueError('Frozen armored clause selection changed')
    participant = ('native-business-worker-inventory.jsonl' if slug.endswith('_no_business')
                   else 'native-service-worker-actors.jsonl')
    contract = {
        'format': 'worker-measurement-contract', 'case_id': case_id,
        'requirements': [{
            'source': row['source'], 'disposition_index': 6,
            'requirement': 'text-6', 'output_key': 'signed_curb_observation',
            'method': 'signed_context', 'value_type': 'object', 'kind': 'measured',
            'inputs': ['native-raw-actors.jsonl', 'native-map-readback.json',
                       participant]}],
        'negative': {'remove': [participant],
                     'error_contains': 'Missing required source: ' + participant},
        'scope': 'Observed armored visual proxy and business activity; actual armored identity, legal verdict, and physical acceptance unverified'}
    output = ROOT / 'selected-measurement-contracts' / (slug + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + '\n')
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == case_id)
    entry['measurement_contract'] = output.relative_to(ROOT).as_posix()
    entry['fixture_recipe'] = ('work/' + ROOT.name + '/selected-diagnostics/' +
                               slug + '/primary-recipe.json')
    manifest['status'] = 'selected_' + slug + '_cpu_pilot'
    manifest['delivery_ready'] = False
    pilot = ROOT / ('execution-manifest-' + slug.replace('_', '-') + '-pilot.json')
    pilot.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'case_id': case_id, 'contract_sha256': sha(output),
                      'pilot_manifest_sha256': sha(pilot),
                      'delivery_ready': False}))


if __name__ == '__main__':
    main()
