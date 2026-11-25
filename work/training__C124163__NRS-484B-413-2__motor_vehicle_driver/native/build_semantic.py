"""Author canonical semantic proposals for both exact statutory distance forks."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
AID = ROOT.name
LAW = 'NRS-484B-413-2'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW+'@'+ACTOR
PHRASES = [
    ('A signal of intention to turn right or left, or otherwise turn a vehicle from a direct course',
     'Original visible signal and observed change from direct course require independent source review.'),
    ('in a business or residential district',
     'District classification must be established from original route context.'),
    ('in any other area',
     'Other-area classification must be established from original route context.'),
    ('regardless of the weather',
     'Weather is source context and cannot waive either distance.'),
]


def write(name, value):
    path = ROOT/'proposals'/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')
    return {'path': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((REPO/'inputs'/AID/'assignment.json').read_text())
    quote = assignment['law']['text']
    original = json.loads((ROOT/'proposals/cases.json').read_text())
    selected = original['cases']
    description = selected[0]['recording_description']
    relevance = {'cell_id': 'C124163', 'actor': ACTOR, 'status': 'draft',
      'relevant_laws': [{'law_id': LAW, 'quote': quote, 'applies_to': [ACTOR],
                        'relevance_type': 'specific_match', 'confidence': 'medium',
                        'notes': 'Same-cell left turn and signal request; original visible signal, district and turn onset remain unverified.'}],
      'borderline_excluded': []}
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
      'status': 'draft', 'quote': quote,
      'structure': {
        'activation': {'source_clause': 'A signal of intention to turn right or left, or otherwise turn a vehicle from a direct course',
                       'description': 'Original change of course and signal visibility need review.'},
        'obligation': {'source_clause': 'shall be given continuously during not less than the last 100 feet traveled in a business or residential district and not less than the last 300 feet traveled in any other area',
                       'description': 'Measure continuous signal-active path length from original onset to original course change, conditional on district.',
                       'district_distance': {'variable': 'continuous_signal_distance_ft', 'operator': '>=', 'value': 100, 'unit': 'ft'},
                       'other_distance': {'variable': 'continuous_signal_distance_ft', 'operator': '>=', 'value': 300, 'unit': 'ft'}},
        'exceptions': [],
        'timing': {'source_clause': 'prior to changing the course of a vehicle. This rule shall be observed, regardless of the weather.',
                   'description': 'Continuous signal duration is measured backward from observed course-change onset; no weather waiver.'},
        'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in PHRASES]},
      'parameter_refs': []}
    bindings = {'cell_id': 'C124163', 'actor': ACTOR, 'status': 'draft',
      'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
      'context_refs': [], 'fixed_parameters': [],
      'variable_parameters': [
        {'name': 'requested_signal_distance_m', 'kind': 'controller',
         'range_or_domain': '20, 30.48, 35.2, 70, 91.44 or 100 m request; observed distance measured separately',
         'used_by_laws': [LAW]},
        {'name': 'district_class', 'kind': 'world_setup',
         'range_or_domain': 'business or residential district; other area',
         'used_by_laws': [LAW]},
        {'name': 'weather', 'kind': 'world_setup',
         'range_or_domain': 'clear or rain; rule never waived', 'used_by_laws': [LAW]}]}
    baseline = {'case_id': AID+'__baseline', 'target_law_id': None,
      'target_type': 'baseline', 'rationale': 'Neutral unselected median-opening route context.',
      'variable_assignments': deepcopy(selected[0]['variable_assignments']),
      'recording_description': description,
      'unresolved_judgment_calls': [phrase for phrase, _ in PHRASES]}
    baseline['variable_assignments']['requested_signal_distance_m']['value'] = None
    for case in selected:
        condition = case['case_id'].rsplit('__', 1)[-1]
        district = 'other' if condition.startswith('other_') else 'district'
        threshold = 300 if district == 'other' else 100
        value_m = case['variable_assignments']['requested_signal_distance_m']['value']
        case['target_type'] = 'boundary_probe'
        case['paired_probe_id'] = AID+'__'+district+'_distance_triplet'
        case['epsilon_used'] = {'value': 0.4/.3048, 'unit': 'ft',
                                'rationale': '20 Hz at 8 m/s gives 0.4 m sampling granularity; not a legal tolerance.'}
        case['probe'].update(threshold_ref='obligation.other_distance' if district == 'other' else 'obligation.district_distance',
                             operator='>=', unit='ft',
                             test_value=threshold if condition.endswith('_at') else round(value_m/.3048, 8))
        case['unresolved_judgment_calls'] = [phrase for phrase, _ in PHRASES]
    cases = {'format': 'worker-case-proposals', 'cell_id': 'C124163',
      'actor': ACTOR, 'law_id': LAW, 'status': 'draft',
      'cases': [baseline, *selected],
      'sweep_specs': [{'sweep_id': AID+'__original_context_review',
                       'target_law_id': LAW, 'status': 'incomplete',
                       'judgment_refs': [{'phrase': phrase, 'note': note} for phrase, note in PHRASES],
                       'rationale': 'Six source-distance boundary requests do not settle visible signal, district or weather source judgments.',
                       'missing_inputs': ['Original signal pixels and independent onset review',
                                          'Independent district/weather route review',
                                          'Original accepted-recording source hashes']}],
      'sweeps_expanded': True}
    refs = {'relevance_batch': write('relevance_batch.json', relevance),
            'relevance': write('relevance.json', relevance),
            'template': write('template.json', template)}
    judgments = []
    for i, (phrase, note) in enumerate(PHRASES):
        observable = 'sig.turn_indicator' if i == 0 else 'env.precipitation'
        obj = {'template_id': TEMPLATE, 'phrase': phrase, 'note': note,
          'status': 'draft',
          'observable_requirements': {
            'observables': [{'name': observable, 'unit': 'structured',
                             'description': 'Original source-joined signal, location and weather review.'}],
            'context_inputs': [{'name': 'district_weather_review', 'unit': 'structured',
                                'description': 'Independent original district/weather source review.'}],
            'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': 'kin.path_length', 'unit': 'structured',
                                 'description': 'Post-tick Native traveled distance with frame join.'}],
            'limitations': ['Synthetic fixture does not establish visible signaling or legal outcome.',
                            'Right, hand-signal and lane-change alternatives require further original review.']}}
        judgments.append(write(f'judgment_observables_{i}.json', obj))
    refs['judgment_observables'] = judgments
    refs['bindings'] = write('bindings.json', bindings)
    refs['cases'] = write('cases.json', cases)
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': AID, 'stages': refs})
    print(json.dumps({'stages': len(refs), 'selected': len(selected)}))


if __name__ == '__main__':
    main()
