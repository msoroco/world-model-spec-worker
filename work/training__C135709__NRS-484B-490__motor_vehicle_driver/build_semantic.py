"""Build original-law canonical stages for the narrow-highway parking pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
SOURCE = json.loads((REPO / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
LAW = SOURCE['law']
LAW_ID = LAW['id']
ACTOR = SOURCE['actor']
TEMPLATE_ID = f'{LAW_ID}@{ACTOR}'
OUT = HERE / 'proposals'
OUT.mkdir(exist_ok=True)


def save(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name + '.json',
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': 'C135709', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW_ID, 'quote': LAW['text'],
                                    'applies_to': [ACTOR], 'relevance_type': 'specific_match',
                                    'confidence': 'high',
                                    'notes': 'The frozen narrow-road park cell and prohibitory device match the exact law; official authority, erection and governed extent require original source review.'}],
                 'borderline_excluded': []}
    relevance_batch_ref = save('relevance_batch', relevance)
    relevance_ref = save('relevance', relevance)
    template = {'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
                'status': 'draft', 'quote': LAW['text'],
                'structure': {
                    'law_id': LAW_ID,
                    'activation': {'condition': 'Official traffic-control devices are erected prohibiting parking on a narrow highway.',
                                   'numeric_conditions': [],
                                   'source_clause': 'When official traffic-control devices are erected prohibiting parking upon a narrow highway'},
                    'obligation': {'description': 'A person shall not park a vehicle upon any such highway.',
                                   'type': 'must_not', 'numeric_conditions': [],
                                   'source_clause': 'a person shall not park a vehicle upon any such highway'},
                    'exceptions': [],
                    'timing': {'description': 'Review every original frame in the parked interval; 30 seconds is a recording requirement, not a legal threshold.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': []},
                'parameter_refs': [
                    {'name': 'parking_x_m', 'kind': 'world_setup',
                     'range_or_domain': '0 m inside or 35 m outside requested extent; independent source fixes actual extent'}]}
    template_ref = save('template', template)
    binding = {'cell_id': 'C135709', 'actor': ACTOR, 'status': 'draft',
               'established_contexts': [],
               'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': 'parking_x_m', 'kind': 'world_setup',
                                        'range_or_domain': '0 m or 35 m requested placement',
                                        'used_by_laws': [LAW_ID]}]}
    bindings_ref = save('bindings', binding)
    recording = json.loads((HERE / 'construction.json').read_text())['recording_description']
    cases = []
    pair = ASSIGNMENT + '__governed_extent_comparison'
    for index, (suffix, x, target) in enumerate((('probe_01', 35, 'compliant_attempt'),
                                                  ('probe_02', 0, 'violating_attempt'))):
        cases.append({'case_id': ASSIGNMENT + '__' + suffix, 'target_law_id': LAW_ID,
                      'target_type': target,
                      'rationale': 'Requested parked footprint outside versus within source-reviewed prohibited narrow-highway extent; no observed legal verdict.',
                      'variable_assignments': {'parking_x_m': {
                          'kind': 'world_setup', 'value': x, 'unit': 'm',
                          'source': 'selected exact Native config'}},
                      'unresolved_judgment_calls': [],
                      'paired_probe_id': pair,
                      'deliberate_differences': ['parking_x_m'],
                      'probe': {'primary_variable': 'parking_x_m',
                                'comparison_or_standard': 'same sourced road/device and governed extent; original full vehicle footprint relative to it',
                                'target_value_or_branch': x},
                      'recording_description': recording,
                      'selection_rank': index})
    cases.insert(0, {'case_id': ASSIGNMENT + '__baseline',
                     'target_law_id': None, 'target_type': 'baseline',
                     'rationale': 'Unselected neutral narrow-road context.',
                     'variable_assignments': {'parking_x_m': {
                         'kind': 'world_setup', 'value': None, 'unit': 'm'}},
                     'unresolved_judgment_calls': [],
                     'recording_description': recording})
    cases_ref = save('cases', {'cell_id': 'C135709', 'actor': ACTOR,
                               'status': 'draft', 'sweep_specs': [],
                               'sweeps_expanded': True, 'cases': cases})
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
             'stages': {'relevance_batch': relevance_batch_ref, 'relevance': relevance_ref,
                        'template': template_ref, 'judgment_observables': [],
                        'bindings': bindings_ref, 'cases': cases_ref}}
    save('semantic-index', index)
    print(index['stages'])


if __name__ == '__main__':
    main()
