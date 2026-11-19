"""Add the paving employee activity comparison to the work-owned draft plan."""
import json
from build_variant_exact import PACKAGE
from variant_recording_contract import ASSIGNMENT, config


def write():
    plan_path = PACKAGE / 'case-plan.json'
    proposal_path = PACKAGE / 'proposals/cases.json'
    plan = json.loads(plan_path.read_text())
    proposal = json.loads(proposal_path.read_text())
    cfgs = [config('employee_exception', route, 600)
            for route in ('employee_crossing', 'nonemployee_crossing')]
    for cfg in cfgs:
        case_id, route = cfg['case_id'], cfg['case_suffix']
        if not any(row['case_id'] == case_id for row in plan['cases']):
            plan['cases'].append({
                'case_id': case_id, 'target_law_id': cfg['law_id'],
                'planning_status': 'unverified_definition', 'target_type': 'attempt',
                'comparison_variable': 'operator_actually_engaged_in_paving_or_repair',
                'comparison_unit': 'bool', 'requested_setting': route,
                'recorded_value': None,
                'case_description': 'same surveyed pavement crossing with independently sourced employee versus nonemployee activity',
                'fixed_context': 'Hold pavement, route, actor type, warning control, weather, cameras and controller fixed; verify actual activity from original sources.',
                'source_topic_ids': ['text-0', 'text-1']})
        if not any(row['case_id'] == case_id for row in proposal['cases']):
            proposal['cases'].append({
                'case_id': case_id, 'target_law_id': cfg['law_id'],
                'target_type': 'attempt', 'recording_description': cfg['recording_description'],
                'rationale': 'Request crossing with ' + route.replace('_', ' ') + ' source context.',
                'unresolved_judgment_calls': ['whether the operator is actually engaged in paving or repair',
                                              'whether the pavement was newly laid or repaired',
                                              'whether a statutory warning was present'],
                'variable_assignments': {
                    'requested_pavement_crossing': {'kind': 'controller', 'value': True},
                    'operator_actually_engaged_in_paving_or_repair': {'kind': 'world_setup',
                        'value': 'independent original activity source required'},
                    'actual_body_contact': {'kind': 'subject_behavior', 'value': None}}})
        for disposition in plan['requirement_dispositions'][:2]:
            if case_id not in disposition['case_ids']:
                disposition['case_ids'].append(case_id)
    if 'Paving employee exception' not in plan['scope_branches']:
        plan['scope_branches'].append('Paving employee exception')
    comparison_id = ASSIGNMENT + '__comparison_employee_exception'
    if not any(row['comparison_id'] == comparison_id for row in plan['comparisons']):
        plan['comparisons'].append({
            'comparison_id': comparison_id, 'case_ids': [cfg['case_id'] for cfg in cfgs],
            'deliberate_differences': ['operator_actually_engaged_in_paving_or_repair'],
            'fixed_conditions': ['cell', 'actor', 'surveyed pavement', 'crossing route',
                                 'warning control', 'weather', 'controller settings',
                                 'camera and capture profile'],
            'status': 'planned_unverified'})
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    proposal_path.write_text(json.dumps(proposal, indent=2) + '\n')


if __name__ == '__main__':
    write()
