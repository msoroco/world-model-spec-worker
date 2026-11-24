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
                     'notes': 'The selected branch routes a qualifying moving emergency vehicle approaching the driver to subsection 1.'}],
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
         'range_or_domain': ['move_to_right_edge_and_stop_until_passed', 'continue_at_3_mps']},
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
    for index, judgment in enumerate(judgments):
        observed.append(put('judgment_observables_' + str(index) + '.json', {
            'template_id': TEMPLATE_ID, 'phrase': judgment['phrase'],
            'note': judgment['note'], 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': 'original_actor_motion_and_light', 'unit': 'structured',
                                 'description': 'Frame joined ego and emergency body, speed, lamp state and camera frames.'}],
                'context_inputs': [{'name': 'independent_qualification_review', 'unit': 'structured',
                                    'description': 'Authority, equipment, visible indication and officer direction source review.'}],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': 'four_camera_frame_join', 'unit': 'structured',
                                     'description': 'Retain original four camera and actor frame joins.'}],
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
