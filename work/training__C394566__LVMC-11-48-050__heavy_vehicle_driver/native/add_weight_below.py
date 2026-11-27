"""Add the source-bound below/at/above statutory weight boundary probe."""
import copy
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
AID = FOLDER.name
OLD = AID + '__weight_8000'
NEW = AID + '__weight_below_8000'


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


def main():
    plan_path = FOLDER / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if any(c['case_id'] == NEW for c in plan['cases']):
        raise ValueError('Weight-below case already exists')
    at_index = next(i for i, c in enumerate(plan['cases']) if c['case_id'] == OLD)
    below = copy.deepcopy(plan['cases'][at_index])
    below.update(case_id=NEW, requested_setting='weight_below_8000',
                 comparison_variable='certified unladen weight below, at and above 8000 lb',
                 case_description='Source-governed C394566 street travel; measure certified unladen weight below the exact 8000 lb threshold, holding other cited factors fixed. No authority or legal outcome is asserted.')
    for case in plan['cases']:
        if case['case_id'] in (OLD, AID + '__weight_above_8000'):
            case['comparison_variable'] = below['comparison_variable']
    plan['cases'].insert(at_index, below)
    comparison = next(c for c in plan['comparisons'] if c['comparison_id'].endswith('__weight_comparison'))
    comparison['case_ids'].insert(0, NEW)
    comparison['deliberate_differences'] = [below['comparison_variable']]
    for disposition in plan['requirement_dispositions']:
        if OLD in disposition.get('case_ids', []):
            disposition['case_ids'].insert(disposition['case_ids'].index(OLD), NEW)
    write(plan_path, plan)

    proposal_path = FOLDER / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    index = next(i for i, c in enumerate(proposal['cases']) if c['case_id'] == OLD)
    proposed = copy.deepcopy(proposal['cases'][index])
    proposed['case_id'] = NEW
    proposed['rationale'] = below['case_description']
    proposed['variable_assignments'] = {below['comparison_variable']: {
        'kind': 'source_context', 'unit': 'lb', 'value': 7999}}
    proposal['cases'].insert(index, proposed)
    write(proposal_path, proposal)

    contract = json.loads((FOLDER / 'measurement-weight_8000.json').read_text())
    contract['case_id'] = NEW
    write(FOLDER / 'measurement-weight_below_8000.json', contract)
    print(json.dumps({'cases': len(plan['cases']), 'weight_comparison': comparison['case_ids']}))


if __name__ == '__main__':
    main()
