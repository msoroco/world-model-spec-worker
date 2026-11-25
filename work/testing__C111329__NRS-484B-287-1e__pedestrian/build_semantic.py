"""Author source-cited draft semantic stages for the exact diagonal law split."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / 'proposals'
ASSIGNMENT = HERE.name
LAW = 'NRS-484B-287-1e'
CELL = 'C111329'
ACTOR = 'pedestrian'
QUOTE = ('When authorized to cross diagonally, pedestrians shall cross only in '
         'accordance with the official traffic-control devices pertaining to such crossing movements.')


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    OUT.mkdir(exist_ok=True)
    plan = json.loads((HERE / 'case-plan.json').read_text())
    assignment_path = REPO / 'inputs' / ASSIGNMENT / 'assignment.json'
    relevant = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                'relevant_laws': [{'law_id': LAW, 'quote': QUOTE,
                                   'applies_to': [ACTOR],
                                   'relevance_type': 'specific_match',
                                   'confidence': 'low',
                                   'notes': 'Actual diagonal authorization, official pedestrian device and NRS 484B.290 exception source remain unverified.'}],
                'borderline_excluded': []}
    relevance_batch = write('relevance_batch.json', relevant)
    relevance = write('relevance.json', relevant)
    template = write('template.json', {
        'template_id': LAW + '@' + ACTOR, 'law_id': LAW, 'actor': ACTOR,
        'quote': QUOTE, 'status': 'draft',
        'structure': {'law_id': LAW,
                      'activation': {'condition': 'Pedestrian is authorized to cross diagonally.',
                                     'numeric_conditions': []},
                      'obligation': {'description': 'Cross only in accordance with the official traffic-control devices pertaining to that diagonal crossing.',
                                     'type': 'must', 'numeric_conditions': []},
                      'exceptions': [{'trigger': 'Referenced NRS 484B.290 exception, unresolved without its official source and facts',
                                      'effect': 'Preserve exception state for separate review; no verdict inferred.',
                                      'replacement_obligation': 'Apply the source-reviewed exception if established.',
                                      'source_clause': 'Except as provided in NRS 484B.290 [LVMC-11-30-140-B]'}],
                      'timing': {'description': 'Observe the governing diagonal instruction across the complete original pedestrian crossing.',
                                 'numeric_conditions': []},
                      'judgment_calls_needed': []},
        'parameter_refs': [{'name': 'governing_diagonal_instruction',
                            'kind': 'world_setup'}]})
    bindings = write('bindings.json', {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': ['Intersection, pedestrian travel, traffic-control device'],
        'law_refs': [{'template_id': LAW + '@' + ACTOR, 'binding_kind': 'direct'}],
        'context_refs': [],
        'fixed_parameters': [{'name': 'diagonal_site_authorization', 'kind': 'world_setup',
                              'range_or_domain': 'source-reviewed original site; currently pending'},
                             {'name': 'exception_484b_290_source_state', 'kind': 'world_setup',
                              'range_or_domain': 'unresolved pending official source'}],
        'variable_parameters': [{'name': 'governing_diagonal_instruction',
                                 'kind': 'world_setup',
                                 'range_or_domain': 'diagonal_walk, diagonal_dont_walk, transition',
                                 'used_by_laws': [LAW]}]})
    description = json.loads((HERE / 'construction-permissive_whole_crossing.json').read_text())['recording_description']
    baseline = {'case_id': ASSIGNMENT + '__shared_baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Reference for the common diagonal site and original walker route; no separate recording selected.',
                'variable_assignments': {'governing_diagonal_instruction': {
                    'kind': 'world_setup', 'value': 'diagonal_walk'}},
                'deliberate_differences': [], 'unresolved_judgment_calls': [],
                'recording_description': description}
    cases = [baseline]
    for case in plan['cases']:
        suffix = case['case_id'].split('__')[-1]
        target_type = ('compliant_attempt' if suffix == 'permissive_whole_crossing'
                       else 'violating_attempt' if suffix == 'prohibitive_whole_crossing'
                       else 'boundary_probe')
        cases.append({'case_id': case['case_id'], 'target_law_id': LAW,
                      'target_type': target_type,
                      'rationale': case['purpose'] + '; intended software contrast only, with exception and official source unresolved.',
                      'variable_assignments': {'governing_diagonal_instruction': {
                          'kind': 'world_setup',
                          'value': case['scenario_parameters']['governing_device_instruction']}},
                      'paired_probe_id': 'diagonal_instruction_contrast',
                      'deliberate_differences': ['governing_diagonal_instruction'],
                      'probe': {'primary_variable': 'governing_diagonal_instruction',
                                'comparison_or_standard': 'source-observed governing diagonal instruction contrast',
                                'target_value_or_branch': suffix},
                      'unresolved_judgment_calls': [],
                      'recording_description': description})
    cases_ref = write('cases.json', {'cell_id': CELL, 'actor': ACTOR,
                                     'status': 'draft', 'sweeps_expanded': True,
                                     'sweep_specs': [], 'cases': cases})
    stages = {'relevance_batch': relevance_batch, 'relevance': relevance,
              'template': template, 'judgment_observables': [],
              'bindings': bindings, 'cases': cases_ref}
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': ASSIGNMENT,
                                  'source': {'path': str(assignment_path.relative_to(REPO)),
                                             'sha256': hashlib.sha256(assignment_path.read_bytes()).hexdigest()},
                                  'stages': stages,
                                  'status': 'draft_official_site_and_exception_source_review_pending'})
    return stages


if __name__ == '__main__':
    print('authored', len(build()), 'draft semantic stages')
