"""Build source-grounded canonical semantic stages for the three rider cases."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROPOSALS = HERE / 'proposals'
ASSIGNMENT = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
TEXT = ASSIGNMENT['law']['text']
TEMPLATE = LAW + '@' + ACTOR


def put(name, data):
    path = PROPOSALS / name
    path.write_text(json.dumps(data, indent=2) + '\n')
    return {'path': 'proposals/' + name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': 'C104538', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': TEXT,
                                    'applies_to': [ACTOR], 'relevance_type': 'direct',
                                    'confidence': 'high',
                                    'notes': 'Frozen U-turn cell engages the no-U-turn branch; source-backed sign authorization and rider conduct remain to be reviewed.'}],
                 'borderline_excluded': []}
    r0 = put('relevance-batch.json', relevance)
    r1 = put('relevance.json', relevance)
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
                'quote': TEXT, 'status': 'draft',
                'structure': {
                    'law_id': LAW,
                    'activation': {'condition': 'An authorized no-right, no-left, or no-U-turn sign governs the person operating a bicycle, electric bicycle, or electric scooter.',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must',
                                   'description': 'The operator obeys the applicable turn prohibition while operating the machine.',
                                   'numeric_conditions': []},
                    'exceptions': [{
                        'trigger': 'The person dismounts from the machine to make that turn.',
                        'effect': 'The turn prohibition duty for a mounted operator gives way to pedestrian regulations.',
                        'replacement_obligation': 'The person obeys the regulations applicable to pedestrians.',
                        'source_clause': 'except where such person dismounts from the bicycle, electric bicycle, or electric scooter to make any such turn, in which event such person shall then obey the regulations applicable to pedestrians.'}],
                    'timing': {'description': 'Observe sign applicability before the turn, dismount before turning, and pedestrian conduct during the dismounted turn.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': []},
                'parameter_refs': [
                    {'name': 'requested_turn_path', 'kind': 'controller', 'range_or_domain': ['through', 'u_turn']},
                    {'name': 'requested_dismount', 'kind': 'controller', 'range_or_domain': [False, True]}]}
    r2 = put('template.json', template)
    binding = {'cell_id': 'C104538', 'actor': ACTOR, 'status': 'draft',
               'established_contexts': ['Frozen hill-crest U-turn cell contains an authored no-U-turn cue; legal authorization and applicability await original review.'],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [
                   {'name': 'requested_turn_path', 'kind': 'controller',
                    'range_or_domain': ['through', 'u_turn'], 'used_by_laws': [LAW]},
                   {'name': 'requested_dismount', 'kind': 'controller',
                    'range_or_domain': [False, True], 'used_by_laws': [LAW]}]}
    r3 = put('bindings.json', binding)
    cases = json.loads((PROPOSALS / 'cases.json').read_text())
    entries = json.loads((HERE / 'draft-thirty-second-execution-manifest.json').read_text())['cases']
    selected = {e['case_id']: e for e in entries}
    cases['cases'] = [c for c in cases['cases'] if c['target_type'] != 'baseline']
    for c in cases['cases']:
        cid = c['case_id']
        entry = selected[cid]
        construction = json.loads((HERE / entry['construction']).read_text())
        c['recording_description'] = construction['recording_description']
        suffix = cid.rsplit('__', 1)[-1]
        path, dismount = (('through', False) if suffix == 'controlled_1' else
                          ('u_turn', suffix == 'controlled_3'))
        c['target_type'] = ('compliant_attempt' if suffix == 'controlled_1' else
                            'violating_attempt' if suffix == 'controlled_2' else 'boundary_probe')
        c['paired_probe_id'] = 'signed_rider_turn_and_dismount'
        c['deliberate_differences'] = ['requested_turn_path', 'requested_dismount']
        c['probe'] = {'primary_variable': 'requested_dismount' if dismount else 'requested_turn_path',
                      'comparison_or_standard': 'source-bound controlled turn/dismount request under one authored sign; original applicability and legal outcome unverified',
                      'target_value_or_branch': 'dismounted_turn' if dismount else path}
        c['variable_assignments'] = {
            'requested_turn_path': {'kind': 'controller', 'value': path},
            'requested_dismount': {'kind': 'controller', 'value': dismount}}
        c['rationale'] = ('Check dismount-before-turn timing and walking-machine evidence with pedestrian-rule review pending.'
                          if dismount else 'Compare mounted obey and mounted U-turn source behavior under the same authored sign.')
        c['unresolved_judgment_calls'] = []
    baseline = copy.deepcopy(cases['cases'][0])
    baseline['case_id'] = HERE.name + '__neutral_baseline'
    baseline['target_law_id'] = None
    baseline['target_type'] = 'baseline'
    baseline['rationale'] = 'Unselected shared context reference; no recording or legal result.'
    baseline['variable_assignments'] = {
        'requested_turn_path': {'kind': 'controller', 'value': 'through'},
        'requested_dismount': {'kind': 'controller', 'value': False}}
    baseline.pop('paired_probe_id', None)
    baseline.pop('probe', None)
    cases['cases'].insert(0, baseline)
    cases['sweep_specs'] = []
    cases['status'] = 'draft'
    r4 = put('cases.json', cases)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
             'stages': {'relevance_batch': r0, 'relevance': r1, 'template': r2,
                        'judgment_observables': [], 'bindings': r3, 'cases': r4}}
    r5 = put('semantic-index.json', index)
    print(json.dumps({'index_sha256': r5['sha256'], 'selected_cases': 3}))


if __name__ == '__main__':
    main()
