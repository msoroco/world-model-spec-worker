"""Extend the draft C183370 case plan with a controlled barrier route pair."""
import json
from pathlib import Path

from variant_recording_contract import ASSIGNMENT, config

PACKAGE = Path(__file__).resolve().parents[1]


def write():
    plan_path = PACKAGE / 'case-plan.json'
    proposal_path = PACKAGE / 'proposals/cases.json'
    plan = json.loads(plan_path.read_text())
    proposal = json.loads(proposal_path.read_text())
    cases = [config('barrier', route, 600) for route in ('crossing', 'avoidance')]
    for cfg in cases:
        case_id, route = cfg['case_id'], cfg['case_suffix']
        if not any(row['case_id'] == case_id for row in plan['cases']):
            plan['cases'].append({
                'case_id': case_id, 'target_law_id': cfg['law_id'],
                'planning_status': 'unverified_definition', 'target_type': 'attempt',
                'comparison_variable': 'requested_pavement_crossing',
                'comparison_unit': 'bool', 'requested_setting': route,
                'recorded_value': None,
                'case_description': 'source-surveyed barrier and repaired pavement crossing versus avoidance',
                'fixed_context': 'Hold surveyed pavement, barrier, weather, cameras and all other controller settings fixed; verify barrier and repair from original sources.',
                'source_topic_ids': ['text-0', 'text-1']})
        if not any(row['case_id'] == case_id for row in proposal['cases']):
            proposal['cases'].append({
                'case_id': case_id,
                'rationale': 'Request body contact with surveyed pavement near a barrier.' if route == 'crossing'
                             else 'Request avoidance of the same surveyed pavement and barrier.',
                'recording_description': cfg['recording_description'],
                'target_law_id': cfg['law_id'], 'target_type': 'attempt',
                'unresolved_judgment_calls': [
                    'whether a barrier was placed across or around newly laid or repaired pavement',
                    'whether the pavement was newly laid or repaired',
                    'whether the paving employee exception applies'],
                'variable_assignments': {
                    'requested_pavement_crossing': {'kind': 'controller',
                                                    'value': route == 'crossing'},
                    'actual_body_contact': {'kind': 'subject_behavior', 'value': None},
                    'surveyed_pavement_and_barrier': {'kind': 'world_setup',
                                                      'value': 'source-surveyed live map and barrier actor required'}}})
    selected = plan['requirement_dispositions'][0]['case_ids']
    for cfg in cases:
        if cfg['case_id'] not in selected:
            selected.append(cfg['case_id'])
    if 'Barrier' not in plan['scope_branches']:
        plan['scope_branches'].append('Barrier')
    comparison_id = ASSIGNMENT + '__comparison_barrier'
    if not any(row['comparison_id'] == comparison_id for row in plan['comparisons']):
        plan['comparisons'].append({
            'comparison_id': comparison_id,
            'case_ids': [cfg['case_id'] for cfg in cases],
            'deliberate_differences': ['requested_pavement_crossing'],
            'fixed_conditions': ['cell', 'actor', 'surveyed pavement', 'barrier actor',
                                 'weather', 'other controller settings',
                                 'camera and capture profile'],
            'status': 'planned_unverified'})
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    proposal_path.write_text(json.dumps(proposal, indent=2) + '\n')


if __name__ == '__main__':
    write()
