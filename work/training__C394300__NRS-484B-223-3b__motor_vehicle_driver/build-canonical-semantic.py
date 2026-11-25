"""Build draft canonical stages for the exact 200-foot center-turn rule."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'NRS-484B-223-3b'
TEMPLATE = LAW + '@motor_vehicle_driver'
VALUES = {'witness_1': 180, 'witness_2': 220,
          'numeric_1_0': 199, 'numeric_1_1': 200, 'numeric_1_2': 201}


def write(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': path.relative_to(HERE).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = assignment['law']['text']
    assert quote == plan['source_law']['text']
    selected = json.loads((HERE / 'selected-probe-manifest.json').read_text())
    description = json.loads((HERE / selected['cases'][0]['construction']).read_text())['recording_description']
    for entry in selected['cases']:
        assert json.loads((HERE / entry['construction']).read_text())['recording_description'] == description
    design = 'a single center lane to be used only for turning by traffic moving in both directions'
    distance = 'must not travel more than 200 feet in a center turn lane before making a left-hand turn from the highway'
    assert design in quote and distance in quote
    relevance = {'cell_id': 'C394300', 'actor': 'motor_vehicle_driver',
                 'status': 'draft', 'relevant_laws': [{
                     'law_id': LAW, 'quote': quote, 'applies_to': ['motor_vehicle_driver'],
                     'relevance_type': 'specific_match', 'confidence': 'medium',
                     'notes': 'Original center-lane designation, body path and turn onset require local review.'}],
                 'borderline_excluded': []}
    judgment = {'phrase': design,
                'note': 'Authored center-lane design and original Native lane survey require independent review.'}
    template = {'template_id': TEMPLATE, 'law_id': LAW,
                'actor': 'motor_vehicle_driver', 'status': 'draft', 'quote': quote,
                'structure': {
                    'activation': {'description': 'A highway has one center lane designed only for turns by both directions.',
                                   'source_clause': design},
                    'obligation': {'description': 'Do not travel more than 200 feet in that lane before the left turn from the highway.',
                                   'source_clause': distance},
                    'exceptions': [],
                    'timing': {'description': 'Measure from full-body entry to observed left-turn onset.',
                               'source_clause': distance},
                    'judgment_calls_needed': [judgment]},
                'parameter_refs': []}
    observable = {'name': 'st.centre_turn_lane', 'unit': 'structured',
                  'description': 'Retain authored map, Native lane survey, body and camera sources for design review.'}
    judged = {'template_id': TEMPLATE, 'phrase': design, 'note': judgment['note'],
              'status': 'draft', 'observable_requirements': {
                  'observables': [observable], 'context_inputs': [],
                  'sweep_dimensions': [], 'landmarks': [],
                  'recording_needs': [observable],
                  'limitations': ['Synthetic source rows do not prove Native lane design or legal compliance.']}}
    binding = {'cell_id': 'C394300', 'actor': 'motor_vehicle_driver',
               'status': 'draft', 'established_contexts': [],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': 'requested_center_lane_distance_ft',
                                        'kind': 'controller',
                                        'range_or_domain': '180, 199, 200, 201 or 220 feet requested before left turn',
                                        'used_by_laws': [LAW]}]}
    baseline = {'case_id': HERE.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline',
                'rationale': 'Unselected common center-lane map, actor and capture context.',
                'variable_assignments': {'requested_center_lane_distance_ft':
                                         {'kind': 'controller', 'value': None}},
                'recording_description': description,
                'unresolved_judgment_calls': [design]}
    cases = [baseline]
    for entry in selected['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        value = VALUES[suffix]
        pair = ('c394300-center-turn-distance-witness' if suffix.startswith('witness_')
                else 'c394300-center-turn-distance-numeric')
        cases.append({'case_id': case_id, 'target_law_id': LAW,
                      'target_type': 'boundary_probe',
                      'rationale': 'Compare original full-body center-lane path distance and left-turn onset with shared map, actor and capture.',
                      'paired_probe_id': pair,
                      'deliberate_differences': ['requested_center_lane_distance_ft'],
                      'probe': {'primary_variable': 'requested_center_lane_distance_ft',
                                'comparison_or_standard': '200 feet from original body entry to observed turn onset',
                                'target_value_or_branch': value},
                      'variable_assignments': {'requested_center_lane_distance_ft':
                                               {'kind': 'controller', 'value': value}},
                      'recording_description': description,
                      'unresolved_judgment_calls': [design]})
    proposal = {'cell_id': 'C394300', 'actor': 'motor_vehicle_driver',
                'status': 'draft', 'cases': cases, 'sweeps_expanded': True,
                'sweep_specs': [{'sweep_id': 'c394300-center-turn-distance-review',
                                 'target_law_id': LAW, 'status': 'incomplete',
                                 'judgment_refs': [judgment],
                                 'rationale': 'Five software-prepared distance requests await original Native lane and body measurements.',
                                 'missing_inputs': ['Original Native center-lane and body evidence',
                                                    'Independent 200-foot interval and turn-onset review']}]}
    stages = {'relevance_batch': write('relevance_batch.json', relevance),
              'relevance': write('relevance.json', relevance),
              'template': write('template.json', template),
              'judgment_observables': [write('judgment_observables_0.json', judged)],
              'bindings': write('bindings.json', binding),
              'cases': write('cases.json', proposal)}
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': HERE.name, 'stages': stages})
    print(json.dumps({'selected_cases': len(cases) - 1, 'judgments': 1}))


if __name__ == '__main__':
    main()
