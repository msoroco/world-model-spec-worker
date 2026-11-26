"""Build the exact-law canonical stage chain for the four selected cases."""
import hashlib
import json
from pathlib import Path

from build_selected import CASES

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
LAW = 'NRS-484B-223-1b'
TEMPLATE = LAW + '@motor_vehicle_driver'
SIGNAL = 'the appropriate turn signal'
CHECK = 'ascertained that such movement can be made with safety'


def write(name, value):
    path = PACKAGE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    return {'path': str(path.relative_to(PACKAGE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def requirement(name, description):
    return {'name': name, 'unit': 'structured', 'description': description}


def main():
    assignment = json.loads((ROOT / 'inputs' / PACKAGE.name / 'assignment.json').read_text())
    quote = assignment['law']['text']
    if SIGNAL not in quote or CHECK not in quote:
        raise ValueError('Exact law source changed')
    description = json.loads((HERE / 'selected' / CASES[0] / 'construction.json').read_text())['recording_description']
    for suffix in CASES[1:]:
        other = json.loads((HERE / 'selected' / suffix / 'construction.json').read_text())['recording_description']
        if other != description:
            raise ValueError('Selected recording descriptions differ')
    relevance = {'cell_id': 'C245490', 'actor': 'motor_vehicle_driver',
                 'status': 'draft', 'relevant_laws': [{
                     'law_id': LAW, 'quote': quote,
                     'applies_to': ['motor_vehicle_driver'],
                     'relevance_type': 'specific_match', 'confidence': 'medium',
                     'notes': 'Marked same-direction lanes, original departure and signal/check sources require local review.'}],
                 'borderline_excluded': []}
    judgments = [
        {'phrase': SIGNAL,
         'note': 'Original indicator readback and its direction are retained; appropriateness remains unresolved.'},
        {'phrase': CHECK,
         'note': 'Separate controller check and target-lane actor gaps are retained; human ascertainment and legal safety remain unresolved.'},
    ]
    template = {'template_id': TEMPLATE, 'law_id': LAW,
                'actor': 'motor_vehicle_driver', 'status': 'draft', 'quote': quote,
                'structure': {
                    'activation': {'description': 'A highway has at least two clearly marked lanes for traffic traveling in one direction, and the subject moves from its occupied lane.',
                                   'source_clause': 'If a highway has two or more clearly marked lanes for traffic traveling in one direction'},
                    'obligation': {'description': 'Do not move from the occupied lane until both a prior appropriate turn signal and safety ascertainment are present.',
                                   'type': 'must_not',
                                   'source_clause': 'Not be moved from that lane until the driver has given the appropriate turn signal and ascertained that such movement can be made with safety.'},
                    'exceptions': [],
                    'timing': {'description': 'Observe indicator onset and separate check before first full-body departure from occupied lane.',
                               'source_clause': 'until the driver has given'},
                    'judgment_calls_needed': judgments},
                'parameter_refs': []}
    signal_observable = requirement('observed_indicator',
                                    'Original direction-specific lamp readback separated from controller command over full capture.')
    check_observable = requirement('controller_check',
                                   'Separate predeparture action, sampled source gap and controller decision; no inferred human state.')
    front_observable = requirement('front_actor',
                                   'Original target-lane front actor pose and longitudinal body clearance.')
    rear_observable = requirement('rear_actor',
                                  'Original target-lane rear actor pose and longitudinal body clearance.')
    observed = [
        {'template_id': TEMPLATE, 'phrase': SIGNAL, 'note': judgments[0]['note'],
         'status': 'draft', 'observable_requirements': {
             'observables': [signal_observable], 'context_inputs': [],
             'sweep_dimensions': [], 'landmarks': [],
             'recording_needs': [signal_observable],
             'limitations': ['Indicator readback alone does not establish legal appropriateness or human intent.']}},
        {'template_id': TEMPLATE, 'phrase': CHECK, 'note': judgments[1]['note'],
         'status': 'draft', 'observable_requirements': {
             'observables': [check_observable, front_observable, rear_observable],
             'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
             'recording_needs': [check_observable, front_observable, rear_observable],
             'limitations': ['Controller gap rule is engineering only; original source does not prove a human mental state.']}},
    ]
    variables = [
        {'name': 'signal_command_frame', 'kind': 'controller',
         'range_or_domain': 'before or after first occupied-lane departure', 'used_by_laws': [LAW]},
        {'name': 'rear_actor_spawn_distance_m', 'kind': 'world_setup',
         'range_or_domain': '8 or 30 m controlled target-lane rear actor distance; no legal cutoff',
         'used_by_laws': [LAW]},
        {'name': 'predeparture_check_action', 'kind': 'controller',
         'range_or_domain': 'evaluated or skipped', 'used_by_laws': [LAW]},
    ]
    binding = {'cell_id': 'C245490', 'actor': 'motor_vehicle_driver',
               'status': 'draft', 'established_contexts': [],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': variables}
    null_assignments = {item['name']: {'kind': item['kind'], 'value': None}
                        for item in variables}
    cases = [{'case_id': PACKAGE.name + '__baseline', 'target_law_id': None,
              'target_type': 'baseline',
              'rationale': 'Unselected common two-lane map, actor and capture context.',
              'variable_assignments': null_assignments,
              'recording_description': description,
              'unresolved_judgment_calls': [SIGNAL, CHECK]}]
    for suffix in CASES:
        case_id = PACKAGE.name + '__' + suffix
        value = {'signal_command_frame': 260 if suffix == 'signal_after_safe' else 100,
                 'rear_actor_spawn_distance_m': 8 if suffix == 'signal_before_unsafe' else 30,
                 'predeparture_check_action': 'skipped' if suffix == 'signal_before_no_check' else 'evaluated'}
        axis = {'signal_after_safe': 'signal_command_frame',
                'signal_before_safe': 'signal_command_frame',
                'signal_before_unsafe': 'rear_actor_spawn_distance_m',
                'signal_before_no_check': 'predeparture_check_action'}[suffix]
        cases.append({'case_id': case_id, 'target_law_id': LAW,
                      'target_type': 'boundary_probe',
                      'rationale': 'Retain original signal, departure, front/rear gap and separate check sources for controlled comparison.',
                      'paired_probe_id': 'c245490-selected-source-comparisons',
                      'deliberate_differences': [axis],
                      'probe': {'primary_variable': axis,
                                'comparison_or_standard': 'observed source order and controller gap/check behavior without a legal numeric cutoff',
                                'target_value_or_branch': value[axis]},
                      'variable_assignments': {
                          item['name']: {'kind': item['kind'], 'value': value[item['name']]}
                          for item in variables},
                      'recording_description': description,
                      'unresolved_judgment_calls': [SIGNAL, CHECK]})
    proposal = {'cell_id': 'C245490', 'actor': 'motor_vehicle_driver',
                'status': 'draft', 'cases': cases, 'sweeps_expanded': True,
                'sweep_specs': [{
                    'sweep_id': 'c245490-judgment-source-review',
                    'target_law_id': LAW, 'status': 'incomplete',
                    'judgment_refs': judgments,
                    'rationale': 'Selected source comparisons test separate facts; legal appropriateness and human safety ascertainment remain unresolved.',
                    'missing_inputs': ['Original Native signal pixels and actor interactions',
                                       'Independent human ascertainment evidence and legal judgment review']} ]}
    stages = {'relevance_batch': write('relevance_batch.json', relevance),
              'relevance': write('relevance.json', relevance),
              'template': write('template.json', template),
              'judgment_observables': [write('judgment_observables_0.json', observed[0]),
                                       write('judgment_observables_1.json', observed[1])],
              'bindings': write('bindings.json', binding),
              'cases': write('cases.json', proposal)}
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': PACKAGE.name, 'stages': stages})
    print(json.dumps({'selected_cases': len(cases) - 1, 'judgments': len(judgments)}))


if __name__ == '__main__':
    main()
