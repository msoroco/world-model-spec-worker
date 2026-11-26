"""Author exact law/cell semantic proposals without a legal verdict."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
PLAN = json.loads((HERE / 'case-plan.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
TEMPLATE_ID = LAW_ID + '@' + ACTOR
OUT = HERE / 'proposals'
OUT.mkdir(exist_ok=True)


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR,
                 'status': 'draft', 'relevant_laws': [{
                     'law_id': LAW_ID, 'quote': LAW['text'], 'applies_to': [ACTOR],
                     'relevance_type': 'specific_match', 'confidence': 'high',
                     'notes': 'Frozen mountain road/travel/blind-pedestrian driver cell; original marker and blindness source review required.'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance_batch.json', relevance)
    write('relevance.json', relevance)
    judgments = [
        ('wholly or partially blind', 'Blindness needs an independent original source; a walker blueprint is not proof.'),
        ('white in color, or white tipped in red', 'Authored marker strokes need original pixel and source review.'),
        ('being assisted by a person with wisdom', 'A second walker is only an assistance request.'),
        ('immediately come to a full stop', 'Measure reaction and stop timing without inventing a numeric legal limit.'),
        ('such precautions before proceeding as may be necessary', 'Review release, gap, encounter history and injury risk without a numeric legal cutoff.'),
    ]
    parameters = [
        {'name': 'cane_or_assistance', 'kind': 'world_setup',
         'range_or_domain': 'red-tipped white cane, white cane, assisted person; each source-reviewed'},
        {'name': 'blindness_extent', 'kind': 'world_setup',
         'range_or_domain': 'wholly or partially blind; source-reviewed'},
        {'name': 'driver_behavior', 'kind': 'controller',
         'range_or_domain': 'stop-clear, no-stop, early-release request'},
    ]
    template = {
        'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
        'status': 'draft', 'quote': LAW['text'],
        'structure': {
            'law_id': LAW_ID,
            'activation': {'condition': 'A driver approaches or contacts a wholly or partially blind person with the named cane or assistance.',
                           'numeric_conditions': []},
            'obligation': {'description': 'Come to a full stop and take precautions before proceeding to avoid accident or injury.',
                           'type': 'must', 'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Immediately stop and take necessary precautions before proceeding; no numeric legal cutoff supplied.',
                       'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                      for phrase, note in judgments],
        }, 'parameter_refs': parameters}
    template_ref = write('template.json', template)
    judgment_refs = []
    for index, (phrase, note) in enumerate(judgments, 1):
        observables = [{'name': name, 'unit': 'structured',
                        'description': 'Original source and pixel review for ' + phrase}
                       for name in ('vehicle_person_pose', 'blind_person_source_context')]
        judgment_refs.append(write('judgment-' + str(index) + '.json', {
            'template_id': TEMPLATE_ID, 'phrase': phrase, 'note': note,
            'status': 'draft',
            'observable_requirements': {
                'observables': observables, 'context_inputs': [],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': observables,
                'limitations': ['Synthetic CPU sources do not establish this legal judgment.'],
            }}))
    bindings = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR,
                'status': 'draft', 'established_contexts': [],
                'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [],
                'variable_parameters': [{**item, 'used_by_laws': [LAW_ID]}
                                        for item in parameters]}
    bindings_ref = write('bindings.json', bindings)
    description = json.loads((HERE / 'draft-exact/probe_1/primary/construction.json').read_text())['recording_description']
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
              'target_type': 'baseline',
              'rationale': 'Unselected frozen-cell reference, no delivery recording.',
              'variable_assignments': {item['name']: {'kind': item['kind'], 'value': None}
                                       for item in parameters},
              'unresolved_judgment_calls': [phrase for phrase, _ in judgments],
              'recording_description': description}]
    for planned in PLAN['cases']:
        suffix = planned['case_id'].rsplit('__', 1)[-1]
        construction = json.loads((HERE / 'draft-exact' / suffix / 'primary/construction.json').read_text())
        request = planned['source_context_request']
        assignments = {item['name']: {'kind': item['kind'], 'value': request[item['name']]}
                       for item in parameters}
        controlled = {'probe_1': 'driver_behavior', 'probe_2': 'driver_behavior',
                      'white_wholly': 'cane_or_assistance',
                      'white_partial': 'blindness_extent',
                      'assisted': 'cane_or_assistance',
                      'early_release': 'driver_behavior'}[suffix]
        cases.append({'case_id': planned['case_id'], 'target_law_id': LAW_ID,
                      'target_type': 'boundary_probe',
                      'rationale': planned['physical_target'] + '; source facts need independent review',
                      'variable_assignments': assignments,
                      'unresolved_judgment_calls': [phrase for phrase, _ in judgments],
                      'paired_probe_id': 'blind-person-' + suffix,
                      'deliberate_differences': [controlled],
                      'probe': {'primary_variable': controlled,
                                'comparison_or_standard': 'source-joined driver motion and marker-context contrast; no legal verdict',
                                'target_value_or_branch': suffix},
                      'recording_description': construction['recording_description']})
    cases_ref = write('cases.json', {
        'status': 'draft', 'assignment_id': HERE.name, 'law_id': LAW_ID,
        'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR,
        'cases': cases,
        'sweep_specs': [{
            'sweep_id': 'c129273-' + str(index), 'target_law_id': LAW_ID,
            'judgment_refs': [{'phrase': phrase, 'note': note}],
            'status': 'incomplete',
            'rationale': 'Original Native and person-source verification and a feasible physical range are unavailable.',
            'missing_inputs': ['Original source and physical range for ' + phrase]}
            for index, (phrase, note) in enumerate(judgments, 1)],
        'sweeps_expanded': True})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': HERE.name,
        'stages': {'relevance_batch': relevance_ref, 'relevance': relevance_ref,
                   'template': template_ref, 'judgment_observables': judgment_refs,
                   'bindings': bindings_ref, 'cases': cases_ref}})
    print(json.dumps({'selected_cases': len(cases) - 1,
                      'judgment_observables': len(judgment_refs)}))


if __name__ == '__main__':
    main()
