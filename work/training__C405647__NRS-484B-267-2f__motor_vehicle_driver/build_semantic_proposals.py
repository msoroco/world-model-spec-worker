"""Bind the selected approach comparison to source-grounded semantic drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
TEMPLATE_ID = LAW['id'] + '@' + ASSIGNMENT['actor']


def put(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': path.relative_to(HERE).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'],
                 'status': 'draft', 'relevant_laws': [{
                     'law_id': LAW['id'], 'quote': LAW['text'],
                     'applies_to': [ASSIGNMENT['actor']], 'relevance_type': 'direct',
                     'confidence': 'high',
                     'notes': 'Selected branches route a qualifying approaching emergency or regulatory official vehicle to subsection 1 and preserve a stopped-vehicle referral without inferring NRS 484B.607 duties.'}],
                 'borderline_excluded': []}
    r1 = put('relevance-batch.json', relevance)
    r2 = put('relevance.json', relevance)
    judgments = [
        {'phrase': 'authorized emergency vehicle or an official vehicle of a regulatory agency',
         'note': 'Authorization and role need an original source; blueprint identity alone is insufficient.'},
        {'phrase': 'moving or preparing to move in any direction',
         'note': 'Join original motion and visibly indicated preparation; no speed cutoff defines preparation.'},
        {'phrase': 'making use of flashing lights meeting the requirements of subsection 3 of NRS 484A.480',
         'note': 'Original equipment and pixels require independent review.'},
        {'phrase': 'except when otherwise directed by a law enforcement officer',
         'note': 'Officer identity, direction content, recipient and time require original review.'},
        {'phrase': 'Approaches the driver’s vehicle, proceed as required pursuant to subsection 1',
         'note': 'The three supplied subsection 1 duties require original yield, right-edge position and stop-until-passed review; synthetic response paths are diagnostics.'},
        {'phrase': 'Stops, proceed as required pursuant to NRS 484B.607',
         'note': 'Record the stopped alternative; the exact 484B.607 duties are absent from the frozen corpus.'}]
    parameters = [
        {'name': 'requested_subsection_1_response', 'kind': 'controller',
         'range_or_domain': ['move_to_right_edge_and_stop_until_passed', 'continue_at_3_mps',
                             'right_edge_hold_without_607_verdict']},
        {'name': 'responding_vehicle_kind', 'kind': 'world_setup',
         'range_or_domain': ['authorized_emergency', 'regulatory_agency_official']},
        {'name': 'source_vehicle_stops', 'kind': 'world_setup',
         'range_or_domain': [True, False]},
        {'name': 'qualifying_source_vehicle_and_lamps', 'kind': 'world_setup',
         'range_or_domain': [True, False, None]},
        {'name': 'pre_approach_source_movement', 'kind': 'world_setup',
         'range_or_domain': [True, False]},
        {'name': 'visible_driver_hand_signal', 'kind': 'world_setup',
         'range_or_domain': [True, False, None]},
        {'name': 'observed_emergency_approach', 'kind': 'subject_behavior',
         'range_or_domain': [True, False, None]},
        {'name': 'officer_direction', 'kind': 'world_setup',
         'range_or_domain': [True, False, None]}]
    template = {'template_id': TEMPLATE_ID, 'law_id': LAW['id'],
                'actor': ASSIGNMENT['actor'], 'quote': LAW['text'], 'status': 'draft',
                'structure': {
                    'law_id': LAW['id'],
                    'activation': {'condition': 'A qualifying emergency or regulatory vehicle is moving or visibly preparing to move with qualifying flashing lights.', 'numeric_conditions': []},
                    'obligation': {'description': 'On approach to the driver, follow subsection 1; on stopping, follow NRS 484B.607.', 'type': 'must', 'numeric_conditions': []},
                    'exceptions': [{'source_clause': 'except when otherwise directed by a law enforcement officer',
                                    'description': 'Original officer direction may change the response.'}],
                    'timing': {'description': 'Track vehicle state across approach; do not assign a numeric legal switching threshold.', 'numeric_conditions': []},
                    'judgment_calls_needed': judgments},
                'parameter_refs': parameters}
    r3 = put('template.json', template)
    observed = []
    channel_for_judgment = ('drv.responding_emergency', 'kin.velocity',
                            'drv.responding_emergency', 'dev.human_direction',
                            'drv.approaching', 'drv.stopped')
    for index, judgment in enumerate(judgments):
        observed.append(put('judgment_observables_' + str(index) + '.json', {
            'template_id': TEMPLATE_ID, 'phrase': judgment['phrase'],
            'note': judgment['note'], 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': channel_for_judgment[index], 'unit': 'structured',
                                 'description': 'Frame-joined original actor, motion, light or officer direction source review.'}],
                'context_inputs': [],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': 'rel.visible', 'unit': 'structured',
                                     'description': 'Retain original four camera and actor frame joins for independent visibility review.'}],
                'limitations': [judgment['note'], 'Synthetic fixture cannot establish physical or legal acceptance.']}}))
    bindings = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'],
                'status': 'draft', 'established_contexts': [
                    'Two opposing Native routes authored; realization remains unverified'],
                'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
                'context_refs': [],
                'fixed_parameters': [{'name': 'approach_setup', 'value': 'held_fixed',
                                      'rationale': 'Same road, actor routes, emergency request, lamps and four camera plan in the response pair.'}],
                'variable_parameters': [dict(p, used_by_laws=[LAW['id']]) for p in parameters]}
    r4 = put('bindings.json', bindings)
    cases = {'path': 'proposals/cases.json',
             'sha256': hashlib.sha256((HERE / 'proposals/cases.json').read_bytes()).hexdigest()}
    put('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': HERE.name,
        'stages': {'relevance_batch': r1, 'relevance': r2, 'template': r3,
                   'judgment_observables': observed, 'bindings': r4, 'cases': cases}})
    print(json.dumps({'stages': 6, 'judgments': len(judgments),
                      'selected_cases': len(json.loads((HERE / 'proposals/cases.json').read_text())['cases'])}))


if __name__ == '__main__':
    main()
