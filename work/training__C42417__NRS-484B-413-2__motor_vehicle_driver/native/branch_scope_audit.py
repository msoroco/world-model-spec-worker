"""Audit C42417 business-district scope against the separate area branches."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
ROOT = FOLDER.parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    plan = read(FOLDER / 'case-plan.json')
    assignment = read(ROOT / 'inputs' / FOLDER.name / 'assignment.json')
    matrix = read(ROOT / 'work/_shared/branch-coverage.json')
    manifest = read(FOLDER / 'execution-manifest.json')
    topics = {item['topic_id']: item for item in plan['source_topic_inventory']}
    if set(topics) != {'text-0', 'text-1', 'reviewed-scope-0', 'reviewed-scope-1'}:
        raise ValueError('Original source topics omitted')
    if '100 feet' not in plan['source_law']['text'] or '300 feet' not in plan['source_law']['text']:
        raise ValueError('Statutory area distinction lost')
    if assignment['cell']['layout'] != 'business_district':
        raise ValueError('C42417 is not the fixed business-district cell')
    ids = {case['case_id'] for case in plan['cases']}
    if ids != {entry['case_id'] for entry in manifest['cases']} or len(ids) != 3:
        raise ValueError('Selected cases and manifest differ')
    comparison = plan['comparisons']
    if len(comparison) != 1 or set(comparison[0]['case_ids']) != ids:
        raise ValueError('Business-distance comparison does not cover all cases')
    if not all(disposition['status'] == 'selected_required' and
               set(disposition['case_ids']) == ids for disposition in plan['requirement_dispositions']):
        raise ValueError('Selected business requirements are not fully assigned')
    delegation = plan['separate_area_branch_delegation']
    if set(delegation['source_topic_ids']) != {'reviewed-scope-0', 'reviewed-scope-1'}:
        raise ValueError('300-foot reviewed topics were not retained')
    branches = matrix['laws'][plan['law_id']]['branches']
    for key in ('any_other_area_300_foot', 'alternate_cell_300_foot'):
        target = delegation[key]
        other = ROOT / 'work' / target['assignment_id'] / 'case-plan.json'
        other_plan = read(other)
        other_ids = {case['case_id'] for case in other_plan['cases']}
        if not set(target['case_ids']) <= other_ids or len(target['case_ids']) < 2:
            raise ValueError('Delegated 300-foot cases are not planned')
        matching = [branch for branch in branches if branch.get('assignment_id') == target['assignment_id']
                    and set(target['case_ids']) <= set(branch.get('case_ids', []))
                    and {'reviewed-scope-0', 'reviewed-scope-1'} <= set(branch.get('topic_ids', []))]
        if not matching:
            raise ValueError('Delegated 300-foot branch absent from shared source inventory')
    if any('300' in case_id for case_id in ids):
        raise ValueError('Business cases imply another area threshold')
    return {'format':'c42417-business-branch-scope-audit-v1',
            'assignment_id':FOLDER.name,'source_sha256':sha(ROOT/'inputs'/FOLDER.name/'assignment.json'),
            'case_plan_sha256':sha(FOLDER/'case-plan.json'),
            'selected_business_case_ids':sorted(ids),
            'delegated_any_other_area_case_ids':delegation['any_other_area_300_foot']['case_ids'],
            'delegated_alternate_cell_case_ids':delegation['alternate_cell_300_foot']['case_ids'],
            'physical_or_legal_acceptance_claimed':False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
