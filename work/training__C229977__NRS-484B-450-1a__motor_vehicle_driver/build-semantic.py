"""Author source-bounded semantic proposals for selected sidewalk probes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = SOURCE['law']
LAW_ID = SOURCE['law_id']
ACTOR = SOURCE['actor']
TEMPLATE_ID = LAW_ID + '@' + ACTOR
OUT = HERE / 'proposals'
OUT.mkdir(exist_ok=True)


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': SOURCE['cell_id'], 'actor': ACTOR,
                 'status': 'draft', 'relevant_laws': [{
                     'law_id': LAW_ID, 'quote': LAW['text'], 'applies_to': [ACTOR],
                     'relevance_type': 'specific_match', 'confidence': 'high',
                     'notes': 'Frozen road/sidewalk stop cell; original surface and exception authority remain source-review questions.'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance_batch.json', relevance)
    write('relevance.json', relevance)
    judgments = [
        ('on a sidewalk', 'Native map sidewalk lane alone does not establish the legal surface; acquire highway, property and pedestrian-use sources.'),
        ('necessary to avoid conflict with other traffic', 'Observed traffic history and necessity must be reviewed without a numeric legal cutoff.'),
        ('in compliance with law or the directions of a police officer or official traffic-control device', 'Identify governing authority and observe its direction and compliance from original sources.'),
        ('does not impede the normal and reasonable movement of pedestrians', 'Subsection 3 applies to a bicycle, electric bicycle or electric scooter, outside this motor-vehicle actor; do not infer a width cutoff.'),
    ]
    parameters = [
        {'name': 'sidewalk_vehicle_occupancy', 'kind': 'world_setup',
         'range_or_domain': 'requested off-sidewalk or on-sidewalk stop; physical overlap measured from original body and map sources'},
        {'name': 'other_traffic_actor_present', 'kind': 'world_setup',
         'range_or_domain': 'absent or stationary same-lane vehicle request; actual conflict and necessity require original evidence review'}]
    template = {
        'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
        'status': 'draft', 'quote': LAW['text'],
        'structure': {
            'law_id': LAW_ID,
            'activation': {'condition': 'The subject motor vehicle stops, stands or parks on a source-verified sidewalk.',
                           'numeric_conditions': []},
            'obligation': {'description': 'Do not stop, stand or park a vehicle on a sidewalk unless the stated exception applies.',
                           'type': 'must_not', 'numeric_conditions': []},
            'exceptions': [
                {'description': 'Necessary to avoid conflict with other traffic',
                 'source_clause': 'when necessary to avoid conflict with other traffic'},
                {'description': 'Compliance with governing law',
                 'source_clause': 'in compliance with law'},
                {'description': 'Compliance with police officer direction',
                 'source_clause': 'directions of a police officer'},
                {'description': 'Compliance with official traffic-control device direction',
                 'source_clause': 'official traffic-control device'},
                {'description': 'Subsection 3 cycle and scooter parking without impeding pedestrian movement, outside this actor',
                 'source_clause': 'A person may park a bicycle, an electric bicycle or an electric scooter on a sidewalk provided that the bicycle, electric bicycle or electric scooter does not impede the normal and reasonable movement of pedestrians on the sidewalk.'}],
            'timing': {'description': 'Assess each observed stop or stand interval; no statutory numeric duration or gap cutoff is supplied.',
                       'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in judgments]},
        'parameter_refs': parameters}
    template_ref = write('template.json', template)
    judgment_refs = []
    for index, (phrase, note) in enumerate(judgments, 1):
        observables = [{'name': 'vehicle_body_pose', 'unit': 'structured',
                        'description': 'Original source-joined body, map and authority context for ' + phrase},
                       {'name': 'sidewalk_overlap', 'unit': 'm2',
                        'description': 'Diagnostic body-footprint overlap, separate from legal surface determination'}]
        judgment_refs.append(write('judgment-' + str(index) + '.json', {
            'template_id': TEMPLATE_ID, 'phrase': phrase, 'note': note,
            'status': 'draft', 'observable_requirements': {
                'observables': observables, 'context_inputs': [],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': observables,
                'limitations': ['Synthetic CPU sources and motor-vehicle scope do not establish this legal judgment.']}}))
    bindings_ref = write('bindings.json', {
        'cell_id': SOURCE['cell_id'], 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [], 'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{**item, 'used_by_laws': [LAW_ID]} for item in parameters]})
    description = json.loads((HERE / 'selected-probe-1/construction.json').read_text())['recording_description']
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
              'target_type': 'baseline', 'rationale': 'Unselected frozen-cell neutral reference.',
              'variable_assignments': {'sidewalk_vehicle_occupancy': {'kind': 'world_setup', 'value': None},
                                       'other_traffic_actor_present': {'kind': 'world_setup', 'value': None}},
              'unresolved_judgment_calls': [phrase for phrase, _ in judgments],
              'recording_description': description}]
    for index, occupied in ((1, False), (2, True)):
        case_id = HERE.name + f'__probe_{index}'
        cases.append({'case_id': case_id, 'target_law_id': LAW_ID,
                      'target_type': 'boundary_probe',
                      'rationale': 'Source-joined sidewalk occupancy contrast; no legal outcome label.',
                      'variable_assignments': {'sidewalk_vehicle_occupancy': {'kind': 'world_setup', 'value': occupied},
                                               'other_traffic_actor_present': {'kind': 'world_setup', 'value': None}},
                      'unresolved_judgment_calls': [phrase for phrase, _ in judgments],
                      'paired_probe_id': 'sidewalk-stop-location',
                      'deliberate_differences': ['sidewalk_vehicle_occupancy'],
                      'probe': {'primary_variable': 'sidewalk_vehicle_occupancy',
                                'comparison_or_standard': 'Original body and surface source comparison without a legal cutoff',
                                'target_value_or_branch': 'requested sidewalk occupancy' if occupied else 'requested off-sidewalk stop'},
                      'recording_description': description})
    for present in (False, True):
        suffix = 'traffic_conflict_present' if present else 'traffic_conflict_absent'
        traffic_description = json.loads((HERE / ('selected-' + suffix.replace('_', '-') + '/construction.json')).read_text())['recording_description']
        cases.append({'case_id': HERE.name + '__' + suffix,
                      'target_law_id': LAW_ID, 'target_type': 'boundary_probe',
                      'rationale': 'Controlled other-traffic actor source contrast; necessity and legal exception remain unverified.',
                      'variable_assignments': {
                          'sidewalk_vehicle_occupancy': {'kind': 'world_setup', 'value': True},
                          'other_traffic_actor_present': {'kind': 'world_setup', 'value': present}},
                      'unresolved_judgment_calls': [phrase for phrase, _ in judgments],
                      'paired_probe_id': 'traffic-conflict-context',
                      'deliberate_differences': ['other_traffic_actor_present'],
                      'probe': {'primary_variable': 'other_traffic_actor_present',
                                'comparison_or_standard': 'Original other-traffic trajectory and subject-stop evidence, without a legal necessity verdict',
                                'target_value_or_branch': suffix},
                      'recording_description': traffic_description})
    cases_ref = write('cases.json', {
        'status': 'draft', 'assignment_id': HERE.name, 'law_id': LAW_ID,
        'cell_id': SOURCE['cell_id'], 'actor': ACTOR,
        'cases': cases, 'sweep_specs': [{
            'sweep_id': 'c229977-judgment-' + str(index), 'target_law_id': LAW_ID,
            'judgment_refs': [{'phrase': phrase, 'note': note}],
            'status': 'incomplete',
            'rationale': 'Original source, physical range and actor-compatible branch binding remain unavailable.',
            'missing_inputs': ['Original authority, surface and actor-compatible source review for ' + phrase]}
            for index, (phrase, note) in enumerate(judgments, 1)],
        'sweeps_expanded': True})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': HERE.name,
        'stages': {'relevance_batch': relevance_ref, 'relevance': relevance_ref,
                   'template': template_ref, 'judgment_observables': judgment_refs,
                   'bindings': bindings_ref, 'cases': cases_ref}})


if __name__ == '__main__':
    main()
