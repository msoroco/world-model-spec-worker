"""Stage an isolated draft package for exact saved-source compatibility checks.

The canonical manifest and case plan remain unchanged until every exact proof
and comparison for this new branch exists. All staged files are ignored media
work under .runtime-work, and no physical acceptance is asserted.
"""
import argparse
import copy
import json
import shutil
from pathlib import Path

folder = Path(__file__).resolve().parents[2]
repo = folder.parent.parent
draft = Path(__file__).resolve().parent
case = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__inside_yield'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def stage(root):
    if root.exists():
        raise ValueError('Use a fresh ignored draft stage')
    target = root / 'work' / folder.name
    target.mkdir(parents=True)
    bundle = target / 'cases/inside_yield'
    shutil.copytree(draft, bundle, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.log'))
    plan = json.loads((folder / 'case-plan.json').read_text())
    plan['cases'].append({'case_id': case, 'target_law_id': 'NRS-484B-253',
                          'gap_ids': ['gap-conditional-branch'],
                          'status': 'draft_offline_branch',
                          'objective': 'Initial opposing complete body inside sourced junction; subject yields while both bodies overlap, then turns after clearance.'})
    for requirement in plan['requirement_dispositions']:
        if requirement.get('status') == 'selected_required':
            requirement['case_ids'].append(case)
    write(target / 'case-plan.json', plan)
    proposals = target / 'proposals'
    proposals.mkdir()
    cases = json.loads((folder / 'proposals/cases.json').read_text())
    new = copy.deepcopy(next(item for item in cases['cases'] if item['case_id'].endswith('__reciprocal_yield_after_turn')))
    new['case_id'] = case
    new['rationale'] = 'CPU draft: opposing complete body begins within the sourced junction; subject yield and later turn are observed without a legal verdict.'
    new['recording_description'] = json.loads((draft / 'construction.json').read_text())['recording_description']
    cases['cases'].append(new)
    write(proposals / 'cases.json', cases)
    manifest = json.loads((draft / 'draft-manifest.json').read_text())
    manifest['runtime_manifest_sha256'] = json.loads((folder / 'execution-manifest.json').read_text())['runtime_manifest_sha256']
    entry = manifest['cases'][0]
    entry['construction'] = 'cases/inside_yield/construction.json'
    entry['measurement_procedure'] = {'entrypoint': 'finalizer.py'}
    entry['measurement_contract'] = 'cases/inside_yield/measurement-contract.json'
    entry['fixture_recipe'] = 'work/' + folder.name + '/cases/inside_yield/diagnostic-recipe.json'
    for candidate in entry['candidates']:
        candidate['construction'] = 'cases/inside_yield/' + candidate['construction']
    write(target / 'draft-manifest.json', manifest)
    print(json.dumps({'stage_manifest': str(target / 'draft-manifest.json'),
                      'stage_output': str(root / '.runtime-work/inside-yield-primary-compat')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    stage(args.root.resolve())
