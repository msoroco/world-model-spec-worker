"""Bind exact alley clause to draft semantic stages and selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
A = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = A['law']
TID = LAW['id'] + '@' + A['actor']


def put(name, value):
    p = HERE / 'proposals' / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(p.relative_to(HERE)),
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': A['cell_id'], 'actor': A['actor'], 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW['id'], 'quote': LAW['text'],
                                    'applies_to': [A['actor']], 'relevance_type': 'direct',
                                    'confidence': 'medium',
                                    'notes': 'The selected park branch is within the clause; qualifying alley and local ordinance require source review.'}],
                 'borderline_excluded': []}
    r_batch = put('relevance_batch.json', relevance)
    r_rel = put('relevance.json', relevance)
    judgments = [
        {'phrase': 'Unless otherwise provided by ordinance of the local authority having jurisdiction',
         'note': 'Identify the actual jurisdiction and ordinance legal effect from independent source records.'},
        {'phrase': 'any other alley',
         'note': 'Verify statutory alley identity, public highway, city block, rear access, abutting property and antecedent scope.'},
        {'phrase': 'Stop, stand or park a vehicle',
         'note': 'The frozen cell selects park; original rest duration, purpose, occupant activity and alternative stop/stand status remain source reviewed.'},
        {'phrase': 'for the free movement of vehicular traffic',
         'note': 'Retain continuous body and other-vehicle footprint evidence; do not infer legal free movement from width alone.'}]
    template = {'template_id': TID, 'law_id': LAW['id'], 'actor': A['actor'],
                'status': 'draft', 'quote': LAW['text'],
                'structure': {'law_id': LAW['id'],
                              'activation': {'description': 'Vehicle stops, stands or parks in a qualifying other alley, subject to local ordinance.',
                                             'numeric_conditions': []},
                              'obligation': {'description': 'Do not leave less than 10 feet available for free vehicular movement.',
                                             'type': 'must_not',
                                             'numeric_conditions': [{'variable': 'measured_free_width_m', 'operator': '<',
                                                                     'value': 3.048, 'unit': 'meters'}]},
                              'exceptions': [{'source_clause': judgments[0]['phrase'],
                                              'description': 'A controlling local ordinance may provide otherwise; effect is not presumed.'}],
                              'timing': {'description': 'Measure available width throughout the observed rest interval, with original 20 Hz joins.',
                                         'numeric_conditions': []},
                              'judgment_calls_needed': judgments},
                'parameter_refs': []}
    r_template = put('template.json', template)
    observed = []
    for i, judgment in enumerate(judgments):
        name = ('st.alley', 'st.alley', 'drv.standing_or_parked', 'rel.surface_gap')[i]
        context = {'name': 'independent_alley_review', 'unit': 'structured',
                   'description': 'Source-bound jurisdiction, ordinance, alley identity and purpose review.'}
        observed.append(put(f'judgment_observables_{i}.json',
                            {'template_id': TID, 'phrase': judgment['phrase'],
                             'note': judgment['note'], 'status': 'draft',
                             'observable_requirements': {
                                 'observables': [{'name': name, 'unit': 'structured',
                                                  'description': 'Original frame-joined alley and vehicle evidence.'}],
                                 'context_inputs': [context], 'sweep_dimensions': [],
                                 'landmarks': [],
                                 'recording_needs': [{'name': name, 'unit': 'structured',
                                                      'description': 'Retain original frame-joined source channel.'}],
                                 'limitations': [judgment['note'],
                                                 'Synthetic diagnostics do not establish Native physical or legal acceptance.']}}))
    binding = {'cell_id': A['cell_id'], 'actor': A['actor'], 'status': 'draft',
               'established_contexts': [],
               'law_refs': [{'template_id': TID, 'binding_kind': 'direct'}],
               'context_refs': [],
               'fixed_parameters': [],
               'variable_parameters': [
                   {'name': 'alley_width_m', 'kind': 'world_setup',
                    'range_or_domain': '6.0, 6.648, 7.5 m authored width; original readback required',
                    'used_by_laws': [LAW['id']]},
                   {'name': 'parking_request', 'kind': 'controller',
                    'range_or_domain': 'park beside a distinct other vehicle; no park in unselected baseline',
                    'used_by_laws': [LAW['id']]}]}
    r_binding = put('bindings.json', binding)
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    description = json.loads((HERE / manifest['cases'][0]['construction']).read_text())['recording_description']
    cases = [{'case_id': HERE.name + '__neutral_baseline', 'target_law_id': None,
              'target_type': 'baseline', 'rationale': 'Unselected neutral context; no park requested.',
              'variable_assignments': {'alley_width_m': {'kind': 'world_setup', 'value': 7.5},
                                       'parking_request': {'kind': 'controller', 'value': 'no park'}},
              'unresolved_judgment_calls': [j['phrase'] for j in judgments],
              'recording_description': description}]
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        width, free = {'controlled_1': (7.5, 3.9),
                       'controlled_at_10': (6.648, 3.048),
                       'controlled_2': (6.0, 2.4)}[suffix]
        construction = json.loads((HERE / entry['construction']).read_text())
        cases.append({'case_id': entry['case_id'], 'target_law_id': LAW['id'],
                      'target_type': 'boundary_probe',
                      'rationale': 'Requested width boundary for the selected park branch; actual free width remains measured.',
                      'variable_assignments': {'alley_width_m': {'kind': 'world_setup', 'value': width},
                                               'parking_request': {'kind': 'controller',
                                                                   'value': 'park beside a distinct other vehicle'}},
                      'unresolved_judgment_calls': [j['phrase'] for j in judgments],
                      'paired_probe_id': HERE.name + '__ten_foot_boundary',
                      'deliberate_differences': ['alley_width_m'],
                      'epsilon_used': {'basis': 'engineering width choices only',
                                       'legal_threshold_m': 3.048},
                      'probe': {'primary_variable': 'alley_width_m',
                                'comparison_or_standard': 'source-bound minimum free width versus exact 10 feet',
                                'target_value_or_branch': suffix,
                                'threshold_ref': 'obligation.numeric_conditions[0]',
                                'operator': '<', 'unit': 'meters', 'test_value': free},
                      'recording_description': construction['recording_description']})
    proposal = {'cell_id': A['cell_id'], 'actor': A['actor'], 'status': 'draft',
                'cases': cases, 'sweeps_expanded': True,
                'sweep_specs': [{'sweep_id': 'alley-ordinance-purpose-review',
                                 'target_law_id': LAW['id'], 'status': 'incomplete',
                                 'judgment_refs': judgments,
                                 'rationale': 'Original legal site, ordinance, parking purpose and free movement review remains.',
                                 'missing_inputs': ['Reviewed original Native site and ordinance source packet.']}]}
    r_cases = put('cases.json', proposal)
    put('semantic-index.json', {'format': 'worker-semantic-delivery',
                                'assignment_id': HERE.name,
                                'stages': {'relevance_batch': r_batch, 'relevance': r_rel,
                                           'template': r_template,
                                           'judgment_observables': observed,
                                           'bindings': r_binding, 'cases': r_cases}})
    print('semantic draft cases', len(cases), 'judgments', len(judgments))


if __name__ == '__main__':
    main()
