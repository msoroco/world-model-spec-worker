"""Bind the exact school-bus speed statute and unresolved original trip context."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
LAW = 'NRS-484B-360-1'
ACTOR = 'school_bus_driver'
TEMPLATE = LAW + '@' + ACTOR
PHRASES = [('when transporting pupils to and from school',
            'Original pupils aboard and school-trip purpose require independent source review.')]


def write(name, value):
    path = FOLDER / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(FOLDER)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    quote = assignment['law']['text']
    original = json.loads((FOLDER / 'proposals/cases.json').read_text())
    selected = original['cases']
    description = selected[0]['recording_description']
    relevance = {'cell_id': 'C230241', 'actor': ACTOR, 'status': 'draft',
      'relevant_laws': [{'law_id': LAW, 'quote': quote, 'applies_to': [ACTOR],
                         'relevance_type': 'specific_match', 'confidence': 'medium',
                         'notes': 'School bus identity and pupil-trip purpose require original source review; ice cream truck is fixed cell context, not a speed-law condition.'}],
      'borderline_excluded': []}
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
      'status': 'draft', 'quote': quote,
      'structure': {
        'activation': {'source_clause': 'A school bus',
                       'description': 'Confirm exact Native bus class and original school transportation context.'},
        'obligation': {'source_clause': 'shall not exceed: A speed of 55 miles per hour',
                       'description': 'Measure every original post-tick velocity sample against statutory 55 mph; no requested-speed verdict.'},
        'exceptions': [],
        'timing': {'source_clause': 'when transporting pupils to and from school',
                   'description': 'Review full original trip interval and pupil occupancy.'},
        'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in PHRASES]},
      'parameter_refs': []}
    bindings = {'cell_id': 'C230241', 'actor': ACTOR, 'status': 'draft',
      'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
      'context_refs': [], 'fixed_parameters': [],
      'variable_parameters': [
        {'name': 'requested_speed_mph', 'kind': 'controller',
         'range_or_domain': '52 or 58 mph request; actual original speed measured independently',
         'used_by_laws': [LAW]},
        {'name': 'school_trip_and_ice_cream_control', 'kind': 'world_setup',
         'range_or_domain': 'same school transport trip and separate ice cream truck',
         'used_by_laws': [LAW]}]}
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None,
      'target_type': 'baseline', 'rationale': 'Neutral unselected school-bus route context.',
      'variable_assignments': deepcopy(selected[0]['variable_assignments']),
      'recording_description': description,
      'unresolved_judgment_calls': [phrase for phrase, _ in PHRASES]}
    baseline['variable_assignments']['requested_speed_mph']['value'] = None
    for case in selected:
        case['unresolved_judgment_calls'] = [phrase for phrase, _ in PHRASES]
    cases = {'format': 'worker-case-proposals', 'cell_id': 'C230241',
      'actor': ACTOR, 'law_id': LAW, 'status': 'draft',
      'cases': [baseline, *selected],
      'sweep_specs': [{'sweep_id': AID + '__trip_source_review',
                       'target_law_id': LAW, 'status': 'incomplete',
                       'judgment_refs': [{'phrase': phrase, 'note': note} for phrase, note in PHRASES],
                       'rationale': 'The 52/58 mph pair is a controlled request contrast; original pupil and trip review remain open.',
                       'missing_inputs': ['Original physical school bus and pupil camera pixels',
                                          'Independent school trip purpose source']}],
      'sweeps_expanded': True}
    refs = {'relevance_batch': write('relevance_batch.json', relevance),
            'relevance': write('relevance.json', relevance),
            'template': write('template.json', template)}
    judgment = []
    for index, (phrase, note) in enumerate(PHRASES):
        obj = {'template_id': TEMPLATE, 'phrase': phrase, 'note': note,
          'status': 'draft',
          'observable_requirements': {
            'observables': [{'name': 'bus_speed_mph', 'unit': 'mph',
                             'description': 'Source-joined original post-tick bus velocity magnitude.'}],
            'context_inputs': [{'name': 'pupil_trip_context', 'unit': 'structured',
                                'description': 'Independent original bus, pupil occupancy and trip-purpose review.'}],
            'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': 'camera_frame_join', 'unit': 'structured',
                                 'description': 'Original synchronized four-camera 600-frame measurement.'}],
            'limitations': ['Synthetic pupil fixture does not establish original school transport.',
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
