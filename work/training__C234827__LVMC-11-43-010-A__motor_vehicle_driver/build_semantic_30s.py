"""Build source-bound rotary direction semantic proposals for the selected pair."""
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
                      'notes': 'Exact roundabout direction clause; actual within-roundabout motion requires original Native evidence.'}],
                 'borderline_excluded': []}
    r1 = write('relevance-batch.json', relevance)
    r2 = write('relevance.json', relevance)
    parameters = [
        {'name': 'requested_rotation', 'kind': 'controller',
         'range_or_domain': ['counterclockwise', 'clockwise']},
        {'name': 'observed_signed_rotation', 'kind': 'subject_behavior',
         'range_or_domain': 'source-derived continuous angular position and heading progression, initially unknown'},
        {'name': 'observed_roundabout_occupancy', 'kind': 'subject_behavior',
         'range_or_domain': 'source-derived original body and map readback, initially unknown'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW['id'], 'actor': ASSIGNMENT['actor'],
                'quote': LAW['text'], 'status': 'draft',
                'structure': {'law_id': LAW['id'],
                              'activation': {'condition': 'vehicle travels within a roundabout',
                                             'numeric_conditions': []},
                              'obligation': {'description': 'all vehicular travel within the roundabout shall be counterclockwise',
                                             'type': 'must', 'numeric_conditions': []},
                              'exceptions': [],
                              'timing': {'description': 'direction is assessed during each interval of actual roundabout travel',
                                         'numeric_conditions': []},
                              'judgment_calls_needed': []},
                'parameter_refs': parameters}
    r3 = write('template.json', template)
    bindings = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'],
                'status': 'draft',
                'established_contexts': ['authored four-quarter rotary road; verify original Native geometry and island before selection'],
                'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
                'context_refs': [],
                'fixed_parameters': [{'name': 'roundabout_authored', 'value': True,
                                      'rationale': 'Exact selected construction requests an island and circulatory roadway; Native readback remains required'}],
                'variable_parameters': [dict(item, used_by_laws=[LAW['id']]) for item in parameters]}
    r4 = write('bindings.json', bindings)
    recording = json.loads((FOLDER / 'selected-construction-witness_1.json').read_text())['recording_description']

    def values(direction):
        return {'requested_rotation': variable('controller', direction, 'categorical'),
                'observed_signed_rotation': variable('subject_behavior', None, 'radians'),
                'observed_roundabout_occupancy': variable('subject_behavior', None, 'boolean')}

    cases = [{'case_id': AID + '__baseline', 'target_law_id': None,
              'target_type': 'baseline',
              'rationale': 'Outside-roundabout neutral comparison context; unselected.',
              'variable_assignments': values('counterclockwise'),
              'unresolved_judgment_calls': [], 'recording_description': recording}]
    for suffix, direction, target_type in (('witness_1', 'counterclockwise', 'compliant_attempt'),
                                           ('witness_2', 'clockwise', 'violating_attempt')):
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW['id'],
                      'target_type': target_type,
                      'rationale': 'Compare requested rotation while holding frozen cell, island, lane radius, actor, cameras and 30-second clock fixed; original motion and legal outcome remain unobserved.',
                      'variable_assignments': values(direction),
                      'unresolved_judgment_calls': [],
                      'paired_probe_id': AID + '__rotation_pair',
                      'deliberate_differences': ['requested_rotation'],
                      'probe': {'primary_variable': 'requested_rotation',
                                'comparison_or_standard': 'counterclockwise versus clockwise travel within the same authored roundabout',
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
