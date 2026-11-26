"""Build draft canonical stage proposals from the frozen taxi law and exact cases."""
import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]
ASSIGNMENT = json.loads((ROOT / 'inputs' / PACKAGE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
TEMPLATE_ID = LAW_ID + '@' + ACTOR
PROPOSALS = PACKAGE / 'proposals'


def write(name, data):
    path = PROPOSALS / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def construction(case):
    return json.loads((PACKAGE / 'native-selected' / case / 'construction.json').read_text())


def make():
    PROPOSALS.mkdir(exist_ok=True)
    base = {'cell_id': 'C150173', 'actor': ACTOR, 'status': 'draft'}
    relevance = {**base, 'relevant_laws': [{
        'law_id': LAW_ID, 'quote': LAW['text'], 'applies_to': [ACTOR],
        'relevance_type': 'specific_match', 'confidence': 'high',
        'notes': 'Frozen taxi role and yellow-curb cell; sign authority, vehicle identity and passenger purpose need original review.'}],
        'borderline_excluded': []}
    relevance_ref = write('relevance.json', relevance)
    write('relevance-batch.json', relevance)
    judgments = [
        {'phrase': 'conditions and times posted on an accompanying sign',
         'note': 'The authored 09:00–17:00 sign is a construction proposal. Its wording, authority, governed curb and ordinary rules outside posted hours need independent source review.',
         'observables': ['dev.regulatory_sign', 'env.civil_time', 'drv.condition_in_effect']},
        {'phrase': 'Taxicabs',
         'note': 'A vehicle blueprint and role name do not establish taxicab licensing or status; retain original vehicle identity and independent classification source.',
         'observables': ['ru.taxicab']},
        {'phrase': 'for the purpose of loading, unloading or waiting for passengers',
         'note': 'Requested walker motion is not observed passenger exchange or purpose. Retain original activity and independent purpose review over the standing interval.',
         'observables': ['sig.door_open', 'ru.occupant_count']},
    ]
    template = {
        'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
        'status': 'draft', 'quote': LAW['text'],
        'structure': {
            'activation': {'description': 'A vehicle stops, stands or parks in an established yellow zone with an accompanying sign.',
                           'source_clause': 'Yellow indicates a zone for:'},
            'obligation': {'description': 'Measure taxi standing, observed purpose, sign terms and civil time without a legal verdict.',
                           'type': 'conditional_permission',
                           'source_clause': 'Taxicabs to stop, stand, park for the purpose of loading, unloading or waiting for passengers in accordance with the conditions and times posted on an accompanying sign.',
                           'numeric_conditions': []},
            'exceptions': [
                {'description': 'Commercial vehicles loading or unloading freight require a compatible commercial actor and purpose source.',
                 'source_clause': 'Commercial vehicles to stop, stand or park for the purpose of loading or unloading freight in accordance with the conditions and times posted on an accompanying sign;'},
                {'description': 'Taxi passenger loading, unloading or waiting subject to the source-reviewed posted conditions and times.',
                 'source_clause': 'Taxicabs to stop, stand, park for the purpose of loading, unloading or waiting for passengers in accordance with the conditions and times posted on an accompanying sign.'}
            ],
            'timing': {'description': 'Measure the complete 600-frame standing interval at 20 Hz and join civil time to source-reviewed posted hours.'},
            'judgment_calls_needed': [{k: item[k] for k in ('phrase', 'note')} for item in judgments]
        },
        'parameter_refs': [
            {'name': 'civil_start_local', 'kind': 'world_setup', 'range_or_domain': 'source-joined civil clock time'},
            {'name': 'requested_passenger_purpose', 'kind': 'controller', 'range_or_domain': 'waiting, loading or unloading request'},
            {'name': 'taxi_stop_x_m', 'kind': 'controller', 'range_or_domain': 'stop target along the same authored yellow zone'}
        ]}
    template_ref = write('template.json', template)
    judgment_refs = []
    for index, item in enumerate(judgments, 1):
        recorded = []
        for name in item['observables']:
            recorded.append({'name': name, 'unit': 'source observation',
                             'description': 'Retain original frame-joined ' + name + ' and independent source review.'})
        payload = {'template_id': TEMPLATE_ID, 'phrase': item['phrase'],
                   'note': item['note'], 'status': 'draft',
                   'observable_requirements': {
                       'observables': recorded, 'context_inputs': [],
                       'sweep_dimensions': [], 'landmarks': [],
                       'recording_needs': recorded,
                       'limitations': ['Synthetic requested activity cannot establish original vehicle, sign or passenger facts.']}}
        judgment_refs.append(write(f'judgment-{index}.json', payload))
    bindings = {**base, 'established_contexts': [],
        'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [
            {'name': 'yellow_zone_cell', 'value': 'one_way_road / park / yellow_curb',
             'rationale': 'Frozen C150173 catalog cell; actual sign and curb require original review.'}],
        'variable_parameters': [
            {'name': 'civil_start_local', 'kind': 'world_setup', 'range_or_domain': '10:00 or 18:00 local civil time', 'used_by_laws': [LAW_ID]},
            {'name': 'requested_passenger_purpose', 'kind': 'controller', 'range_or_domain': 'waiting, loading or unloading request', 'used_by_laws': [LAW_ID]},
            {'name': 'taxi_stop_x_m', 'kind': 'controller', 'range_or_domain': 'stop position along yellow curb', 'used_by_laws': [LAW_ID]}
        ]}
    bindings_ref = write('bindings.json', bindings)
    description = construction('probe_a')['recording_description']
    def assigned(clock, purpose, x=5.25):
        return {'civil_start_local': {'kind': 'world_setup', 'value': clock},
                'requested_passenger_purpose': {'kind': 'controller', 'value': purpose},
                'taxi_stop_x_m': {'kind': 'controller', 'value': x}}
    cases = [{
        'case_id': ASSIGNMENT['assignment_id'] + '__baseline',
        'target_law_id': None, 'target_type': 'baseline',
        'rationale': 'Shared taxi yellow-zone context only; no source-based legal finding.',
        'variable_assignments': assigned(None, None, None),
        'unresolved_judgment_calls': [j['phrase'] for j in judgments],
        'recording_description': description}]
    for suffix, clock, purpose, difference in [
            ('probe_a', '2026-11-26T10:00:00', 'waiting_for_passengers', ['civil_start_local', 'requested_passenger_purpose']),
            ('probe_b', '2026-11-26T18:00:00', 'waiting_for_passengers', ['civil_start_local']),
            ('probe_c', '2026-11-26T10:00:00', 'loading_passengers', ['requested_passenger_purpose']),
            ('probe_d', '2026-11-26T10:00:00', 'unloading_passengers', ['requested_passenger_purpose'])]:
        exact = construction(suffix)
        cases.append({
            'case_id': exact['case_id'], 'target_law_id': LAW_ID,
            'target_type': 'judgment_sweep',
            'rationale': 'Measure the taxi passenger request, original activity, curb and posted-hour source joins without an expected legal label.',
            'variable_assignments': assigned(clock, purpose),
            'unresolved_judgment_calls': [j['phrase'] for j in judgments],
            'paired_probe_id': 'taxi-yellow-zone-requested-contrast',
            'deliberate_differences': difference,
            'probe': {'primary_variable': difference[-1],
                      'comparison_or_standard': 'controlled taxi yellow-zone source review',
                      'target_value_or_branch': suffix},
            'recording_description': exact['recording_description']})
    sweep_specs = [{
        'sweep_id': f'taxi-yellow-{index}', 'target_law_id': LAW_ID,
        'judgment_refs': [{k: item[k] for k in ('phrase', 'note')}],
        'status': 'incomplete',
        'rationale': 'The four selected requests are source-shaped contrasts; physical and official classification need original source review before a complete judgment sweep can be frozen.',
        'missing_inputs': [item['note']]}
        for index, item in enumerate(judgments, 1)]
    cases_ref = write('cases.json', {**base, 'sweep_specs': sweep_specs,
                                    'sweeps_expanded': True, 'cases': cases})
    write('semantic-index.json', {
        'format': 'worker-semantic-delivery',
        'assignment_id': ASSIGNMENT['assignment_id'],
        'stages': {'relevance_batch': write('relevance-batch.json', relevance),
                   'relevance': relevance_ref, 'template': template_ref,
                   'judgment_observables': judgment_refs,
                   'bindings': bindings_ref, 'cases': cases_ref}})


if __name__ == '__main__':
    make()
