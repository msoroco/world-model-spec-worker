"""Bind the eleven proved short exception fixture/contract pairs canonically.

This only selects diagnostic inputs. It does not assert delivery readiness or
carry pilot receipts across the changed manifest.
"""
import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SLUGS = (
    'mail_adjacent_deposit', 'mail_no_box_deposit',
    'mail_adjacent_no_deposit',
    'armored_car_signed_business', 'armored_car_signed_no_business',
    'armored_car_unsigned_business', 'armored_car_unsigned_no_business',
    'emergency_vehicle_signed_business',
    'emergency_vehicle_signed_no_business',
    'emergency_vehicle_unsigned_business',
    'emergency_vehicle_unsigned_no_business',
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    path = ROOT / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    entries = {entry['case_id']: entry for entry in manifest['cases']}
    for slug in SLUGS:
        case_id = ROOT.name + '__' + slug
        entry = entries[case_id]
        contract = Path('selected-measurement-contracts') / (slug + '.json')
        recipe = Path('work') / ROOT.name / 'selected-diagnostics' / slug / 'primary-recipe.json'
        if json.loads((ROOT / contract).read_text())['case_id'] != case_id:
            raise ValueError('Measurement contract selects another case: ' + slug)
        if json.loads((REPO / recipe).read_text())['format'] != 'worker-fixture-recipe':
            raise ValueError('Invalid fixture recipe: ' + slug)
        if entry.get('measurement_contract') or entry.get('fixture_recipe'):
            if (entry.get('measurement_contract'), entry.get('fixture_recipe')) != (str(contract), str(recipe)):
                raise ValueError('Existing binding differs: ' + slug)
        entry['measurement_contract'] = str(contract)
        entry['fixture_recipe'] = str(recipe)
    manifest['status'] = 'selected_short_exception_cpu_proofs_pending'
    manifest['delivery_ready'] = False
    output = args.output.resolve() if args.output else path
    if output.parent != ROOT:
        raise ValueError('Output manifest must remain in the assignment directory')
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'bound_cases': len(SLUGS), 'delivery_ready': False}))


if __name__ == '__main__':
    main()
