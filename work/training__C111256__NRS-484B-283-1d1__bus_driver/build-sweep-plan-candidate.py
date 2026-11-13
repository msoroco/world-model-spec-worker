"""Prepare exact case-plan coverage for the four unselected physical sweep cases."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    plan = copy.deepcopy(read(HERE / 'case-plan.json'))
    stage = read(HERE / 'proposals/sweep-stage-candidate.json')
    bound = read(HERE / 'sweep-proof-bound-promotion-candidate.json')
    stage_cases = [case for case in stage['cases'] if case['target_type'] == 'judgment_sweep']
    by_id = {item['case_id']: item for item in bound['cases']}
    if (len(stage_cases) != 4 or set(by_id) != {case['case_id'] for case in stage_cases}
            or len(plan['cases']) != 2):
        raise ValueError('Sweep plan input coverage differs')
    requested = []
    for case in stage_cases:
        case_id = case['case_id']
        setting = case['sweep_point']['crosswalk_hold_margin_m']
        requested.append(setting)
        entry = by_id[case_id]
        if (case['variable_assignments']['crosswalk_hold_margin_m']['value'] != setting or
                entry['candidate_risk']['status'] != 'physical' or
                len(entry['candidates']) != 3 or
                not entry.get('physical_preparation')):
            raise ValueError('Physical sweep construction or risk binding differs')
        plan['cases'].append({
            'case_id': case_id, 'target_law_id': case['target_law_id'],
            'planning_status': 'unverified_definition', 'target_type': 'attempt',
            'comparison_variable': 'crosswalk_hold_margin_m', 'comparison_unit': 'm',
            'requested_setting': setting, 'recorded_value': None,
            'case_description': ('Fixed bus hold-margin engineering probe under authored '
                                 'Walk/crosswalk context; physical and legal response unresolved.'),
            'fixed_context': ('Hold cell, actors, route, authored Walk device, crossing geometry, '
                              'weather, noncompared controller settings and four-camera capture '
                              'policy constant; verify original source and exceptions before use.'),
            'source_topic_ids': ['text-0', 'text-1', 'text-2'],
            'gap_ids': ['walk_signal_governance', 'bus_pedestrian_original_motion',
                        'introductory_exceptions', 'right_of_way_physical_judgment'],
            'physical_risk_assessment': {
                'status': 'physical',
                'risks': ['bus lane tracking and measured crosswalk hold margin',
                          'original pedestrian-facing Walk pixel coverage and governance'],
                'source_trigger_requirements': [
                    'original bus full-body/pose and control request',
                    'original source camera pixels',
                    'Native signal identity and map readback']}})
    if set(requested) != {0.5, 1.0, 1.5, 2.0}:
        raise ValueError('Physical sweep grid changed')
    sweep_ids = [case['case_id'] for case in stage_cases]
    for disposition in plan['requirement_dispositions']:
        if disposition['status'] == 'selected_required':
            disposition['case_ids'] = sorted(set(disposition['case_ids']) | set(sweep_ids))
    plan['comparisons'].append({
        'comparison_id': HERE.name + '__right_of_way_physical_context_sweep',
        'case_ids': sweep_ids,
        'deliberate_differences': ['crosswalk_hold_margin_m'],
        'fixed_conditions': ['cell', 'actor', 'legal context', 'traffic controls',
                             'weather', 'other controller settings', 'camera and capture profile'],
        'status': 'planned_unverified'})
    if len({case['case_id'] for case in plan['cases']}) != 6:
        raise ValueError('Duplicate or missing selected plan case')
    path = HERE / 'case-plan-sweep-candidate.json'
    path.write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps({'planned_cases': len(plan['cases']),
                      'sweep_comparison_cases': len(sweep_ids),
                      'margin_setpoints_m': sorted(requested),
                      'selected': False, 'legal_threshold_claimed': False,
                      'plan_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
