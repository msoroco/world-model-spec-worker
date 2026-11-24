"""Prepare source-quoted canonical drafts while preserving judgment uncertainty."""
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
    law = assignment['law']
    law_id, cell_id, actor = assignment['law_id'], assignment['cell_id'], assignment['actor']
    template_id = law_id + '@' + actor
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'relevant_laws': [{'law_id': law_id, 'quote': law['text'], 'applies_to': [actor],
            'relevance_type': 'direct', 'confidence': 'high',
            'notes': 'The fixed intersection parking maneuver invokes the exact within-intersection clause; exception circumstances remain source-unverified.'}],
        'borderline_excluded': []}
    write(PROPOSALS / 'relevance-batch.json', relevance)
    write(PROPOSALS / 'relevance.json', relevance)
    judgments = [
        {'phrase': 'necessary to avoid conflict with other traffic',
         'note': 'Original conflict actors, trajectory and causal necessity require review; no numeric necessity threshold is supplied.'},
        {'phrase': 'in compliance with law',
         'note': 'An applicable legal direction and reason for stopping cannot be inferred from the parking controller.'},
        {'phrase': 'the directions of a police officer',
         'note': 'Original officer identity, authority, communication and applicability require independent source review.'},
        {'phrase': 'official traffic-control device',
         'note': 'Original official device identity, display, applicability and direction require independent source review.'}]
    parameters = [
        {'name': 'commanded_parking_target_x_m', 'kind': 'controller',
         'range_or_domain': 'authored intersection coordinate in metres'},
        {'name': 'observed_intersection_body_overlap_m2', 'kind': 'subject_behavior',
         'range_or_domain': 'measured full-body sampled overlap area, originally unknown'},
        {'name': 'observed_parked_duration_s', 'kind': 'subject_behavior',
         'range_or_domain': 'measured continuous rest interval, originally unknown'},
        {'name': 'original_exception_context', 'kind': 'world_setup',
         'range_or_domain': 'source-qualified conflict, applicable law, officer and official-device context'}]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
        'quote': law['text'], 'status': 'draft',
        'structure': {'law_id': law_id,
            'activation': {'condition': 'A person stops, stands or parks a vehicle within an intersection.',
                           'numeric_conditions': []},
            'obligation': {'type': 'must_not', 'description': 'Do not stop, stand or park there when no statutory exception applies.',
                           'numeric_conditions': []},
            'exceptions': [
                {'source_clause': 'necessary to avoid conflict with other traffic',
                 'description': 'A halt necessary to avoid conflict with other traffic; causal necessity remains unresolved.'},
                {'source_clause': 'in compliance with law',
                 'description': 'A stop complying with applicable law; source and applicability remain unresolved.'},
                {'source_clause': 'the directions of a police officer',
                 'description': 'A stop directed by a police officer; authority and original direction remain unresolved.'},
                {'source_clause': 'official traffic-control device',
                 'description': 'A stop directed by an applicable official traffic-control device; original display remains unresolved.'}],
            'timing': {'description': 'Assess original parked or stopped footprint throughout the rest interval, preserving 20 Hz sample uncertainty.',
                       'numeric_conditions': []},
            'judgment_calls_needed': judgments},
        'parameter_refs': parameters}
    write(PROPOSALS / 'template.json', template)
    refs = []
    names = ['drv.forced_halt', 'native_body_pose_control', 'dev.human_direction', 'dev.traffic_signal']
    for index, (judgment, name) in enumerate(zip(judgments, names)):
        value = {'template_id': template_id, 'phrase': judgment['phrase'],
            'note': judgment['note'], 'status': 'draft',
            'observable_requirements': {'observables': [{'name': name, 'unit': 'structured',
                'description': 'Original time-joined Native source observations relevant to this phrase'}],
                'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': name, 'unit': 'structured',
                    'description': 'Retain original source and provenance; do not infer legal satisfaction'}],
                'limitations': ['Synthetic source-shaped diagnostics cannot establish the legal judgment or absence of an exception.']}}
        path = PROPOSALS / f'judgment-{index}.json'
        write(path, value)
        refs.append({'path': path.relative_to(HERE).as_posix(), 'sha256': sha(path)})
    bindings = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'established_contexts': ['Authored two-way intersection parking context; original map, highway definition, body and exception sources require local review.'],
        'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{**parameter, 'used_by_laws': [law_id]} for parameter in parameters]}
    write(PROPOSALS / 'bindings.json', bindings)
    case_rows = []
    for suffix, target in [('baseline', None), ('probe_a', -13.0), ('probe_b', 0.0)]:
        case_id = HERE.name + '__' + suffix
        source_suffix = suffix if suffix != 'baseline' else 'probe_a'
        construction = json.loads((HERE / f'current-v2-{source_suffix}-primary-construction.json').read_text())
        assignments = {
            'commanded_parking_target_x_m': {'kind': 'controller', 'value': target if target is not None else -13.0, 'unit': 'm'},
            'observed_intersection_body_overlap_m2': {'kind': 'subject_behavior', 'value': None, 'unit': 'm2'},
            'observed_parked_duration_s': {'kind': 'subject_behavior', 'value': None, 'unit': 's'},
            'original_exception_context': {'kind': 'world_setup', 'value': 'source_unverified', 'unit': 'structured'}}
        row = {'case_id': case_id, 'target_law_id': law_id if suffix != 'baseline' else None,
            'target_type': 'baseline' if suffix == 'baseline' else 'judgment_sweep',
            'rationale': 'Authored parking target; original body, map, exception and pixels remain unverified.',
            'variable_assignments': assignments,
            'recording_description': construction['recording_description'],
            'unresolved_judgment_calls': [j['phrase'] for j in judgments] if suffix != 'baseline' else []}
        if suffix != 'baseline':
            row.update({'paired_probe_id': 'intersection_parking_footprint',
                        'deliberate_differences': ['commanded_parking_target_x_m'],
                        'probe': {'primary_variable': 'commanded_parking_target_x_m',
                            'comparison_or_standard': 'Outside versus inside sampled parked-body footprint; no legal verdict',
                            'target_value_or_branch': target}})
        case_rows.append(row)
    cases = {'cell_id': cell_id, 'actor': actor, 'status': 'draft', 'cases': case_rows,
             'sweep_specs': [{'sweep_id': 'intersection_parking_exception_judgments_pending',
                'target_law_id': law_id, 'status': 'incomplete', 'judgment_refs': judgments,
                'missing_inputs': ['Original conflict causation and other traffic',
                                   'Applicable law and stop direction',
                                   'Original police direction and authority',
                                   'Original official device state, applicability and direction'],
                'rationale': 'The two physical footprint cases are CPU prepared; exception judgments require original source review.'}],
             'sweeps_expanded': True}
    write(PROPOSALS / 'canonical-cases.json', cases)
    write(PROPOSALS / 'cases.json', cases)
    files = {'relevance_batch': 'relevance-batch.json', 'relevance': 'relevance.json',
             'template': 'template.json', 'judgment_observables': refs,
             'bindings': 'bindings.json', 'cases': 'canonical-cases.json'}
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
             'status': 'draft_source_qualified_judgment_pending',
             'stages': {key: value if isinstance(value,list) else
                 {'path': f'proposals/{value}', 'sha256': sha(PROPOSALS / value)}
                 for key, value in files.items()}}
    write(PROPOSALS / 'semantic-index.json', index)
    print(json.dumps({'cases': len(case_rows), 'judgments': len(judgments),
                      'semantic_index_sha256': sha(PROPOSALS / 'semantic-index.json')}))


if __name__ == '__main__':
    main()
