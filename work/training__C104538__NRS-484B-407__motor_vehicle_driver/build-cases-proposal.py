"""Materialize an unselected canonical-shape cases proposal from the case plan."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    by_case = {entry['case_id']: entry for entry in manifest['cases']}
    cases = []
    for item in plan['cases']:
        entry = by_case[item['case_id']]
        construction = json.loads((HERE / entry['construction']).read_text())
        cases.append({'case_id': item['case_id'], 'target_law_id': plan['law_id'],
            'target_type': item['target_type'],
            'rationale': 'Unselected authored curve/crest and 500-foot sightline boundary probe; '
                         'Native and original pixels still unverified.',
            'variable_assignments': {
                'authored_sightline_limit_ft': {'kind': 'environment',
                    'value': item['requested_setting'], 'unit': 'ft'},
                'observed_two_direction_body_visibility': {'kind': 'subject_behavior',
                    'value': None, 'unit': 'boolean'}},
            'unresolved_judgment_calls': [
                'Driver-eye/body visibility from both approaches requires original Native pixels',
                'No universal legal threshold is inferred from the authored radius'],
            'recording_description': construction['recording_description']})
    proposal = {'cell_id': plan['cell_id'], 'actor': plan['actor'], 'status': 'draft',
        'cases': cases,
        'sweep_specs': [{'comparison_id': comparison['comparison_id'],
            'case_ids': comparison['case_ids'],
            'variable': 'authored_sightline_limit_ft',
            'values_ft': [next(case['requested_setting'] for case in plan['cases']
                               if case['case_id'] == case_id)
                          for case_id in comparison['case_ids']],
            'status': 'planned_unverified'} for comparison in plan['comparisons']]}
    folder = HERE / 'proposals'
    folder.mkdir(exist_ok=True)
    path = folder / 'cases.json'
    path.write_text(json.dumps(proposal, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'sweeps': len(proposal['sweep_specs']),
                      'status': 'draft'}))


if __name__ == '__main__':
    main()
