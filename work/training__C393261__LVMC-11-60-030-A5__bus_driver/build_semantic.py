"""Canonical draft proposals for source-gated bus terminus dwell."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID, ACTOR = LAW['id'], ASSIGNMENT['actor']
TEMPLATE = LAW_ID + '@' + ACTOR


def put(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': path.relative_to(HERE).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': 'C393261', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW_ID, 'quote': LAW['text'],
            'applies_to': [ACTOR], 'relevance_type': 'direct',
            'confidence': 'high',
            'notes': 'The frozen terminus is plausible; official endpoint designation and period remain source-gated.'}],
        'borderline_excluded': []}
    r1 = put('relevance_batch.json', relevance)
    r2 = put('relevance.json', relevance)
    judgment = {'phrase': 'designated for such bus stop or origin or destination point in accordance with Section 11.60.010',
                'note': 'Require original applicable authority, exact endpoint and effective designated period; a marker without a time is insufficient.'}
    params = [
        {'name': 'target_stationary_dwell_s', 'kind': 'controller',
         'range_or_domain': [8.0, 18.0]},
        {'name': 'terminus_road_and_zone', 'kind': 'world_setup',
         'range_or_domain': ['same residential road 1 parking lane -2']},
        {'name': 'designation_source_status', 'kind': 'world_setup',
         'range_or_domain': ['unverified', 'original_authority_reviewed']},
    ]
    template = {'template_id': TEMPLATE, 'law_id': LAW_ID, 'actor': ACTOR,
        'quote': LAW['text'], 'status': 'draft',
        'structure': {'law_id': LAW_ID,
            'activation': {'condition': 'Operator of a bus other than a tour bus at a bus stop or origin or destination point.',
                           'numeric_conditions': []},
            'obligation': {'type': 'must_not',
                           'description': 'Do not stand or park longer than the period designated for that place under Section 11.60.010.',
                           'numeric_conditions': []},
            'exceptions': [{'source_clause': 'other than a tour bus',
                            'condition': 'tour bus',
                            'effect': 'Excluded from this paragraph; original bus classification requires review.'}],
            'timing': {'description': 'Measure the complete original bus standing or parking interval and compare only after applicable designated period is sourced.',
                       'numeric_conditions': []},
            'judgment_calls_needed': [judgment]},
        'parameter_refs': params}
    r3 = put('template.json', template)
    r4 = put('judgment-observables-1.json', {
        'template_id': TEMPLATE, 'phrase': judgment['phrase'],
        'note': judgment['note'], 'status': 'draft',
        'observable_requirements': {
            'observables': [{'name': 'kin.time', 'unit': 'structured',
                'description': 'Original post-tick complete bus dwell frame span.'}],
            'context_inputs': [{'name': 'designation_authority_source', 'unit': 'structured',
                'description': 'Original official designation, endpoint match, applicability and period source hash.'}],
            'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': 'ru.bus', 'unit': 'structured',
                'description': 'Original bus identity, non-tour classification and activity review.'}],
            'limitations': [judgment['note'],
                'No designated numeric period is supplied by the clause or frozen cell.']}})
    binding = {'cell_id': 'C393261', 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(param, used_by_laws=[LAW_ID]) for param in params]}
    r5 = put('bindings.json', binding)
    recording = json.loads((HERE / 'construction.json').read_text())['recording_description']
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline',
        'rationale': 'Unselected neutral residential terminus context.',
        'variable_assignments': {param['name']: {'kind': param['kind'],
            'value': None, 'unit': 'categorical'} for param in params},
        'unresolved_judgment_calls': [], 'recording_description': recording}]
    for rank, (suffix, dwell) in enumerate((('probe_01', 8.0), ('probe_02', 18.0)), 1):
        cases.append({'case_id': HERE.name + '__' + suffix,
            'target_law_id': LAW_ID, 'target_type': 'judgment_sweep',
            'rationale': 'Compare measured complete bus dwell with all road, actor, marker and cameras fixed; official period remains unknown until sourced.',
            'variable_assignments': {
                'target_stationary_dwell_s': {'kind': 'controller', 'value': dwell,
                                               'unit': 'seconds'},
                'terminus_road_and_zone': {'kind': 'world_setup',
                    'value': 'same residential road 1 parking lane -2',
                    'unit': 'categorical'},
                'designation_source_status': {'kind': 'world_setup', 'value': None,
                                               'unit': 'categorical'}},
            'unresolved_judgment_calls': [judgment['phrase']],
            'paired_probe_id': HERE.name + '__dwell_comparison',
            'deliberate_differences': ['target_stationary_dwell_s'],
            'probe': {'primary_variable': 'target_stationary_dwell_s',
                      'comparison_or_standard': 'Original authority-designated period, if established',
                      'target_value_or_branch': dwell},
            'recording_description': recording, 'selection_rank': rank})
    sweep = {'sweep_id': HERE.name + '__dwell_comparison',
        'target_law_id': LAW_ID, 'status': 'incomplete',
        'judgment_refs': [judgment],
        'rationale': 'Actual complete bus dwell and official applicable period require separate original sources.',
        'missing_inputs': ['Original Native motion and official Section 11.60.010 designation.']}
    r6 = put('cases.json', {'cell_id': 'C393261', 'actor': ACTOR,
        'status': 'draft', 'sweep_specs': [sweep], 'sweeps_expanded': True,
        'cases': cases})
    put('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': HERE.name,
        'stages': {'relevance_batch': r1, 'relevance': r2, 'template': r3,
                   'judgment_observables': [r4], 'bindings': r5, 'cases': r6}})
    print('Two exact bus dwell semantic proposals written')


if __name__ == '__main__':
    main()
