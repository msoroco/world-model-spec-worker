"""Stage the exact straight case for CPU compatibility without rebinding old cases.

The current C125745 manifest is hash-bound by earlier physical receipts. This
temporary, ignored staging package exercises the new case before the full
canonical proof rebinding. It contains no altered runtime or frozen input.
"""
import copy
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__stop_opposite_straight'


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def stage(output):
    output = Path(output).resolve()
    if output.parent != (ROOT / '.runtime-work').resolve():
        raise ValueError('Stage package must be one directory below .runtime-work')
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((HERE / 'straight-execution-manifest.json').read_text())
    selected = [entry for entry in manifest['cases'] if entry['case_id'] == CASE]
    if len(selected) != 1:
        raise ValueError('One exact straight case required')
    manifest['cases'] = selected
    write(output / 'execution-manifest.json', manifest)
    shutil.copyfile(HERE / 'straight-construction.json',
                    output / 'straight-construction.json')
    shutil.copyfile(HERE / 'measurement-contract.json',
                    output / 'measurement-contract.json')
    plan = json.loads((HERE / 'case-plan.json').read_text())
    for row in plan['requirement_dispositions']:
        if row['status'] == 'selected_required' and CASE not in row['case_ids']:
            row['case_ids'].append(CASE)
    if not any(row['case_id'] == CASE for row in plan['cases']):
        plan['cases'].append({
            'case_id': CASE, 'target_law_id': 'NRS-484B-250-2',
            'purpose': 'Opposite straight-intent controlled comparison',
            'physical_risk': 'Original Native motion unverified'})
    write(output / 'case-plan.json', plan)
    proposals = json.loads((HERE / 'proposals/cases.json').read_text())
    left = next(row for row in proposals['cases']
                if row['case_id'].endswith('stop_opposite_left_turn'))
    straight = copy.deepcopy(left)
    straight['case_id'] = CASE
    straight['rationale'] = ('Synthetic opposite straight-intent diagnostic; '
                             'physical and legal qualification unresolved')
    values = straight['variable_assignments']
    values['opposite_direction_left_turn']['value'] = 'other_straight_intended'
    values['commanded_turn_path']['value'] = 'opposite_straight_waypoints'
    proposals['cases'] = [straight]
    (output / 'proposals').mkdir(exist_ok=True)
    write(output / 'proposals/cases.json', proposals)
    return {'case_id': CASE, 'manifest': str(output / 'execution-manifest.json'),
            'canonical_manifest_unchanged': True,
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.output), sort_keys=True))
