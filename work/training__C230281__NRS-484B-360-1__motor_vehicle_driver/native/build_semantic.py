"""Bind the exact school-bus speed statute and unresolved original trip context."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
LAW = 'NRS-484B-360-1'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW + '@' + ACTOR
PHRASES = [('A school bus',
            'The judged motor-vehicle driver must be source-joined to an independently confirmed school bus.'),
           ('when transporting pupils to and from school',
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
    selected = [case for case in original['cases'] if case['target_type'] != 'baseline']
    description = selected[0]['recording_description']
    relevance = {'cell_id': 'C230281', 'actor': ACTOR, 'status': 'draft',
      'relevant_laws': [{'law_id': LAW, 'quote': quote, 'applies_to': [ACTOR],
                         'relevance_type': 'specific_match', 'confidence': 'medium',
                         'notes': 'Frozen motor_vehicle_driver is not automatically a bus driver; bus design, driver join, pupils and trip purpose require original source review.'}],
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
    bindings = {'cell_id': 'C230281', 'actor': ACTOR, 'status': 'draft',
      'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
      'context_refs': [], 'fixed_parameters': [],
      'variable_parameters': [
        {'name': 'requested_speed_mph', 'kind': 'controller',
         'range_or_domain': '53, 55 or 57 mph request; actual original speed measured independently',
         'used_by_laws': [LAW]}]}
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None,
      'target_type': 'baseline', 'rationale': 'Neutral unselected school-bus route context.',
      'variable_assignments': deepcopy(selected[0]['variable_assignments']),
      'recording_description': description,
      'unresolved_judgment_calls': [phrase for phrase, _ in PHRASES]}
    baseline['variable_assignments']['requested_speed_mph']['value'] = None
    for case in selected:
        case['unresolved_judgment_calls'] = [phrase for phrase, _ in PHRASES]
        case['probe'] = {'primary_variable': 'requested_speed_mph',
                         'comparison_or_standard': 'original measured bus velocity against 55 mph statutory text',
                         'target_value_or_branch': case['variable_assignments']['requested_speed_mph']['value']}
    cases = {'format': 'worker-case-proposals', 'cell_id': 'C230281',
      'actor': ACTOR, 'law_id': LAW, 'status': 'draft',
      'cases': [baseline, *selected],
      'sweep_specs': [{'sweep_id': AID + '__trip_source_review',
                       'target_law_id': LAW, 'status': 'incomplete',
                       'judgment_refs': [{'phrase': phrase, 'note': note} for phrase, note in PHRASES],
                       'rationale': 'The 53/55/57 mph triplet is a controlled request contrast; original bus driver, pupil and trip review remain open.',
                       'missing_inputs': ['Original school-bus design and driver join; original pupil camera pixels',
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
            'observables': [{'name': 'school_bus_speed', 'unit': 'mph',
                             'description': 'Source-joined original post-tick bus velocity magnitude.'}],
            'context_inputs': [{'name': 'school_bus_driver_and_pupil_trip_review', 'unit': 'structured',
                                'description': 'Independent original bus design, driver join, pupil occupancy and trip-purpose review.'}],
            'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': 'school_bus_speed', 'unit': 'mph',
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
