"""Author source-faithful CPU stage proposals for the exact taxi law."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
PROPOSALS = BASE / 'proposals'
ASSIGNMENT = json.loads((ROOT / 'inputs' / BASE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
ACTOR = ASSIGNMENT['actor']
LAW_ID = ASSIGNMENT['law_id']
TEMPLATE_ID = LAW_ID + '@' + ACTOR
JUDGMENTS = [
    {'phrase': 'taxicab stand so designated',
     'note': 'Original stand designation and street position require authority review.',
     'observables': ['ru.taxicab', 'st.curb_zone', 'dev.regulatory_sign',
                     'rel.occupies']},
    {'phrase': 'temporarily stopping in accordance with other regulations',
     'note': 'Original stop duration and other parking-rule authority require review.',
     'observables': ['drv.stopped', 'drv.standing_or_parked', 'kin.time']},
    {'phrase': 'actually engaged in expeditious loading or unloading of passengers',
     'note': 'Original participant activity and continuous loading interval require review.',
     'observables': ['sig.door_open', 'ru.occupant_count', 'kin.time']},
]


def save(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    return {'path': str(path.relative_to(BASE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    from build_cases_proposal import main as build_cases
    build_cases()
    relevance = {
        'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{
            'law_id': LAW_ID, 'quote': LAW['text'], 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'low',
            'notes': 'Taxi-stand cell is planning context; original taxi status, stand authority and activity still need source review.'}],
        'borderline_excluded': []}
    ref_batch = save('relevance-batch.json', relevance)
    ref_relevance = save('relevance.json', relevance)
    template = {
        'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
        'quote': LAW['text'], 'status': 'draft',
        'structure': {
            'law_id': LAW_ID,
            'activation': {
                'condition': 'operator of a taxicab stands or parks on a street at a place other than a designated taxicab stand',
                'numeric_conditions': []},
            'obligation': {
                'type': 'must_not',
                'description': 'taxicab operator must not stand or park on a street outside a designated stand',
                'source_clause': LAW['text'].split(' This provision')[0],
                'numeric_conditions': []},
            'exceptions': [{
                'trigger': 'temporarily stopping in accordance with other stopping or parking regulations while actually engaged in expeditious passenger loading or unloading',
                'effect': 'the outside-stand prohibition does not prevent that stop',
                'replacement_obligation': 'comply with other stopping and parking regulations and limit the stop to actual expeditious passenger loading or unloading',
                'source_clause': LAW['text'].split(' This provision ')[1]}],
            'timing': {
                'description': 'stand or park, or temporary stop during actual expeditious loading or unloading',
                'numeric_conditions': []},
            'judgment_calls_needed': [{k: item[k] for k in ('phrase', 'note')}
                                      for item in JUDGMENTS]},
        'parameter_refs': [
            {'name': 'curb_and_stand_context', 'kind': 'world_setup',
             'range_or_domain': 'original street geometry and source-reviewed taxi-stand designation'},
            {'name': 'taxi_and_participant', 'kind': 'world_setup',
             'range_or_domain': 'original taxi and loading participant identities'},
            {'name': 'loading_subject_and_occupant_transition', 'kind': 'controller',
             'range_or_domain': ['passenger_loading', 'merchandise_loading']}]}
    ref_template = save('template.json', template)
    refs_judgment = []
    for number, item in enumerate(JUDGMENTS, 1):
        names = item['observables']
        observables = [{'name': name, 'unit': 'source observation',
                        'description': 'Original Native synchronized observation and source review for ' + name}
                       for name in names]
        contexts = [{'name': name, 'unit': 'source review',
                     'description': 'Authority or identity review tied to original Native capture'}
                    for name in ('taxi_license_review', 'stand_designation_review',
                                 'other_regulations_review')]
        proposal = {
            'template_id': TEMPLATE_ID, 'phrase': item['phrase'],
            'note': item['note'], 'status': 'draft',
            'observable_requirements': {
                'observables': observables, 'context_inputs': contexts,
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': observables,
                'limitations': [
                    'Original taxi identity, stand authority, participant activity and legal meaning require local review.']}}
        refs_judgment.append(save('judgment-observables-' + str(number) + '.json', proposal))
    parameters = [{**item, 'used_by_laws': [LAW_ID]}
                  for item in template['parameter_refs']]
    binding = {
        'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [
            'Taxi stand is a cell planning cue, not proof of original stand designation.'],
        'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': parameters}
    ref_binding = save('bindings.json', binding)
    case_path = PROPOSALS / 'cases.json'
    index = {
        'format': 'worker-semantic-delivery', 'assignment_id': BASE.name,
        'stages': {
            'relevance_batch': ref_batch, 'relevance': ref_relevance,
            'template': ref_template, 'judgment_observables': refs_judgment,
            'bindings': ref_binding,
            'cases': {'path': 'proposals/cases.json',
                      'sha256': hashlib.sha256(case_path.read_bytes()).hexdigest()}}}
    save('semantic-index.json', index)


if __name__ == '__main__':
    main()
