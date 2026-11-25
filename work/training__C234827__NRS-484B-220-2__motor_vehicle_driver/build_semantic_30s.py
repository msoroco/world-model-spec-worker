"""Build source-bound rotary island-side semantic proposals for the selected pair."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
ASSIGNMENT = json.loads((ROOT / 'inputs' / FOLDER.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
AID = FOLDER.name
TEMPLATE = LAW['id'] + '@' + ASSIGNMENT['actor']


def write(name, value):
    path = FOLDER / 'proposals' / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(FOLDER)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def variable(kind, value, unit):
    return {'kind': kind, 'value': value, 'unit': unit}


def main():
    relevance = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'],
                 'status': 'draft', 'relevant_laws': [
                     {'law_id': LAW['id'], 'quote': LAW['text'],
                      'applies_to': [ASSIGNMENT['actor']], 'relevance_type': 'direct',
                      'confidence': 'high',
                      'notes': 'Exact right-of-island clause; original physical island and full body passage require Native review.'}],
                 'borderline_excluded': []}
    r1 = write('relevance-batch.json', relevance)
    r2 = write('relevance.json', relevance)
    parameters = [
        {'name': 'requested_island_side', 'kind': 'controller',
         'range_or_domain': ['island_on_left', 'island_on_right']},
        {'name': 'observed_island_side', 'kind': 'subject_behavior',
         'range_or_domain': 'source-derived island bearing and original body position at each joined frame, initially unknown'},
        {'name': 'observed_island_identity', 'kind': 'context',
         'range_or_domain': 'original map, geometry and pixel review of physical rotary traffic island, initially unknown'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW['id'], 'actor': ASSIGNMENT['actor'],
                'quote': LAW['text'], 'status': 'draft',
                'structure': {'law_id': LAW['id'],
                              'activation': {'condition': 'vehicle passes around a rotary traffic island',
                                             'numeric_conditions': []},
                              'obligation': {'description': 'vehicle shall be driven only to the right of that island',
                                             'type': 'must', 'numeric_conditions': []},
                              'exceptions': [],
                              'timing': {'description': 'island side is assessed continuously during actual passage around the island',
                                         'numeric_conditions': []},
                              'judgment_calls_needed': []},
                'parameter_refs': parameters}
    r3 = write('template.json', template)
    bindings = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'],
                'status': 'draft',
                'established_contexts': ['authored four-quarter rotary road; verify original physical traffic island and exact passage before legal use'],
                'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
                'context_refs': [],
                'fixed_parameters': [{'name': 'rotary_island_authored', 'value': True,
                                      'rationale': 'Exact construction requests an island and circulatory roadway; original physical readback and pixels remain required'}],
                'variable_parameters': [dict(item, used_by_laws=[LAW['id']]) for item in parameters]}
    r4 = write('bindings.json', bindings)
    recording = json.loads((FOLDER / 'selected-construction-reference.json').read_text())['recording_description']

    def values(side):
        return {'requested_island_side': variable('controller', side, 'categorical'),
                'observed_island_side': variable('subject_behavior', None, 'categorical per frame'),
                'observed_island_identity': variable('context', None, 'source review')}

    cases = [{'case_id': AID + '__baseline', 'target_law_id': None,
              'target_type': 'baseline',
              'rationale': 'Outside-island neutral comparison context; unselected.',
              'variable_assignments': values('island_on_left'),
              'unresolved_judgment_calls': [], 'recording_description': recording}]
    for suffix, direction, target_type in (('reference', 'island_on_left', 'compliant_attempt'),
                                           ('contrast', 'island_on_right', 'violating_attempt')):
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW['id'],
                      'target_type': target_type,
                      'rationale': 'Compare requested island side while holding frozen cell, island, lane radius, actor, cameras and 30-second clock fixed; original motion, physical island and legal outcome remain unobserved.',
                      'variable_assignments': values(direction),
                      'unresolved_judgment_calls': [],
                      'paired_probe_id': AID + '__island_side_pair',
                      'deliberate_differences': ['requested_island_side'],
                      'probe': {'primary_variable': 'requested_island_side',
                                'comparison_or_standard': 'island on left versus right throughout the same authored rotary passage',
                                'target_value_or_branch': direction},
                      'recording_description': recording})
    r5 = write('cases.json', {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'],
                              'status': 'draft', 'cases': cases, 'sweep_specs': []})
    index = {'format': 'worker-semantic-delivery', 'assignment_id': AID,
             'status': 'draft_selected_delivery',
             'stages': {'relevance_batch': r1, 'relevance': r2, 'template': r3,
                        'judgment_observables': [], 'bindings': r4, 'cases': r5}}
    write('semantic-index.json', index)
    print(json.dumps({'selected_cases': 2, 'judgment_phrases': 0}))


if __name__ == '__main__':
    main()
