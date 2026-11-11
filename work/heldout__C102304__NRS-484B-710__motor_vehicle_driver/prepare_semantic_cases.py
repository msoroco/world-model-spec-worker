"""Expand the existing exact-case draft into canonical stage assignments.

This edits only the assignment's proposal. It does not alter a construction,
source fixture, or accepted recording.
"""
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
path = folder / 'proposals/cases.json'
proposal = json.loads(path.read_text())
base = {
    'fire_following_gap_ft': {'kind': 'subject_behavior', 'value': None},
    'fire_drive_to_distance_ft': {'kind': 'subject_behavior', 'value': None},
    'fire_park_distance_ft': {'kind': 'subject_behavior', 'value': None},
    'apparatus_alarm_response': {'kind': 'world_setup', 'value': True},
    'apparatus_stopped_in_answer': {'kind': 'world_setup', 'value': False},
    'subject_authorized_emergency': {'kind': 'world_setup', 'value': False},
    'subject_official_business': {'kind': 'world_setup', 'value': False},
    'fire_branch': {'kind': 'world_setup', 'value': 'traveling_follow'},
    'target_distance_ft': {'kind': 'controller', 'value': 500},
    'target_centre_ft': {'kind': 'controller', 'value': 500},
}
first = proposal['cases'][0]
baseline = {
    'case_id': folder.name + '__neutral_baseline', 'target_law_id': None,
    'target_type': 'baseline', 'rationale': 'Shared neutral comparison reference; no delivery recording',
    'variable_assignments': base, 'unresolved_judgment_calls': [],
    'recording_description': first['recording_description'],
}
for case in proposal['cases']:
    suffix = case['case_id'].split('__')[-1]
    branch = ('stopped_drive_to' if suffix.startswith('stopped_drive_to')
              else 'stopped_park' if suffix.startswith('stopped_park')
              else 'traveling_follow')
    if branch == 'traveling_follow':
        threshold_index, variable, knob = 0, 'fire_following_gap_ft', 'target_distance_ft'
        group = 'traveling_500_boundary'
    elif branch == 'stopped_drive_to':
        threshold_index, variable, knob = 1, 'fire_drive_to_distance_ft', 'target_centre_ft'
        group = 'stopped_drive_to_500_boundary'
    else:
        threshold_index, variable, knob = 2, 'fire_park_distance_ft', 'target_centre_ft'
        group = 'stopped_park_500_boundary'
    target = case['variable_assignments'].get(knob, {}).get('value', 500)
    assignments = json.loads(json.dumps(base))
    assignments['fire_branch']['value'] = branch
    assignments['apparatus_stopped_in_answer']['value'] = branch != 'traveling_follow'
    assignments[knob]['value'] = target
    if suffix == 'authorized_emergency_at500':
        assignments['subject_authorized_emergency']['value'] = True
        assignments['subject_official_business']['value'] = True
    case['variable_assignments'] = assignments
    case['target_type'] = 'boundary_probe'
    case['paired_probe_id'] = group
    case['deliberate_differences'] = ([knob, 'subject_authorized_emergency',
                                      'subject_official_business'] if group == 'traveling_500_boundary'
                                     else [knob])
    case['probe'] = {
        'primary_variable': variable,
        'comparison_or_standard': 'NRS 484B.710 branch-specific 500 ft boundary; observed values are measured after capture',
        'target_value_or_branch': 'below' if target < 500 else 'above' if target > 500 else 'at',
        'threshold_ref': f'obligation.numeric_conditions[{threshold_index}]',
        'operator': '<' if threshold_index == 0 else '<=',
        'unit': 'ft', 'test_value': target,
    }
proposal['cases'] = [baseline, *proposal['cases']]
path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + '\n')
