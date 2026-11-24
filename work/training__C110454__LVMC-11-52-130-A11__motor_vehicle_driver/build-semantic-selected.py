"""Build the exact-law, source-qualified eleven-case canonical proposal chain."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROPOSALS = HERE / 'proposals'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    law_id, cell_id, actor = (assignment[k] for k in ('law_id', 'cell_id', 'actor'))
    law = assignment['law']['text']
    template_id = law_id + '@' + actor
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': law, 'applies_to': [actor],
                                    'relevance_type': 'direct', 'confidence': 'high',
                                    'notes': 'The fixed intersection parking maneuver reaches the exact fifteen-foot clause; original exceptions remain unresolved.'}],
                 'borderline_excluded': []}
    write(PROPOSALS / 'relevance-batch.json', relevance)
    write(PROPOSALS / 'relevance.json', relevance)
    judgments = [
        {'phrase': 'when necessary to avoid conflict with other traffic',
         'note': 'Original traffic trajectories and causal necessity need source review.'},
        {'phrase': 'in compliance with law',
         'note': 'Applicable law and reason for the stop need independent source review.'},
        {'phrase': 'the directions of a police officer or a traffic control device',
         'note': 'Original authority, display, communication and applicability need independent source review.'}]
    parameters = [
        {'name': 'commanded_parking_clearance_target_m', 'kind': 'controller',
         'range_or_domain': 'authored nearest parked-body clearance target in metres'},
        {'name': 'observed_parked_body_distance_m', 'kind': 'subject_behavior',
         'range_or_domain': 'measured full-body nearest distance from surveyed intersection boundary in metres'},
        {'name': 'observed_parked_duration_s', 'kind': 'subject_behavior',
         'range_or_domain': 'measured continuous rest interval in seconds'},
        {'name': 'original_exception_context', 'kind': 'world_setup',
         'range_or_domain': 'source-qualified conflict, applicable law, officer and device context'}]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'quote': law, 'status': 'draft',
                'structure': {'law_id': law_id,
                              'activation': {'condition': 'The subject stops, stands or parks near an intersection.',
                                             'numeric_conditions': [{'variable': 'observed_parked_body_distance_m',
                                                                     'operator': '<=', 'value': 4.572, 'unit': 'm'}]},
                              'obligation': {'type': 'must_not',
                                             'description': 'Avoid stopping, standing or parking in the specified place unless an exception applies.',
                                             'numeric_conditions': []},
                              'exceptions': [
                                  {'source_clause': 'when necessary to avoid conflict with other traffic',
                                   'description': 'Causal necessity of stopping to avoid other traffic remains unresolved.'},
                                  {'source_clause': 'in compliance with law',
                                   'description': 'Applicable law and compliance remain unresolved.'},
                                  {'source_clause': 'the directions of a police officer or a traffic control device',
                                   'description': 'Applicable officer or device direction remains unresolved.'}],
                              'timing': {'description': 'Evaluate original full-body footprint throughout the measured rest interval.',
                                         'numeric_conditions': []},
                              'judgment_calls_needed': judgments},
                'parameter_refs': parameters}
    write(PROPOSALS / 'template.json', template)
    judgment_refs = []
    for index, judgment in enumerate(judgments):
        requirements = {'observables': [
            {'name': 'native_body_pose_control', 'unit': 'structured',
             'description': 'Original time-joined body, pose and controller source'},
            {'name': 'camera_frame_join', 'unit': 'structured',
             'description': 'Original synchronized frame references for human review'}],
            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [
                {'name': 'native_body_pose_control', 'unit': 'structured',
                 'description': 'Retain original motion and parked body source'},
                {'name': 'camera_frame_join', 'unit': 'structured',
                 'description': 'Retain original synchronized pixels and frame times'}],
            'limitations': ['Synthetic packets do not establish a legal exception; case-specific context sources and original Native pixels need review.']}
        path = PROPOSALS / f'judgment-{index}.json'
        write(path, {'template_id': template_id, **judgment, 'status': 'draft',
                     'observable_requirements': requirements})
        judgment_refs.append({'path': str(path.relative_to(HERE)), 'sha256': sha(path)})
    bindings = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                'established_contexts': ['Authored two-way intersection parking cell; original map, body, exception context and pixels remain unverified.'],
                'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [],
                'variable_parameters': [{**item, 'used_by_laws': [law_id]} for item in parameters]}
    write(PROPOSALS / 'bindings.json', bindings)
    planned = {item['case_id']: item for item in plan['cases']}
    cases = []
    baseline_description = json.loads((HERE / manifest['cases'][0]['construction']).read_text())['recording_description']
    cases.append({'case_id': HERE.name + '__baseline', 'target_law_id': None,
                  'target_type': 'baseline', 'rationale': 'Neutral reference for the fixed cell; no selected recording.',
                  'variable_assignments': {
                      'commanded_parking_clearance_target_m': {'kind': 'controller', 'value': 15.4, 'unit': 'm'},
                      'observed_parked_body_distance_m': {'kind': 'subject_behavior', 'value': None, 'unit': 'm'},
                      'observed_parked_duration_s': {'kind': 'subject_behavior', 'value': None, 'unit': 's'},
                      'original_exception_context': {'kind': 'world_setup', 'value': 'source_unverified', 'unit': 'structured'}},
                  'unresolved_judgment_calls': [], 'recording_description': baseline_description})
    clearances = {'witness_1': 15.4, 'witness_2': 3.9,
                  'numeric_1_0': 3.9, 'numeric_1_1': 4.572, 'numeric_1_2': 5.4}
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        source_case = planned[case_id]
        clearance = clearances.get(suffix, 3.9)
        exception = 'source_unverified'
        if suffix.startswith('exception_'):
            number, polarity = suffix.split('_')[1:]
            exception = 'exception_' + number + ('_absent' if polarity == '1' else '_present')
        assignments = {
            'commanded_parking_clearance_target_m': {'kind': 'controller', 'value': clearance, 'unit': 'm'},
            'observed_parked_body_distance_m': {'kind': 'subject_behavior', 'value': None, 'unit': 'm'},
            'observed_parked_duration_s': {'kind': 'subject_behavior', 'value': None, 'unit': 's'},
            'original_exception_context': {'kind': 'world_setup', 'value': exception, 'unit': 'structured'}}
        if suffix.startswith('numeric_'):
            group, different = 'fifteen_foot_numeric_boundary', ['commanded_parking_clearance_target_m']
            primary = 'observed_parked_body_distance_m'
        elif suffix.startswith('exception_'):
            group, different = 'exception_' + suffix.split('_')[1] + '_source_context', ['original_exception_context']
            primary = 'original_exception_context'
        else:
            group, different = 'intersection_parking_footprint', ['commanded_parking_clearance_target_m']
            primary = 'observed_parked_body_distance_m'
        probe = {'primary_variable': primary,
                 'comparison_or_standard': source_case['comparison_variable'],
                 'target_value_or_branch': source_case['physical_target']}
        if suffix.startswith('numeric_'):
            probe.update({'threshold_ref': 'activation.numeric_conditions[0]',
                          'operator': '<=', 'unit': 'm', 'test_value': clearance})
        construction = json.loads((HERE / entry['construction']).read_text())
        row = {'case_id': case_id, 'target_law_id': law_id,
               'target_type': 'boundary_probe', 'rationale': source_case['physical_target'],
               'variable_assignments': assignments,
               'unresolved_judgment_calls': [item['phrase'] for item in judgments],
               'recording_description': construction['recording_description'],
               'paired_probe_id': group, 'deliberate_differences': different,
               'probe': probe}
        if suffix.startswith('numeric_'):
            row['epsilon_used'] = {'value': 0.5, 'unit': 'm',
                                   'basis': 'Planning spacing, not measured uncertainty or legal tolerance'}
        cases.append(row)
    proposal = {'cell_id': cell_id, 'actor': actor, 'status': 'draft', 'cases': cases,
                'sweep_specs': [{'sweep_id': 'parking_exception_judgments_pending',
                                 'target_law_id': law_id, 'status': 'incomplete',
                                 'judgment_refs': judgments,
                                 'missing_inputs': ['Original conflict trajectories and necessity',
                                                    'Applicable independent law and stop purpose',
                                                    'Original officer or official device direction and applicability'],
                                 'rationale': 'The selected categorical exception cases retain source packets; continuous judgment sweeps require independent Native context.'}],
                'sweeps_expanded': True}
    write(PROPOSALS / 'canonical-cases.json', proposal)
    write(PROPOSALS / 'cases.json', proposal)
    stage_files = {'relevance_batch': 'relevance-batch.json', 'relevance': 'relevance.json',
                   'template': 'template.json', 'judgment_observables': judgment_refs,
                   'bindings': 'bindings.json', 'cases': 'canonical-cases.json'}
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
             'status': 'draft_source_qualified_judgment_pending',
             'stages': {key: value if isinstance(value, list) else
                        {'path': 'proposals/' + value, 'sha256': sha(PROPOSALS / value)}
                        for key, value in stage_files.items()}}
    write(PROPOSALS / 'semantic-index.json', index)
    print(json.dumps({'selected_cases': len(cases) - 1,
                      'semantic_index_sha256': sha(PROPOSALS / 'semantic-index.json')}))


if __name__ == '__main__':
    main()
