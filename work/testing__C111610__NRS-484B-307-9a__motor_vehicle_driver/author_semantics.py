"""Author source-bound draft semantic proposals for the exact 9(a) cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
LAW = 'NRS-484B-307-9a'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW + '@' + ACTOR
ASSIGNED = json.loads((HERE.parent.parent / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
PLAN = json.loads((HERE / 'case-plan.json').read_text())
QUOTE = ASSIGNED['law']['text']
PHRASES = [
    ('yield the right-of-way to pedestrians lawfully within an adjacent crosswalk',
     'The source supplies no numeric yielding or lawful-presence cutoff.'),
    ('yield the right-of-way to other traffic lawfully using the intersection',
     'The source supplies no numeric yielding or lawful-use cutoff.'),
]


def write(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def variable(name, kind, domain):
    return {'name': name, 'kind': kind, 'range_or_domain': domain,
            'used_by_laws': [LAW]}


def assignment(name, kind, value, note):
    return {'kind': kind, 'value': value, 'note': note}


def main():
    relevance = {'cell_id': 'C111610', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': QUOTE,
                                    'applies_to': [ACTOR],
                                    'relevance_type': 'direct red-plus-green-turn-arrow intersection duty',
                                    'confidence': 'high',
                                    'notes': 'Frozen assignment selects a turning motor vehicle driver and adjacent-crosswalk pedestrian.'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance.json', relevance)
    relevance_batch_ref = write('relevance_batch.json', relevance)
    params = [
        variable('adjacent_crosswalk_occupancy', 'world_setup', 'clear or sourced lawful pedestrian in adjacent crosswalk'),
        variable('other_traffic_occupancy', 'world_setup', 'absent or sourced lawful traffic in intersection'),
        variable('turn_controller_policy', 'controller', 'hold until clear or continue'),
        variable('commanded_turn_path', 'controller', 'arrow-directed turn or straight movement'),
    ]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
                'quote': QUOTE,
                'structure': {'law_id': LAW,
                              'activation': {'condition': 'Motor vehicle driver faces an official steady red with illuminated green turn arrow.', 'numeric_conditions': []},
                              'obligation': {'description': 'Enter only for the arrow-directed movement, yielding to lawfully present adjacent-crosswalk pedestrians and other traffic lawfully using the intersection.', 'type': 'must', 'numeric_conditions': []},
                              'exceptions': [{'trigger': 'Actor qualifies under paragraph (b).',
                                              'effect': 'Paragraph (b) governs the listed operator instead of this paragraph.',
                                              'replacement_obligation': 'Apply the separately assigned paragraph (b) only to its listed actors.',
                                              'source_clause': 'Except as otherwise provided in paragraph (b) [NRS-484B-307-9b]'}],
                              'timing': {'description': 'Original steady red, green arrow, opposing red, lawful occupancy and actual entry are joined by Native frame.', 'numeric_conditions': []},
                              'judgment_calls_needed': [{'phrase': p, 'note': n} for p, n in PHRASES]},
                'parameter_refs': [{k: v for k, v in p.items() if k != 'used_by_laws'} for p in params]}
    template_ref = write('template.json', template)
    judgment_refs = []
    for index, (phrase, note) in enumerate(PHRASES, 1):
        common = [{'name': o['name'], 'unit': 'structured record',
                   'description': o['description']} for o in PLAN['observations']]
        needs = ['ego_facing_red_arrow', 'opposing_red', 'official_head_approach',
                 'adjacent_crosswalk', 'pedestrian_lawful_presence',
                 'ego_entry_route_speed', 'other_traffic_lawful_use', 'camera_frame_map']
        if index == 1:
            needs.remove('other_traffic_lawful_use')
        else:
            needs.remove('pedestrian_lawful_presence')
        requirement = {'observables': common, 'context_inputs': [{'name': 'reviewed_original_site', 'unit': 'structured record', 'description': 'Source-sealed official heads, map and lawful-use context.'}],
                       'sweep_dimensions': [{'name': 'adjacent_crosswalk_occupancy' if index == 1 else 'other_traffic_occupancy', 'unit': 'categorical', 'description': 'Physical occupancy across the relevant yielding encounter.'}],
                       'landmarks': [], 'recording_needs': [v for v in common if v['name'] in needs],
                       'limitations': ['Original lawful-use context needs independent source review.', 'Physical signal, participant motion and camera pixels require Native review.']}
        judgment_refs.append(write(f'judgment-{index}.json', {'template_id': TEMPLATE,
            'phrase': phrase, 'note': note, 'status': 'draft', 'observable_requirements': requirement}))
    binding = {'cell_id': 'C111610', 'actor': ACTOR, 'status': 'draft',
               'established_contexts': ['intersection', 'turning motor vehicle driver', 'adjacent crosswalk'],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [],
               'fixed_parameters': [{'name': 'official_red_plus_arrow', 'value': 'source-reviewed ego red plus green turn arrow and opposing red', 'rationale': 'Fixed activation and advisory in each comparison.'}],
               'variable_parameters': params}
    binding_ref = write('bindings.json', binding)
    defaults = {
        'adjacent_crosswalk_occupancy': assignment('adjacent_crosswalk_occupancy', 'world_setup', 'clear', 'Reference physical crosswalk state.'),
        'other_traffic_occupancy': assignment('other_traffic_occupancy', 'world_setup', 'absent', 'Reference physical intersection state.'),
        'turn_controller_policy': assignment('turn_controller_policy', 'controller', 'hold_until_clear', 'Common controller for presence and route comparisons.'),
        'commanded_turn_path': assignment('commanded_turn_path', 'controller', 'arrow_turn', 'Arrow-directed movement.'),
    }
    groups = {'yield_pedestrian': ('pedestrian_yield', 'turn_controller_policy'),
              'continue_pedestrian': ('pedestrian_yield', 'turn_controller_policy'),
              'clear_crosswalk_turn': ('arrow_movement', 'commanded_turn_path'),
              'wrong_movement': ('arrow_movement', 'commanded_turn_path'),
              'yield_other_traffic': ('other_traffic_yield', 'turn_controller_policy'),
              'continue_other_traffic': ('other_traffic_yield', 'turn_controller_policy')}
    cases = []
    baseline = {'case_id': ASSIGNMENT + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Reference red-plus-arrow intersection, clear crosswalk and arrow-directed turn.',
                'variable_assignments': defaults, 'recording_description':
                    json.loads((HERE / 'config.json').read_text())['case']['recording_description'],
                'unresolved_judgment_calls': [p for p, _ in PHRASES]}
    cases.append(baseline)
    for row in PLAN['cases']:
        suffix = row['case_suffix']
        values = dict(defaults)
        params_case = row['scenario_parameters']
        values['adjacent_crosswalk_occupancy'] = assignment('adjacent_crosswalk_occupancy', 'world_setup', 'present' if params_case['adjacent_crosswalk_pedestrian_present'] else 'clear', 'Original lawful presence must be verified.')
        values['other_traffic_occupancy'] = assignment('other_traffic_occupancy', 'world_setup', 'present' if params_case.get('other_traffic_lawfully_using_intersection') else 'absent', 'Original lawful use must be verified.')
        values['turn_controller_policy'] = assignment('turn_controller_policy', 'controller', params_case['controller_policy'], 'Native command; actual motion retained.')
        values['commanded_turn_path'] = assignment('commanded_turn_path', 'controller', params_case['intended_route'], 'Native command; actual route retained.')
        group, primary = groups[suffix]
        cases.append({'case_id': row['case_id'], 'target_law_id': LAW,
                      'target_type': 'boundary_probe', 'rationale': row['purpose'],
                      'variable_assignments': values,
                      'recording_description': baseline['recording_description'],
                      'unresolved_judgment_calls': [p for p, _ in PHRASES],
                      'paired_probe_id': group,
                      'deliberate_differences': [primary],
                      'probe': {'primary_variable': primary,
                                'comparison_or_standard': group,
                                'target_value_or_branch': values[primary]['value']}})
    sweeps = [{'sweep_id': 'c111610-9a-'+str(i), 'target_law_id': LAW,
               'judgment_refs': [{'phrase': phrase, 'note': note}],
               'status': 'incomplete',
               'rationale': 'No source-reviewed original site and nontransient physical range are supplied for this assignment.',
               'missing_inputs': ['Source-reviewed official red-plus-arrow site, pedestrian and other traffic lawful-use records',
                                  'Feasible original participant timing and occupancy range']}
              for i, (phrase, note) in enumerate(PHRASES, 1)]
    cases_ref = write('cases.json', {'cell_id': 'C111610', 'actor': ACTOR,
                    'status': 'draft', 'cases': cases, 'sweep_specs': sweeps,
                    'sweeps_expanded': True})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
          'assignment_id': ASSIGNMENT,
          'stages': {'relevance_batch': relevance_batch_ref,
                     'relevance': relevance_ref, 'template': template_ref,
                     'judgment_observables': judgment_refs,
                     'bindings': binding_ref, 'cases': cases_ref}})


if __name__ == '__main__':
    main()
