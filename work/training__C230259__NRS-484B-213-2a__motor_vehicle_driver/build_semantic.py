"""Build source-faithful draft stages for the exact crest/curve branches."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'NRS-484B-213-2a'
ACTOR = 'motor_vehicle_driver'
CELL = 'C230259'


def save(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
    law = assignment['law']['text']
    selected = json.loads((HERE / 'selected-construction-draft.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': law,
                                    'applies_to': [ACTOR], 'relevance_type': 'specific_match',
                                    'confidence': 'medium',
                                    'notes': 'Original crest or curve, highway directionality, sight obstruction and body occupancy need source review.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': save('relevance_batch.json', relevance),
            'relevance': save('relevance.json', relevance)}
    phrases = [
        ('the driver’s view is obstructed within such distance as to create a hazard in the event another vehicle might approach from the opposite direction',
         'Original sight rays, road geometry and possible opposite-direction approach require physical and legal review.',
         'st.sight_distance'),
        ('one-way highway',
         'The subsection 3 exception requires original highway designation, not an authored map label.',
         'st.one_way_roadway')]
    template_id = LAW + '@' + ACTOR
    judgments = [{'phrase': phrase, 'note': note} for phrase, note, _ in phrases]
    template = {'template_id': template_id, 'law_id': LAW, 'actor': ACTOR,
                'status': 'draft', 'quote': law,
                'structure': {
                    'activation': {'description': 'Approaching a crest of grade or upon a curve with the stated obstructed view and possible opposite-direction approach.',
                                   'source_clause': 'When approaching the crest of a grade or upon a curve in the highway where the driver’s view is obstructed within such distance as to create a hazard'},
                    'obligation': {'description': 'A vehicle must not be driven to the left side of the highway while the applicable condition holds.',
                                   'source_clause': 'A vehicle must not be driven to the left side of the highway at any time'},
                    'exceptions': [{'condition': 'one-way highway',
                                    'effect': 'Subsection 2 does not apply',
                                    'source_clause': 'Subsection 2 does not apply upon a one-way highway.'}],
                    'timing': {'description': 'Observe the full approach to the crest or traversal of the curve at every original frame.',
                               'source_clause': 'at any time'},
                    'judgment_calls_needed': judgments},
                'parameter_refs': []}
    refs['template'] = save('template.json', template)
    observed = []
    for index, (phrase, note, channel) in enumerate(phrases):
        named = {'name': channel, 'unit': 'structured',
                 'description': 'Original Native frame-joined map, body, participant and sight source for independent review.'}
        value = {'template_id': template_id, 'phrase': phrase, 'note': note,
                 'status': 'draft', 'observable_requirements': {
                     'observables': [named], 'context_inputs': [], 'sweep_dimensions': [],
                     'landmarks': [], 'recording_needs': [named],
                     'limitations': ['The CPU fixture cannot establish legal hazard distance or one-way highway authority.']}}
        observed.append(save('judgment_observables_' + str(index) + '.json', value))
    refs['judgment_observables'] = observed
    variable_parameters = [
        {'name': 'feature_kind', 'kind': 'world_setup',
         'range_or_domain': 'crest or flat curve', 'used_by_laws': [LAW]},
        {'name': 'road_directionality', 'kind': 'world_setup',
         'range_or_domain': 'two_way or one_way authored context; legal authority unverified',
         'used_by_laws': [LAW]},
        {'name': 'left_of_center_request', 'kind': 'controller',
         'range_or_domain': 'right-side travel or requested left-of-centre travel',
         'used_by_laws': [LAW]}]
    refs['bindings'] = save('bindings.json', {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [],
        'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': variable_parameters})
    proposals = []
    for entry in selected['cases']:
        ident = entry['case_id']
        suffix = ident.rsplit('__', 1)[-1]
        construction = json.loads((HERE / entry['construction']).read_text())
        left = suffix in ('probe_b', 'curve_left', 'one_way_crest', 'one_way_curve')
        one_way = suffix.startswith('one_way')
        curve = 'curve' in suffix
        comparisons = [item['comparison_id'] for item in plan['comparisons']
                       if ident in item['case_ids']]
        paired = (next((item for item in comparisons if 'one_way_exception' in item), None)
                  if one_way else comparisons[0])
        proposal = {'case_id': ident, 'target_law_id': LAW,
                    'target_type': 'judgment_sweep',
                    'rationale': 'Source-bound physical crest/curve and highway-directionality comparison; legal outcome unresolved.',
                    'paired_probe_id': paired,
                    'deliberate_differences': ['road_directionality' if one_way else 'left_of_center_request'],
                    'probe': {'primary_variable': 'road_directionality' if one_way else 'left_of_center_request',
                              'comparison_or_standard': 'Controlled physical comparison with legal judgment deferred',
                              'target_value_or_branch': suffix},
                    'variable_assignments': {
                        'feature_kind': {'kind': 'world_setup', 'value': 'curve' if curve else 'crest'},
                        'road_directionality': {'kind': 'world_setup', 'value': 'one_way' if one_way else 'two_way'},
                        'left_of_center_request': {'kind': 'controller', 'value': left}},
                    'recording_description': construction['recording_description'],
                    'unresolved_judgment_calls': [phrase for phrase, _, _ in phrases]}
        proposals.append(proposal)
    baseline = dict(proposals[0])
    baseline.update(case_id=AID + '__baseline', target_law_id=None,
                    target_type='baseline', paired_probe_id=None,
                    deliberate_differences=[],
                    rationale='Unselected neutral context; no additional recording.')
    baseline['variable_assignments'] = {
        name: {'kind': item['kind'], 'value': None}
        for name, item in proposals[0]['variable_assignments'].items()}
    refs['cases'] = save('cases.json', {'cell_id': CELL, 'actor': ACTOR,
                                     'status': 'draft', 'cases': [baseline] + proposals,
                                     'sweeps_expanded': True,
                                     'sweep_specs': [{
                                         'sweep_id': 'c230259-213-2a-source-review',
                                         'target_law_id': LAW,
                                         'judgment_refs': judgments,
                                         'rationale': 'Hazard distance and one-way highway authority need original source review; no numeric legal cutoff is authored.',
                                         'status': 'incomplete',
                                         'missing_inputs': ['Original line-of-sight and opposite-approach source',
                                                            'Independent one-way highway designation source']}]})
    save('semantic-index.json', {'format': 'worker-semantic-delivery',
                                 'assignment_id': AID, 'stages': refs})
    print(json.dumps({'selected_cases': len(proposals), 'judgment_phrases': len(phrases)}))


if __name__ == '__main__':
    main()
