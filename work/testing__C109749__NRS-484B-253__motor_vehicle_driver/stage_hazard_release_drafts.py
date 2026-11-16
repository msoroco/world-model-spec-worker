"""Mirror unselected 3 s/5 s packages for isolated compatibility proofs."""
import copy
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
STAGE = REPO / '.runtime-work/c109749-hazard-release-stage-v2'


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def stage():
    if STAGE.exists():
        raise ValueError('Use a fresh isolated stage')
    target = STAGE / 'work' / ROOT.name
    draft = json.loads((ROOT / 'hazard-release-draft-manifest.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    proposals = json.loads((ROOT / 'proposals/cases.json').read_text())
    far = next(row for row in proposals['cases'] if row['case_id'].endswith('__approaching_far'))
    for entry in draft['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        source = ROOT / 'cases' / suffix
        dest = target / 'cases' / suffix
        dest.mkdir(parents=True)
        for bundle in source.glob('*construction.json'):
            shutil.copy2(bundle, dest / bundle.name)
        contract = ROOT / ('cases/approaching_yield/measurement-contract.json'
                           if suffix == 'approaching_release_5s'
                           else 'cases/approaching_far/measurement-contract.json')
        shutil.copy2(contract, dest / contract.name)
        entry['measurement_contract'] = 'cases/' + suffix + '/measurement-contract.json'
        recipe_case = ('approaching_yield' if suffix == 'approaching_release_5s'
                       else 'approaching_far')
        entry['fixture_recipe'] = 'work/' + ROOT.name + '/cases/' + recipe_case + '/diagnostic-recipe.json'
        plan['cases'].append({'case_id': case, 'target_law_id': 'NRS-484B-253',
                              'gap_ids': ['gap-conditional-branch'], 'status': 'draft_offline_branch',
                              'objective': 'Measure release-policy behavior at an engineering TTC setting.'})
        for requirement in plan['requirement_dispositions']:
            if requirement.get('status') == 'selected_required':
                requirement.setdefault('case_ids', []).append(case)
        proposal = copy.deepcopy(far)
        proposal['case_id'] = case
        proposal['rationale'] = 'Diagnostic engineering release setting; Native motion and legal immediate hazard unverified.'
        proposals['cases'].append(proposal)
    shutil.copytree(ROOT / 'cases/approaching_far', target / 'cases/approaching_far',
                    ignore=shutil.ignore_patterns('*.log', '*.pyc', '__pycache__'))
    shutil.copytree(ROOT / 'cases/approaching_yield', target / 'cases/approaching_yield',
                    ignore=shutil.ignore_patterns('*.log', '*.pyc', '__pycache__'))
    write(target / 'case-plan.json', plan)
    write(target / 'proposals/cases.json', proposals)
    write(target / 'hazard-release-draft-manifest.json', draft)
    return str(target / 'hazard-release-draft-manifest.json')


if __name__ == '__main__':
    print(stage())
