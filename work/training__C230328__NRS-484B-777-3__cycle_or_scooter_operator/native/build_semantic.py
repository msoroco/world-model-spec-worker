"""Bind the exact statute to the two diagnostic cases without a legal verdict."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
LAW = 'NRS-484B-777-3'
ACTOR = 'cycle_or_scooter_operator'
TEMPLATE = LAW + '@' + ACTOR
PHRASES = [
    ('more than two abreast', 'Original rider identities, longitudinal intervals, lateral bearings and grouping need review.'),
    ('except on paths or parts of roadways set aside for the exclusive use of bicycles, electric bicycles and electric scooters',
     'Original roadway designation and exclusive-use status require independent source review.'),
]


def write(name, value):
    path = FOLDER / 'proposals' / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(FOLDER)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    quote = assignment['law']['text']
    original = json.loads((FOLDER / 'proposals/cases.json').read_text())
    selected = original['cases']
    description = selected[0]['recording_description']
    relevance = {'cell_id': 'C230328', 'actor': ACTOR, 'status': 'draft',
      'relevant_laws': [{'law_id': LAW, 'quote': quote, 'applies_to': [ACTOR],
                         'relevance_type': 'specific_match', 'confidence': 'medium',
                         'notes': 'Roadway bicycle rider count and exclusive-use designation require original source review.'}],
      'borderline_excluded': []}
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
      'status': 'draft', 'quote': quote,
      'structure': {
        'activation': {'source_clause': 'Persons riding bicycles, electric bicycles or electric scooters upon a roadway',
                       'description': 'Observe qualifying rider identity and roadway occupancy from original sources.'},
        'obligation': {'source_clause': 'shall not ride more than two abreast',
                       'description': 'Source-join rider intervals and lateral arrangement; no geometric legal cutoff.'},
        'exceptions': [{'source_clause': 'except on paths or parts of roadways set aside for the exclusive use of bicycles, electric bicycles and electric scooters',
                        'description': 'Roadway designation and exclusive-use source review remain required.'}],
        'timing': {'source_clause': 'upon a roadway',
                   'description': 'Review the full 600-frame original roadway interval.'},
        'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in PHRASES]},
      'parameter_refs': []}
    bindings = {'cell_id': 'C230328', 'actor': ACTOR, 'status': 'draft',
      'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
      'context_refs': [], 'fixed_parameters': [],
      'variable_parameters': [
        {'name': 'requested_rider_count', 'kind': 'controller',
         'range_or_domain': 'two or three riders; actual identities and geometry measured',
         'used_by_laws': [LAW]},
        {'name': 'route_and_device_class', 'kind': 'world_setup',
         'range_or_domain': 'same reviewed roadway, qualifying bicycle devices and exclusive-use survey',
         'used_by_laws': [LAW]}]}
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None,
      'target_type': 'baseline', 'rationale': 'Neutral unselected roadway bicycle context.',
      'variable_assignments': deepcopy(selected[0]['variable_assignments']),
      'recording_description': description,
      'unresolved_judgment_calls': [phrase for phrase, _ in PHRASES]}
    baseline['variable_assignments']['requested_rider_count']['value'] = None
    for case in selected:
        case['unresolved_judgment_calls'] = [phrase for phrase, _ in PHRASES]
    cases = {'format': 'worker-case-proposals', 'cell_id': 'C230328',
      'actor': ACTOR, 'law_id': LAW, 'status': 'draft',
      'cases': [baseline, *selected],
      'sweep_specs': [{'sweep_id': AID + '__abreast_source_review',
                       'target_law_id': LAW, 'status': 'incomplete',
                       'judgment_refs': [{'phrase': phrase, 'note': note} for phrase, note in PHRASES],
                       'rationale': 'The two/three rider pair is a count contrast; original rider, roadway and exception review remain open.',
                       'missing_inputs': ['Original physical rider and camera pixels',
                                          'Independent roadway, exclusive-use and abreast judgment']}],
      'sweeps_expanded': True}
    refs = {'relevance_batch': write('relevance_batch.json', relevance),
            'relevance': write('relevance.json', relevance),
            'template': write('template.json', template)}
    judgment = []
    for index, (phrase, note) in enumerate(PHRASES):
        obj = {'template_id': TEMPLATE, 'phrase': phrase, 'note': note,
          'status': 'draft',
          'observable_requirements': {
            'observables': [{'name': 'rider_pose', 'unit': 'structured',
                             'description': 'Source-joined original rider identities, intervals and lateral bearings.'}],
            'context_inputs': [{'name': 'roadway_exception_context', 'unit': 'structured',
                                'description': 'Original public roadway and exclusive-use designation sources.'}],
            'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': 'camera_frame_join', 'unit': 'structured',
                                 'description': 'Original synchronized four-camera 600-frame measurement.'}],
            'limitations': ['Geometry does not decide legal abreast grouping or the exclusive-use exception.',
                            'Original physical and independent legal review pending.']}}
        judgment.append(write(f'judgment_observables_{index}.json', obj))
    refs['judgment_observables'] = judgment
    refs['bindings'] = write('bindings.json', bindings)
    refs['cases'] = write('cases.json', cases)
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': AID, 'stages': refs})
    print(json.dumps({'stages': len(refs), 'selected': len(selected)}))


if __name__ == '__main__':
    main()
