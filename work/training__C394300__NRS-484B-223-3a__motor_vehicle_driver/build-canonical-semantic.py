"""Build source-grounded canonical proposals for the exact center-turn rule."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'NRS-484B-223-3a'
TEMPLATE = LAW + '@motor_vehicle_driver'


def write(name, value):
    path = HERE / 'proposals' / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': path.relative_to(HERE).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = assignment['law']['text']
    assert quote == plan['source_law']['text']
    construction = json.loads((HERE / 'selected-candidates/controlled_1/primary/construction.json').read_text())
    description = construction['recording_description']
    relevance = {'cell_id': 'C394300', 'actor': 'motor_vehicle_driver',
                 'status': 'draft', 'relevant_laws': [{
                     'law_id': LAW, 'quote': quote, 'applies_to': ['motor_vehicle_driver'],
                     'relevance_type': 'specific_match', 'confidence': 'medium',
                     'notes': 'Original center-lane designation, body movement and purpose need local review.'}],
                 'borderline_excluded': []}
    judgments = [
        ('a single center lane to be used only for turning by traffic moving in both directions',
         'Authored bidirectional center design and original Native lane survey must agree.'),
        ('only for the purpose of making a left-hand turn onto or from the highway',
         'Declared experimental purpose is separate from observed movement and driver intent.'),
    ]
    assert all(phrase in quote for phrase, _ in judgments)
    template = {'template_id': TEMPLATE, 'law_id': LAW,
                'actor': 'motor_vehicle_driver', 'status': 'draft', 'quote': quote,
                'structure': {
                    'activation': {'description': 'A highway has one center lane designed only for turns by both directions.',
                                   'source_clause': judgments[0][0]},
                    'obligation': {'description': 'Center-lane driving has the purpose of a left turn onto or from the highway.',
                                   'source_clause': judgments[1][0]},
                    'exceptions': [],
                    'timing': {'description': 'Review the entire original center-lane occupancy and subsequent movement.',
                               'source_clause': judgments[1][0]},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                              for phrase, note in judgments]},
                'parameter_refs': []}
    units = {channel['name']: channel['unit'] for channel in description['channels']}
    names = ('st.centre_turn_lane', 'drv.turning')
    observed = []
    for index, ((phrase, note), name) in enumerate(zip(judgments, names)):
        item = {'name': name, 'unit': units[name],
                'description': 'Retain original map, lane, body and movement source for review.'}
        context = {'name': 'authored_center_turn_map_and_native_survey',
                   'unit': 'structured',
                   'description': 'Map and actual Native lane-type review remain separate from Core ordinary lane projection.'}
        value = {'template_id': TEMPLATE, 'phrase': phrase, 'note': note,
                 'status': 'draft', 'observable_requirements': {
                     'observables': [item], 'context_inputs': [],
                     'sweep_dimensions': [], 'landmarks': [],
                     'recording_needs': [item],
                     'limitations': [note, 'Synthetic source rows do not prove physical design, actual movement, driver intent or legal compliance.']}}
        observed.append(write(f'judgment_observables_{index}.json', value))
    binding = {'cell_id': 'C394300', 'actor': 'motor_vehicle_driver',
               'status': 'draft', 'established_contexts': [],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': 'requested_center_lane_movement',
                                        'kind': 'controller',
                                        'range_or_domain': 'left turn at first opportunity or through movement then later turn',
                                        'used_by_laws': [LAW]}]}
    ids = [case['case_id'] for case in plan['cases']]
    assert len(ids) == 2
    baseline = {'case_id': HERE.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline',
                'rationale': 'Unselected common center-lane map, actor and capture context.',
                'variable_assignments': {'requested_center_lane_movement':
                                         {'kind': 'controller', 'value': None}},
                'recording_description': description,
                'unresolved_judgment_calls': [phrase for phrase, _ in judgments]}
    cases = [baseline]
    for case_id, movement in zip(ids, ('left_turn_at_first_opportunity',
                                        'through_first_opportunity_then_later_turn')):
        cases.append({'case_id': case_id, 'target_law_id': LAW,
                      'target_type': 'boundary_probe',
                      'rationale': 'Compare original full-body center-lane use and subsequent movement with shared geometry, capture and actor.',
                      'paired_probe_id': 'c394300-center-turn-purpose-pair',
                      'deliberate_differences': ['requested_center_lane_movement'],
                      'probe': {'primary_variable': 'requested_center_lane_movement',
                                'comparison_or_standard': 'entire original center-lane occupancy and next movement',
                                'target_value_or_branch': movement},
                      'variable_assignments': {'requested_center_lane_movement':
                                               {'kind': 'controller', 'value': movement}},
                      'recording_description': description,
                      'unresolved_judgment_calls': [phrase for phrase, _ in judgments]})
    proposal = {'cell_id': 'C394300', 'actor': 'motor_vehicle_driver',
                'status': 'draft', 'cases': cases, 'sweeps_expanded': True,
                'sweep_specs': [{'sweep_id': 'c394300-original-center-turn-review',
                                 'target_law_id': LAW, 'status': 'incomplete',
                                 'judgment_refs': [{'phrase': phrase, 'note': note}
                                                   for phrase, note in judgments],
                                 'rationale': 'Two software-prepared movement cases await original Native lane, body and purpose review.',
                                 'missing_inputs': ['Original Native center-lane and full-body evidence',
                                                    'Independent driver-purpose and movement review']}]}
    stages = {'relevance_batch': write('relevance_batch.json', relevance),
              'relevance': write('relevance.json', relevance),
              'template': write('template.json', template),
              'judgment_observables': observed,
              'bindings': write('bindings.json', binding),
              'cases': write('cases.json', proposal)}
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': HERE.name, 'stages': stages})
    print(json.dumps({'cases': ids, 'judgment_observables': len(observed)}))


if __name__ == '__main__':
    main()
