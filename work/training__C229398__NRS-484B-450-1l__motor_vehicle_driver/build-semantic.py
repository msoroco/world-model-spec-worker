"""Write source-quoted 450(1)(l) proposal stages for local review."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
ASSIGNMENT = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
LAW = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
TEXT = ASSIGNMENT['law']['text']
TEMPLATE = LAW + '@' + ACTOR
CASES = ('clear', 'stop', 'stand', 'park', 'traffic_conflict',
         'law_direction', 'police_direction', 'device_direction')


def write(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    desc = json.loads((HERE / 'selected-cases/clear/primary/construction.json').read_text())['recording_description']
    refs = {}
    relevance = {'cell_id': 'C229398', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'high',
            'notes': 'Frozen curb/parking cell; original highway designation, activity and exceptions remain for independent review.'}],
        'borderline_excluded': []}
    refs['relevance_batch'] = write('relevance-batch.json', relevance)
    refs['relevance'] = write('relevance.json', relevance)
    judgments = [
        ('highway side of any vehicle stopped or parked at the edge of or curb of a highway',
         'Survey original highway and curb authority, both full-body footprints and the curbside vehicle halt.'),
        ('stop, stand or park a vehicle',
         'Review original purpose, person, activity and rest duration without inventing a legal duration cutoff.'),
        ('necessary to avoid conflict with other traffic',
         'Review original traffic paths and causal necessity for the stopping position.'),
        ('in compliance with law',
         'Review the exact applicable lawful direction and its source.'),
        ('directions of a police officer',
         'Review original officer identity, authority, communication and scope.'),
        ('official traffic-control device',
         'Review original device identity, installation authority, pixels, conditions and effective instruction.')]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'status': 'draft', 'quote': TEXT,
        'structure': {'activation': {'description': 'Two source-identified stopped vehicles are on a highway; the subject may occupy the highway side of the curbside vehicle.',
                        'source_clause': 'On the highway side of any vehicle stopped or parked at the edge of or curb of a highway.'},
            'obligation': {'description': 'Do not stop, stand or park at the specified place except through an exact reviewed exception.',
                           'type': 'must_not', 'source_clause': 'A person shall not stop, stand or park a vehicle',
                           'numeric_conditions': []},
            'exceptions': [
                {'description': 'Review necessity to avoid traffic conflict.', 'source_clause': 'except when necessary to avoid conflict with other traffic'},
                {'description': 'Review compliance with other law.', 'source_clause': 'in compliance with law'},
                {'description': 'Review police officer direction.', 'source_clause': 'the directions of a police officer'},
                {'description': 'Review official device direction.', 'source_clause': 'official traffic-control device'}],
            'timing': {'description': 'Review original concurrent rest and longitudinal body overlap over the full 30 seconds; do not turn engineering stationarity tolerance into law.'},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                      for phrase, note in judgments]},
        'parameter_refs': [
            {'name': 'requested_rest_station', 'kind': 'controller',
             'range_or_domain': 'curb clear or abreast curbside vehicle'},
            {'name': 'requested_activity', 'kind': 'controller',
             'range_or_domain': 'stop, stand, park, or neutral request'},
            {'name': 'exception_context', 'kind': 'world_setup',
             'range_or_domain': 'traffic conflict, law, police or official device source review'},
            {'name': 'observed_highway_side_overlap', 'kind': 'subject_behavior',
             'range_or_domain': 'original joined two-body footprints and halt'}]}
    refs['template'] = write('template.json', template)
    observed = []
    for i, (phrase, note) in enumerate(judgments, 1):
        name = ('curb_geometry', 'activity_context', 'traffic_conflict_context',
                'law_compliance_context', 'police_direction_context',
                'device_direction_context')[i - 1]
        req = {'observables': [{'name': name, 'unit': 'structured',
                'description': 'Original synchronized source for ' + name}],
            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': name, 'unit': 'structured',
                'description': 'Retain original source and review join for ' + name}],
            'limitations': ['Diagnostic source shapes and synthetic pixels do not establish physical or legal acceptance.']}
        observed.append(write('judgment-%d.json' % i, {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note,
            'status': 'draft', 'observable_requirements': req}))
    refs['judgment_observables'] = observed
    binding = {'cell_id': 'C229398', 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE,
            'binding_kind': 'direct'}], 'context_refs': [],
        'fixed_parameters': [{'name': 'curbside_vehicle_context',
            'value': 'authored two-direction road, travel and curbside parking lanes with independently surveyed status',
            'rationale': 'Frozen cell; original curb, highway and parked vehicle remain for review.'}],
        'variable_parameters': [dict(ref, used_by_laws=[LAW])
            for ref in template['parameter_refs']]}
    refs['bindings'] = write('bindings.json', binding)
    variables = lambda suffix: {
        'requested_rest_station': {'kind': 'controller',
            'value': 'clear' if suffix == 'clear' else 'abreast'},
        'requested_activity': {'kind': 'controller',
            'value': 'neutral' if suffix == 'clear' else suffix if suffix in ('stop', 'stand', 'park') else 'park'},
        'exception_context': {'kind': 'world_setup',
            'value': suffix if suffix.endswith('direction') or suffix == 'traffic_conflict' else 'none_requested'},
        'observed_highway_side_overlap': {'kind': 'subject_behavior', 'value': None}}
    cases = [{'case_id': AID + '__baseline', 'target_law_id': None,
        'target_type': 'baseline',
        'rationale': 'Neutral curbside road reference; no selected recording.',
        'variable_assignments': variables('clear'),
        'unresolved_judgment_calls': [p for p, _ in judgments],
        'recording_description': desc}]
    for suffix in CASES:
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW,
            'target_type': 'boundary_probe',
            'paired_probe_id': 'highway-side-double-parking',
            'rationale': 'Request ' + suffix + ' and measure original curbside two-body overlap; retain independent activity/exception review.',
            'deliberate_differences': ['requested_rest_station', 'requested_activity', 'exception_context'],
            'variable_assignments': variables(suffix),
            'unresolved_judgment_calls': [p for p, _ in judgments],
            'recording_description': desc,
            'probe': {'primary_variable': 'observed_highway_side_overlap',
                'comparison_or_standard': 'original curbside vehicle and full-body footprint',
                'target_value_or_branch': suffix}})
    proposal = {'cell_id': 'C229398', 'actor': ACTOR, 'status': 'draft',
        'sweep_specs': [{'sweep_id': 'double-parking-activity-and-exception',
            'target_law_id': LAW, 'judgment_refs': [{'phrase': p, 'note': n}
                for p, n in judgments], 'status': 'incomplete',
            'rationale': 'Original Native and independent authority/context sources remain for local review.',
            'missing_inputs': ['Original highway, curb, activity and exception sources.']}],
        'sweeps_expanded': True, 'cases': cases}
    refs['cases'] = write('cases.json', proposal)
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': AID, 'stages': refs})
    print(json.dumps({'stages': 5 + len(observed), 'selected_cases': len(CASES)}))


if __name__ == '__main__':
    main()
