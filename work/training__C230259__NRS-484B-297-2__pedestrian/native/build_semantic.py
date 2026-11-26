"""Build source-quoted draft semantic stage proposals for the side-only pair."""

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
INPUT = Path('inputs') / BASE.name / 'assignment.json'
PROPOSALS = BASE / 'proposals'


def write(name, value):
    PROPOSALS.mkdir(exist_ok=True)
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': 'proposals/' + name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads(INPUT.read_text())
    law = assignment['law']
    aid = assignment['assignment_id']
    case_plan = json.loads((BASE / 'case-plan.json').read_text())
    constructions = [json.loads((BASE / 'draft-native' / condition / 'construction.json').read_text())
                     for condition in ('a', 'b')]
    description = constructions[0]['recording_description']
    assert description == constructions[1]['recording_description']
    quote = 'pedestrians walking along highways where sidewalks are not provided shall walk on the left side of those highways facing the approaching traffic.'
    assert quote in law['text']
    relevance = {'cell_id': assignment['cell_id'], 'actor': assignment['actor'], 'status': 'draft',
                 'relevant_laws': [{'law_id': law['id'], 'quote': quote,
                                    'applies_to': ['pedestrian'], 'relevance_type': 'specific_match',
                                    'confidence': 'medium',
                                    'notes': 'Pedestrian and broad road/travel cell match; highway authority and sidewalk absence require reviewed Native source.'}],
                 'borderline_excluded': []}
    template_id = law['id'] + '@pedestrian'
    template = {'template_id': template_id, 'law_id': law['id'], 'actor': 'pedestrian',
                'status': 'draft', 'quote': law['text'],
                'structure': {'activation': {'description': 'Pedestrian walks along a highway where no sidewalk is provided.',
                                             'source_clause': 'pedestrians walking along highways where sidewalks are not provided'},
                              'obligation': {'description': 'Walk on the left side facing approaching traffic throughout the activated interval.',
                                             'source_clause': 'shall walk on the left side of those highways facing the approaching traffic.'},
                              'exceptions': [{'description': 'Subsection 6 sidewalk obstruction bypass governs where activated.',
                                              'source_clause': 'Except as otherwise provided in subsection 6 [NRS-484B-297-6]'}],
                              'timing': {'description': 'Continuous for walking along the highway without a sidewalk.',
                                         'source_clause': 'pedestrians walking along highways where sidewalks are not provided'},
                              'judgment_calls_needed': []},
                'parameter_refs': [{'name': 'pedestrian_highway_side', 'kind': 'world_setup',
                                    'range_or_domain': 'traffic_left or traffic_right; original geometry measured'}]}
    bindings = {'cell_id': assignment['cell_id'], 'actor': 'pedestrian', 'status': 'draft',
                'established_contexts': [], 'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [],
                'variable_parameters': [{'name': 'pedestrian_highway_side', 'kind': 'world_setup',
                                         'range_or_domain': 'traffic_left or traffic_right',
                                         'used_by_laws': [law['id']]}]}
    pair_id = case_plan['comparisons'][0]['comparison_id']
    cases = []
    for name, target, value in [('baseline', 'baseline', None),
                                ('a', 'compliant_attempt', 'traffic_left'),
                                ('b', 'violating_attempt', 'traffic_right')]:
        case_id = aid + '__baseline' if name == 'baseline' else constructions[0 if name == 'a' else 1]['case_id']
        cases.append({'case_id': case_id, 'target_law_id': None if name == 'baseline' else law['id'],
                      'target_type': target,
                      'rationale': 'Unselected shared baseline context.' if name == 'baseline' else
                                   'Diagnostic requested side; physical observations and legal interpretation remain unconfirmed.',
                      'variable_assignments': {'pedestrian_highway_side': {'kind': 'world_setup', 'value': value}},
                      'unresolved_judgment_calls': [], 'recording_description': description,
                      **({} if name == 'baseline' else {'paired_probe_id': pair_id,
                         'deliberate_differences': ['pedestrian_highway_side'],
                         'probe': {'primary_variable': 'pedestrian_highway_side',
                                   'comparison_or_standard': pair_id, 'target_value_or_branch': value}})})
    proposal = {'format': 'canonical-cases', 'cell_id': assignment['cell_id'], 'actor': 'pedestrian',
                'status': 'draft', 'sweep_specs': [], 'sweeps_expanded': True, 'cases': cases}
    references = {'relevance_batch': write('relevance-batch.json', relevance),
                  'relevance': write('relevance.json', relevance),
                  'template': write('template.json', template),
                  'judgment_observables': [],
                  'bindings': write('bindings.json', bindings),
                  'cases': write('cases.json', proposal)}
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': aid, 'stages': references})
    print(json.dumps({'assignment_id': aid, 'semantic_stages': 5,
                      'selected_cases': [case['case_id'] for case in cases if case['target_type'] != 'baseline']}))


if __name__ == '__main__':
    main()
