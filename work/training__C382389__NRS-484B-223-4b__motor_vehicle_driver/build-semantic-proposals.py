"""Build source-grounded, unselected NRS 484B.223(4)(b) stage drafts."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
ASSIGNMENT = json.loads((ROOT/'inputs'/FOLDER.name/'assignment.json').read_text())
LAW = ASSIGNMENT['law_record']
AID = FOLDER.name
TEMPLATE_ID = LAW['id']+'@'+ASSIGNMENT['actor']


def write(name, value):
    path = FOLDER/'proposals'/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')
    return {'path': str(path.relative_to(FOLDER)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'],
        'status': 'draft', 'relevant_laws': [{'law_id': LAW['id'], 'quote': LAW['text'],
        'applies_to': [ASSIGNMENT['actor']], 'relevance_type': 'direct',
        'confidence': 'high', 'notes': 'Exact right-only-lane through-intersection clause; Native lane designation and crossing require evidence.'}],
        'borderline_excluded': []}
    r1 = write('relevance-batch.json', relevance)
    r2 = write('relevance.json', relevance)
    parameters = [
        {'name': 'commanded_approach_lane_id', 'kind': 'controller', 'range_or_domain': [-1,-2]},
        {'name': 'observed_right_only_lane_crossing', 'kind': 'subject_behavior',
         'range_or_domain': 'measured full-body road/lane crossing from original Native frames, initially unknown'}]
    template = {'template_id': TEMPLATE_ID, 'law_id': LAW['id'], 'actor': ASSIGNMENT['actor'],
        'quote': LAW['text'], 'status': 'draft',
        'structure': {'law_id': LAW['id'],
            'activation': {'condition': 'single right lane designed only for turning; vehicle driven in it', 'numeric_conditions': []},
            'obligation': {'description': 'while driven in that right turn lane, do not travel through an intersection',
                           'type': 'must', 'numeric_conditions': []},
            'exceptions': [], 'timing': {'description': 'right-only lane identity during body crossing of intersection',
                                         'numeric_conditions': []},
            'judgment_calls_needed': []}, 'parameter_refs': parameters}
    r3 = write('template.json', template)
    bindings = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'], 'status': 'draft',
        'established_contexts': ['authored right-only lane with adjacent straight lane; verify actual Native designation and connector IDs'],
        'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}], 'context_refs': [],
        'fixed_parameters': [{'name': 'right_only_lane_intersection_authored', 'value': True,
          'rationale': 'Authored map proposal; original Native map and saved pixels still required'}],
        'variable_parameters': [dict(item, used_by_laws=[LAW['id']]) for item in parameters]}
    r4 = write('bindings.json', bindings)
    def values(lane):
        return {'commanded_approach_lane_id': {'kind': 'controller', 'value': lane, 'unit': 'lane_id'},
                'observed_right_only_lane_crossing': {'kind': 'subject_behavior', 'value': None, 'unit': 'boolean'}}
    baseline_recording = json.loads((FOLDER/'draft-candidates/reference/primary/construction.json').read_text())['recording_description']
    cases = [{'case_id': AID+'__baseline', 'target_law_id': None, 'target_type': 'baseline',
              'rationale': 'Adjacent straight lane is the shared neutral context; activation is absent. Unselected.',
              'variable_assignments': values(-1), 'unresolved_judgment_calls': [],
              'recording_description': baseline_recording}]
    for suffix,lane in (('reference',-1),('contrast',-2)):
        construction = json.loads((FOLDER/'draft-candidates'/suffix/'primary/construction.json').read_text())
        cases.append({'case_id': AID+'__'+suffix, 'target_law_id': LAW['id'],
          'target_type': 'compliant_attempt' if suffix == 'reference' else 'violating_attempt',
          'rationale': 'Compare straight travel from adjacent lane against straight travel from authored right-only lane; outcome awaits Native designation and independent review.',
          'variable_assignments': values(lane), 'unresolved_judgment_calls': [],
          'paired_probe_id': AID+'__approach_lane_pair',
          'deliberate_differences': ['commanded_approach_lane_id'],
          'probe': {'primary_variable': 'commanded_approach_lane_id',
                    'comparison_or_standard': 'adjacent through lane versus right-only lane, same straight movement',
                    'target_value_or_branch': lane},
          'recording_description': construction['recording_description']})
    r5 = write('cases.json', {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'],
        'status': 'draft', 'cases': cases, 'sweep_specs': []})
    index = {'format': 'worker-semantic-delivery-v1', 'assignment_id': AID,
             'status': 'draft_not_delivery_selected',
             'stages': {'relevance_batch': r1, 'relevance': r2, 'template': r3,
                        'judgment_observables': [], 'bindings': r4, 'cases': r5}}
    write('semantic-index.json', index)
    print(json.dumps({'semantic_stages': 5, 'unselected_case_drafts': 2, 'judgment_phrases': 0}))


if __name__ == '__main__': main()
