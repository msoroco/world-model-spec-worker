"""Mirror unselected 3 s/5 s packages for isolated compatibility proofs."""
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
STAGE = REPO / '.runtime-work/c109749-hazard-release-stage-v2'
SEMANTIC_STAGE = REPO / '.runtime-work/c109749-hazard-release-semantic-v3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def release_proposal(far, entry):
    """Keep the recorded observations fixed and vary the authored controller only."""
    proposal = copy.deepcopy(far)
    proposal['case_id'] = entry['case_id']
    suffix = entry['case_id'].split('__')[-1]
    setting = 3.0 if suffix == 'approaching_release_3s' else 5.0
    assert suffix in ('approaching_release_3s', 'approaching_release_5s')
    proposal['variable_assignments']['controller_release_ttc_s']['value'] = setting
    proposal['variable_assignments']['subject_yield_policy']['value'] = setting == 5.0
    proposal['rationale'] = (
        f'Authored {setting:g} s engineering release setting with a source-measured '
        'turn or yield sequence; Native motion and legal immediate hazard unverified.')
    proposal['paired_probe_id'] = 'c109749-far-approach-engineering-sweep'
    proposal['deliberate_differences'] = (['controller_release_ttc_s', 'subject_yield_policy']
                                          if setting == 5.0 else ['controller_release_ttc_s'])
    proposal['probe'] = {
        'primary_variable': 'controller_release_ttc_s',
        'comparison_or_standard': '3, 4 and 5 s authored controller settings; no legal hazard threshold',
        'target_value_or_branch': f'{setting:g} s engineering release setting',
    }
    return proposal


def verify_release_binding(proposal, entry):
    construction = json.loads((ROOT / entry['construction']).read_text())
    config_file = next(item for item in construction['files'] if item['path'] == 'config.json')
    config = json.loads(config_file['content'])
    expected = proposal['variable_assignments']['controller_release_ttc_s']['value']
    assert config['selected_case_id'] == proposal['case_id'] == entry['case_id']
    assert config['controller_release_ttc_s'] == expected
    assert proposal['variable_assignments']['subject_yield_policy']['value'] == (expected == 5.0)


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
        proposal = release_proposal(far, entry)
        verify_release_binding(proposal, entry)
        proposals['cases'].append(proposal)
    shutil.copytree(ROOT / 'cases/approaching_far', target / 'cases/approaching_far',
                    ignore=shutil.ignore_patterns('*.log', '*.pyc', '__pycache__'))
    shutil.copytree(ROOT / 'cases/approaching_yield', target / 'cases/approaching_yield',
                    ignore=shutil.ignore_patterns('*.log', '*.pyc', '__pycache__'))
    write(target / 'case-plan.json', plan)
    write(target / 'proposals/cases.json', proposals)
    write(target / 'hazard-release-draft-manifest.json', draft)
    return str(target / 'hazard-release-draft-manifest.json')


def semantic_preview():
    """Validate the prospective 3/4/5 s semantic chain without selecting drafts."""
    if SEMANTIC_STAGE.exists():
        raise ValueError('Use a fresh isolated semantic stage')
    target = SEMANTIC_STAGE / 'work' / ROOT.name
    shutil.copytree(ROOT / 'proposals', target / 'proposals')
    selected = json.loads((ROOT / 'execution-manifest.json').read_text())
    draft = json.loads((ROOT / 'hazard-release-draft-manifest.json').read_text())
    proposal_path = target / 'proposals/cases.json'
    proposals = json.loads(proposal_path.read_text())
    far = next(row for row in proposals['cases'] if row['case_id'].endswith('__approaching_far'))
    for entry in [*selected['cases'], *draft['cases']]:
        source = ROOT / entry['construction']
        dest = target / entry['construction']
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        assert sha(dest) == entry['construction_sha256']
    for entry in draft['cases']:
        proposal = release_proposal(far, entry)
        verify_release_binding(proposal, entry)
        proposals['cases'].append(proposal)
        selected['cases'].append(entry)
    write(proposal_path, proposals)
    index_path = target / 'proposals/semantic-index.json'
    index = json.loads(index_path.read_text())
    index['stages']['cases']['sha256'] = sha(proposal_path)
    write(index_path, index)
    sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
    sys.path.insert(1, str(REPO / 'runtime/python'))
    from worker_exchange.semantic_delivery import validate
    assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
    result = validate(target, assignment, selected)
    assert result['selected_cases'] == 16
    return {'semantic_validation': result,
            'release_cases': [
                {'case_id': e['case_id'],
                 'release_ttc_s': next(p for p in proposals['cases']
                                       if p['case_id'] == e['case_id'])
                                      ['variable_assignments']['controller_release_ttc_s']['value'],
                 'construction_sha256': e['construction_sha256']}
                for e in draft['cases']],
            'canonical_selection_changed': False,
            'native_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(semantic_preview(), indent=2) if '--semantic-preview' in sys.argv else stage())
