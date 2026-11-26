"""Check this fixed business right-turn branch against frozen source and delegations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = FOLDER.parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    source = ROOT / 'inputs' / FOLDER.name
    assignment = read(source / 'assignment.json')
    witnesses = read(source / 'witnesses.json')
    plan = read(FOLDER / 'case-plan.json')
    manifest = read(FOLDER / 'execution-manifest.json')
    text = plan['source_law']['text']
    if assignment['cell']['layout'] != 'business_district' or assignment['cell']['maneuver'] != 'right_turn' or assignment['cell']['control'] != 'other_vehicle':
        raise ValueError('Fixed source cell differs')
    if not all(clause in text for clause in ('turn right or left', 'otherwise turn', '100 feet', '300 feet', 'regardless of the weather')):
        raise ValueError('Statutory alternatives or weather clause omitted')
    topics = {item['topic_id']: item for item in plan['source_topic_inventory']}
    if set(topics) != {'text-0', 'text-1', 'reviewed-scope-0', 'reviewed-scope-1'}:
        raise ValueError('Frozen source topic omitted')
    if not any('300 feet of frontage within a 600-foot highway interval' in item for witness in witnesses if isinstance(witness, dict) for item in witness.get('witness', {}).get('required_context', [])):
        raise ValueError('Business district frontage source omitted')
    cases = {item['case_id'] for item in plan['cases']}
    if cases != {item['case_id'] for item in manifest['cases']} or len(cases) != 3:
        raise ValueError('Selected exact cases differ')
    if len(plan['comparisons']) != 1 or set(plan['comparisons'][0]['case_ids']) != cases:
        raise ValueError('Selected comparison is incomplete')
    if any(item['status'] != 'selected_required' or set(item['case_ids']) != cases for item in plan['requirement_dispositions']):
        raise ValueError('Selected statutory dispositions differ')
    delegation = plan['separate_area_branch_delegation']
    if delegation['source_topic_ids'] != ['text-0'] or delegation['status'] != 'delegated_not_claimed_by_this_business_district_package':
        raise ValueError('Other-area alternative is not explicitly delegated')
    delegated = {}
    for key in ('any_other_area_300_foot', 'alternate_cell_300_foot'):
        target = delegation[key]
        other = ROOT / 'work' / target['assignment_id'] / 'case-plan.json'
        other_plan = read(other)
        other_cases = {item['case_id'] for item in other_plan['cases']}
        if not set(target['case_ids']) <= other_cases or len(target['case_ids']) < 2 or other_plan['law_id'] != plan['law_id']:
            raise ValueError('Delegated same-law cases missing: ' + key)
        delegated[key] = {'assignment_id': target['assignment_id'],
                          'case_ids': target['case_ids'], 'case_plan_sha256': sha(other)}
    maneuver = plan['separate_maneuver_branch_delegation']
    if maneuver['source_topic_ids'] != ['text-0'] or maneuver['fixed_case_maneuver'] != 'right_turn' or \
            maneuver['source_alternatives'] != ['turn right', 'turn left', 'otherwise turn a vehicle from a direct course']:
        raise ValueError('Statutory maneuver alternatives omitted')
    left_plan = ROOT / 'work' / maneuver['left_turn_same_law_assignment_id'] / 'case-plan.json'
    if not set(maneuver['left_turn_case_ids']) <= {item['case_id'] for item in read(left_plan)['cases']}:
        raise ValueError('Delegated left-turn cases missing')
    return {'format': 'c42387-business-source-branch-audit-v1',
            'assignment_id': FOLDER.name, 'assignment_sha256': sha(source / 'assignment.json'),
            'witnesses_sha256': sha(source / 'witnesses.json'),
            'case_plan_sha256': sha(FOLDER / 'case-plan.json'),
            'selected_case_ids': sorted(cases), 'other_area_delegations': delegated,
            'left_turn_delegation_sha256': sha(left_plan),
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
