"""Verify selected diagnostic cases and a required recording-channel guard."""
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from batch_pipeline.stages import validate


def check():
    plan = json.loads((FOLDER.parent / 'case-plan.json').read_text())
    selection = json.loads((FOLDER / 'semantic-selection.json').read_text())
    proposal = json.loads((FOLDER / 'cases-stage-proposal.json').read_text())
    inputs = json.loads((FOLDER / 'cases-stage-inputs.json').read_text())
    selected = set(selection['selected_cpu_diagnostic_cases'])
    pending = set(selection['pending_physical_cases'])
    planned = {case['case_id'] for case in plan['cases']}
    assert len(selected) == 6 and len(pending) == 3
    assert selected | pending == planned and not selected & pending
    defined = {case['case_id'] for case in proposal['cases'] if case['target_type'] != 'baseline'}
    assert defined == planned
    assert set(selection['all_semantic_case_ids']) == defined
    for case in proposal['cases']:
        if case['case_id'] in pending:
            assert case.get('execution_readiness') == 'incomplete' and case.get('missing_inputs')
    by_case = {case['case_id']: case for case in proposal['cases']}
    expected_differences = {
        'single_signal': {'arm_command_schedule'},
        'continuity_not_required': {'arm_command_schedule'},
        'electric_bicycle': {'rider_device_class', 'device_blueprint_choice'},
        'electric_scooter': {'rider_device_class', 'device_blueprint_choice'},
        'turn_lane_exception': {'lane_route_selector'},
        'both_hands_exception': {'both_hands_demand_mode'},
        'reasonable_safety': {'clearance_target_band'},
    }
    for comparison in plan['comparisons']:
        left, right = (by_case[ident]['variable_assignments']
                       for ident in comparison['case_ids'])
        changed = {key for key in left if left[key] != right[key]}
        assert changed == expected_differences[comparison['comparison_id']], comparison['comparison_id']
    validate('cases', copy.deepcopy(proposal), inputs)
    broken = copy.deepcopy(proposal)
    target = next(case for case in broken['cases'] if case['target_type'] != 'baseline')
    target['recording_description']['channels'] = [row for row in target['recording_description']['channels']
                                                  if row['name'] != 'time_to_conflict_s']
    try:
        validate('cases', broken, inputs)
    except ValueError as error:
        assert 'Recording omits required law observable/context: time_to_conflict_s' in str(error), str(error)
    else:
        raise AssertionError('Missing original time-to-conflict channel was accepted')
    return {'selected_cpu_diagnostic_cases': len(selected), 'pending_physical_cases': len(pending),
            'semantic_cases_defined': len(defined),
            'comparison_pairs_checked': len(expected_differences),
            'positive_cases_stage_valid': True, 'missing_recording_channel_rejected': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
