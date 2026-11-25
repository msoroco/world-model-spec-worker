"""Build exact draft semantic stages for the selected intersection comparisons."""
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
                      'notes': 'Exact intersection branch; physical highway, centerline and one-way applicability remain original Native review.'}],
                 'borderline_excluded': []}
    r1 = write('relevance-batch.json', relevance)
    r2 = write('relevance.json', relevance)
    parameters = [
        {'name': 'requested_left_interval', 'kind': 'controller',
         'range_or_domain': ['none', 'approach', 'traversal']},
        {'name': 'observed_left_occupancy', 'kind': 'subject_behavior',
         'range_or_domain': 'original full vehicle footprint relative to reviewed centerline, initially unknown'},
        {'name': 'observed_intersection_zone', 'kind': 'world_setup',
         'range_or_domain': 'original physical intersection and roadway direction, initially unknown'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW['id'], 'actor': ASSIGNMENT['actor'],
                'quote': LAW['text'], 'status': 'draft',
                'structure': {'law_id': LAW['id'],
                              'activation': {'condition': 'vehicle approaches within 100 feet or traverses an intersection on a non-one-way highway',
                                             'numeric_conditions': []},
                              'obligation': {'description': 'vehicle must not be driven to the left side of the highway',
                                             'type': 'must_not', 'numeric_conditions': []},
                              'exceptions': [{'condition': 'one-way highway', 'effect': 'subsection 2 does not apply',
                                              'source_clause': 'Subsection 2 does not apply upon a one-way highway.'}],
                              'timing': {'description': 'throughout approach within 100 feet or intersection traversal',
                                         'numeric_conditions': []},
                              'judgment_calls_needed': []},
                'parameter_refs': parameters}
    r3 = write('template.json', template)
    bindings = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'],
                'status': 'draft',
                'established_contexts': ['authored two-way intersection; verify original physical highway, centerline and direction before legal use'],
                'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
                'context_refs': [],
                'fixed_parameters': [{'name': 'intersection_authored', 'value': True,
                                      'rationale': 'Exact construction requests an intersection; original physical source review remains required'}],
                'variable_parameters': [dict(item, used_by_laws=[LAW['id']]) for item in parameters]}
    r4 = write('bindings.json', bindings)
    recording = json.loads((FOLDER / 'selected-construction-probe_01.json').read_text())['recording_description']

    def values(interval):
        return {'requested_left_interval': variable('controller', interval, 'categorical'),
                'observed_left_occupancy': variable('subject_behavior', None, 'per frame'),
                'observed_intersection_zone': variable('world_setup', None, 'source review')}

    cases = [{'case_id': AID + '__baseline', 'target_law_id': None,
              'target_type': 'baseline', 'rationale': 'Neutral unselected context.',
              'variable_assignments': values('none'),
              'unresolved_judgment_calls': [], 'recording_description': recording}]
    for suffix, interval, target_type in (('probe_01', 'none', 'compliant_attempt'),
                                          ('probe_02', 'approach', 'violating_attempt'),
                                          ('probe_03', 'traversal', 'violating_attempt')):
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW['id'],
                      'target_type': target_type,
                      'rationale': 'Compare requested left-side interval with the same authored intersection, actor, cameras and 30-second clock; original motion and legal outcome remain unobserved.',
                      'variable_assignments': values(interval),
                      'unresolved_judgment_calls': [],
                      'paired_probe_id': AID + '__intersection_zone_comparison',
                      'deliberate_differences': ['requested_left_interval'],
                      'probe': {'primary_variable': 'requested_left_interval',
                                'comparison_or_standard': 'right-side approach versus requested left-side approach or traversal',
                                'target_value_or_branch': interval},
                      'recording_description': recording})
    r5 = write('cases.json', {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'],
                              'status': 'draft', 'cases': cases, 'sweep_specs': []})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
          'assignment_id': AID, 'status': 'draft_selected_delivery',
          'stages': {'relevance_batch': r1, 'relevance': r2, 'template': r3,
                     'judgment_observables': [], 'bindings': r4, 'cases': r5}})
    print(json.dumps({'selected_cases': 3, 'judgment_phrases': 0}))


if __name__ == '__main__':
    main()
