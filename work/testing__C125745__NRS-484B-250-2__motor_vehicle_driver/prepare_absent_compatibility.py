"""Stage the absent-device case beside ignored CPU compatibility outputs."""
import copy
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__stop_ego_left_near_time_no_device'


def emit(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def stage(output):
    output = Path(output).resolve()
    if output.parent != (ROOT / '.runtime-work').resolve():
        raise ValueError('Stage package must be one directory below .runtime-work')
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((HERE / 'absent-execution-manifest.json').read_text())
    manifest['cases'] = [row for row in manifest['cases'] if row['case_id'] == CASE]
    if len(manifest['cases']) != 1:
        raise ValueError('One exact absent-device case required')
    emit(output / 'execution-manifest.json', manifest)
    for name in ('absent-construction.json', 'measurement-contract.json'):
        shutil.copyfile(HERE / name, output / name)
    plan = json.loads((HERE / 'case-plan.json').read_text())
    for row in plan['requirement_dispositions']:
        if row['status'] == 'selected_required' and CASE not in row['case_ids']:
            row['case_ids'].append(CASE)
    plan['cases'].append({'case_id': CASE, 'target_law_id': 'NRS-484B-250-2',
                          'purpose': 'Same median crossing with no Native entrance device',
                          'physical_risk': 'Native absence unverified'})
    emit(output / 'case-plan.json', plan)
    proposals = json.loads((HERE / 'proposals/cases.json').read_text())
    original = next(row for row in proposals['cases']
                    if row['case_id'].endswith('stop_ego_left_near_time'))
    absent = copy.deepcopy(original)
    absent['case_id'] = CASE
    absent['rationale'] = ('Synthetic absent-device diagnostic; Native and official '
                           'status unverified')
    values = absent['variable_assignments']
    values['official_device_status']['value'] = 'no Native entrance device; official status unverified'
    values['native_stop_sign_id']['value'] = None
    proposals['cases'] = [absent]
    emit(output / 'proposals/cases.json', proposals)
    return {'case_id': CASE, 'manifest': str(output / 'execution-manifest.json'),
            'canonical_manifest_unchanged': True}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.output), sort_keys=True))
