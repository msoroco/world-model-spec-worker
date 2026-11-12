"""Bind the eight constructed cases to canonical draft parameters and probe metadata."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATH = ROOT / 'proposals/cases.json'
INDEX = ROOT / 'proposals/semantic-index.json'
PREFIX = ROOT.name + '__'


def assignment(kind, value, unit):
    return {'kind': kind, 'value': value, 'unit': unit}


def main():
    data = json.loads(PATH.read_text())
    cases = [case for case in data['cases'] if case['target_type'] != 'baseline']
    description = deepcopy(cases[0]['recording_description'])
    defaults = {
        'requested_body_gap_m': assignment('world_setup', 152.4, 'm'),
        'ego_target_speed_mps': assignment('controller', 12.0, 'm/s'),
        'lead_target_speed_mps': assignment('controller', 12.0, 'm/s'),
        'same_direction_lane_count': assignment('world_setup', 1, 'count'),
        'requested_ego_width_m': assignment('world_setup', 2.032, 'm'),
        'requested_lead_width_m': assignment('world_setup', 2.032, 'm'),
        'passing_lane_id': assignment('world_setup', 0, 'id'),
        'longitudinal_body_gap': assignment('subject_behavior', None, 'm'),
        'ego_overall_width': assignment('subject_behavior', None, 'm'),
        'lead_overall_width': assignment('subject_behavior', None, 'm')}
    baseline = {'case_id': PREFIX + 'baseline', 'target_law_id': 'NRS-484B-127-2',
                'target_type': 'baseline', 'rationale': 'Shared engineering setup, with legal status unresolved.',
                'variable_assignments': deepcopy(defaults),
                'recording_description': deepcopy(description),
                'unresolved_judgment_calls': ['whenever conditions permit', 'without danger']}
    mappings = {
        'gap_below_500ft': ('gap', 'below', 150 / .3048),
        'gap_at_500ft': ('gap', 'at', 500),
        'gap_above_500ft': ('gap', 'above', 155 / .3048),
        'ego_width_below_80in': ('ego_width', 'below', 2.0 / .0254),
        'ego_width_at_80in': ('ego_width', 'at', 80),
        'lead_width_below_80in': ('lead_width', 'below', 2.0 / .0254)}
    paths = {'gap': ('obligation.numeric_conditions[0]', 'longitudinal_body_gap', 'ft', 'requested_body_gap_m'),
             'ego_width': ('activation.numeric_conditions[0]', 'ego_overall_width', 'in', 'requested_ego_width_m'),
             'lead_width': ('activation.numeric_conditions[1]', 'lead_overall_width', 'in', 'requested_lead_width_m')}
    for case in cases:
        suffix = case['case_id'].removeprefix(PREFIX)
        original = case['variable_assignments']
        case['variable_assignments'] = deepcopy(defaults)
        case['variable_assignments'].update(original)
        case['unresolved_judgment_calls'] = ['whenever conditions permit', 'without danger']
        if suffix in mappings:
            group, side, test_value = mappings[suffix]
            path, primary, unit, difference = paths[group]
            case.update(target_type='boundary_probe', paired_probe_id='truck_follow_' + group,
                        deliberate_differences=[difference],
                        epsilon_used={'value': 1 if unit == 'ft' else .5, 'unit': unit,
                                      'rationale': 'Engineering sampling margin; no legal tolerance.'},
                        probe={'primary_variable': primary,
                               'comparison_or_standard': 'exact statutory boundary; physical value awaits Native readback',
                               'target_value_or_branch': side, 'threshold_ref': path,
                               'operator': '>=', 'unit': unit, 'test_value': test_value})
        else:
            case.update(target_type='judgment_sweep', paired_probe_id='truck_follow_exceptions',
                        deliberate_differences=['same_direction_lane_count', 'ego_target_speed_mps',
                                                'lead_target_speed_mps', 'passing_lane_id', 'requested_body_gap_m'],
                        probe={'primary_variable': 'same_direction_lane_count' if suffix == 'two_same_direction_lanes' else 'passing_lane_id',
                               'comparison_or_standard': 'source-law exception branch',
                               'target_value_or_branch': suffix})
    data.update(cell_id='C149237', actor='heavy_vehicle_driver', status='draft',
                cases=[baseline] + cases,
                sweep_specs=[{'sweep_id': 'truck_follow_qualitative_review',
                              'target_law_id': 'NRS-484B-127-2',
                              'judgment_refs': [
                                  {'phrase': 'whenever conditions permit',
                                   'note': 'Road, traffic, visibility, and continuity require original-source review.'},
                                  {'phrase': 'without danger',
                                   'note': 'Safe entry and occupancy by an overtaking vehicle require original-source review.'}],
                              'rationale': 'Original-source judgment review remains to be physically sampled.',
                              'status': 'incomplete',
                              'missing_inputs': ['Native physical capture, reviewed overtaker occupancy, and verified road context']}] )
    PATH.write_text(json.dumps(data, indent=2) + '\n')
    index = json.loads(INDEX.read_text())
    index['stages']['cases']['sha256'] = hashlib.sha256(PATH.read_bytes()).hexdigest()
    INDEX.write_text(json.dumps(index, indent=2) + '\n')


if __name__ == '__main__':
    main()
