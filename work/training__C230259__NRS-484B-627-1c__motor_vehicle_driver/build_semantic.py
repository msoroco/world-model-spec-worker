"""Build a source-faithful, nonclaiming canonical semantic proposal chain."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'NRS-484B-627-1c'
CELL = 'C230259'
ACTOR = 'motor_vehicle_driver'


def save(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
    law = assignment['law']['text']
    manifest = json.loads((HERE / 'draft-route-manifest.json').read_text())
    description = json.loads((HERE / manifest['cases'][0]['construction']).read_text())['recording_description']
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': law, 'applies_to': [ACTOR],
                                    'relevance_type': 'specific_match', 'confidence': 'medium',
                                    'notes': 'Route, follower and controlled-access facts require source review.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': save('relevance_batch.json', relevance),
            'relevance': save('relevance.json', relevance)}
    phrases = [
        ('speed so slow as to impede the forward movement of traffic proceeding immediately behind the driver or operator',
         'Original same-frame immediately following traffic needs physical and legal review.', 'participant_motion'),
        ('the highway is a controlled-access highway',
         'A road designation must be established independently of the authored OpenDRIVE geometry.', 'route_occupancy'),
        ('use alternate routes whenever possible',
         'Original map connectivity and actual practical route availability need review.', 'route_occupancy')]
    template_id = LAW + '@' + ACTOR
    judgments = [{'phrase': phrase, 'note': note} for phrase, note, _ in phrases]
    template = {'template_id': template_id, 'law_id': LAW, 'actor': ACTOR,
                'status': 'draft', 'quote': law,
                'structure': {'activation': {'description': 'Slow subject operation with traffic immediately behind on a controlled-access highway.',
                                              'source_clause': phrases[0][0]},
                              'obligation': {'description': 'Use alternate routes whenever possible, if the statutory conditions are established.',
                                             'source_clause': phrases[2][0]},
                              'exceptions': [],
                              'timing': {'description': 'Observe the available route choice over the full approach, exit and destination interval.',
                                         'source_clause': phrases[2][0]},
                              'judgment_calls_needed': judgments},
                'parameter_refs': []}
    refs['template'] = save('template.json', template)
    obs_refs = []
    for index, (phrase, note, channel) in enumerate(phrases):
        named = {'name': channel, 'unit': 'structured',
                 'description': 'Retain original same-frame actor, route and map source for independent review.'}
        proposal = {'template_id': template_id, 'phrase': phrase, 'note': note,
                    'status': 'draft', 'observable_requirements': {
                        'observables': [named], 'context_inputs': [],
                        'sweep_dimensions': [], 'landmarks': [], 'recording_needs': [named],
                        'limitations': ['Authored route geometry and speeds establish no legal designation, impediment or practical availability.']}}
        obs_refs.append(save('judgment_observables_' + str(index) + '.json', proposal))
    refs['judgment_observables'] = obs_refs
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
               'established_contexts': [], 'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [
                   {'name': 'requested_alternate_route', 'kind': 'controller',
                    'range_or_domain': 'take or pass an authored connected exit', 'used_by_laws': [LAW]},
                   {'name': 'alternate_route_possible', 'kind': 'world_setup',
                    'range_or_domain': 'authored connected alternate road present or omitted', 'used_by_laws': [LAW]}]}
    refs['bindings'] = save('bindings.json', binding)
    ids = {entry['case_id'].rsplit('__', 1)[-1]: entry for entry in manifest['cases']}
    def item(suffix, possible, take, paired, variable):
        entry = ids[suffix]
        construction = json.loads((HERE / entry['construction']).read_text())
        return {'case_id': entry['case_id'], 'target_law_id': LAW,
                'target_type': 'judgment_sweep', 'rationale': 'Physical route-choice coverage with legal judgments unresolved.',
                'paired_probe_id': paired, 'deliberate_differences': [variable],
                'probe': {'primary_variable': variable,
                          'comparison_or_standard': 'source-shaped physical route comparison; no legal threshold',
                          'target_value_or_branch': {'possible': possible, 'take': take}},
                'variable_assignments': {
                    'requested_alternate_route': {'kind': 'controller', 'value': take},
                    'alternate_route_possible': {'kind': 'world_setup', 'value': possible}},
                'recording_description': construction['recording_description'],
                'unresolved_judgment_calls': [phrase for phrase, _, _ in phrases]}
    baseline = item('witness_2', True, False, None, 'requested_alternate_route')
    baseline['case_id'] = AID + '__baseline'
    baseline['target_type'] = 'baseline'
    baseline['rationale'] = 'Unselected neutral route context; no simulated baseline.'
    baseline['paired_probe_id'] = None
    baseline['deliberate_differences'] = []
    baseline['variable_assignments'] = {
        'requested_alternate_route': {'kind': 'controller', 'value': None},
        'alternate_route_possible': {'kind': 'world_setup', 'value': None}}
    cases = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
             'cases': [baseline,
                       item('witness_1', True, True, AID + '__witness_comparison', 'requested_alternate_route'),
                       item('witness_2', True, False, AID + '__witness_comparison', 'requested_alternate_route'),
                       item('exception_1_1', True, False, AID + '__exception_1_comparison', 'alternate_route_possible'),
                       item('exception_1_2', False, False, AID + '__exception_1_comparison', 'alternate_route_possible')],
             'sweep_specs': [{'sweep_id': 'c230259-627-1c-legal-source-review',
                              'target_law_id': LAW, 'judgment_refs': judgments,
                              'rationale': 'The three statutory conditions need original traffic, designation and usable-route evidence.',
                              'status': 'incomplete',
                              'missing_inputs': ['Accepted original recording of immediately following traffic',
                                                 'Independent controlled-access designation source',
                                                 'Independent practical alternate-route availability review']}],
             'sweeps_expanded': True}
    refs['cases'] = save('cases.json', cases)
    save('semantic-index.json', {'format': 'worker-semantic-delivery',
                                 'assignment_id': AID, 'stages': refs})
    print(json.dumps({'stages': len(refs), 'cases': len(cases['cases'])}))


if __name__ == '__main__':
    main()
