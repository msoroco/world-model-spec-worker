"""Add the two sign control comparisons to the work-owned draft plan."""
import json

from build_variant_exact import PACKAGE
from variant_recording_contract import ASSIGNMENT, config


def write():
    plan_path = PACKAGE / 'case-plan.json'
    proposal_path = PACKAGE / 'proposals/cases.json'
    plan = json.loads(plan_path.read_text())
    proposal = json.loads(proposal_path.read_text())
    for kind, label in (('warning_sign', 'Warning sign'),
                        ('highway_closed_sign', 'Highway closed sign')):
        cfgs = [config(kind, route, 600) for route in ('crossing', 'avoidance')]
        for cfg in cfgs:
            route = cfg['case_suffix']
            case_id = cfg['case_id']
            if not any(row['case_id'] == case_id for row in plan['cases']):
                plan['cases'].append({
                    'case_id': case_id, 'target_law_id': cfg['law_id'],
                    'planning_status': 'unverified_definition', 'target_type': 'attempt',
                    'comparison_variable': 'requested_pavement_crossing',
                    'comparison_unit': 'bool', 'requested_setting': route,
                    'recorded_value': None,
                    'case_description': 'source-surveyed ' + label.lower() + ' and pavement crossing versus avoidance',
                    'fixed_context': 'Hold surveyed pavement, sign actor, weather, cameras and other controller settings fixed; verify sign face and repair from original sources.',
                    'source_topic_ids': ['text-0', 'text-1']})
            if not any(row['case_id'] == case_id for row in proposal['cases']):
                proposal['cases'].append({
                    'case_id': case_id, 'target_law_id': cfg['law_id'],
                    'target_type': 'attempt', 'recording_description': cfg['recording_description'],
                    'rationale': 'Request ' + route + ' of surveyed pavement near a source-surveyed ' + label.lower() + '.',
                    'unresolved_judgment_calls': ['whether the original sign face meets the statutory wording',
                                                  'whether the pavement was newly laid or repaired',
                                                  'whether the paving employee exception applies'],
                    'variable_assignments': {
                        'requested_pavement_crossing': {'kind': 'controller', 'value': route == 'crossing'},
                        'actual_body_contact': {'kind': 'subject_behavior', 'value': None},
                        'surveyed_pavement_and_sign': {'kind': 'world_setup',
                            'value': 'source-surveyed live map, sign actor and original sign face required'}}})
            if case_id not in plan['requirement_dispositions'][0]['case_ids']:
                plan['requirement_dispositions'][0]['case_ids'].append(case_id)
        if label not in plan['scope_branches']:
            plan['scope_branches'].append(label)
        comparison_id = ASSIGNMENT + '__comparison_' + kind
        if not any(row['comparison_id'] == comparison_id for row in plan['comparisons']):
            plan['comparisons'].append({
                'comparison_id': comparison_id, 'case_ids': [cfg['case_id'] for cfg in cfgs],
                'deliberate_differences': ['requested_pavement_crossing'],
                'fixed_conditions': ['cell', 'actor', 'surveyed pavement', 'sign actor',
                                     'weather', 'other controller settings',
                                     'camera and capture profile'],
                'status': 'planned_unverified'})
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    proposal_path.write_text(json.dumps(proposal, indent=2) + '\n')


if __name__ == '__main__':
    write()
