"""Build source-faithful same-lane motorcycle semantic proposals."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
TEMPLATE = LAW['id'] + '@' + ASSIGNMENT['actor']
CASES = [ROOT.name + '__controlled_1', ROOT.name + '__controlled_2']


def put(name, value):
    path = ROOT / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False).rstrip() + '\n')
    return {'path': path.relative_to(ROOT).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': 'C146108', 'actor': ASSIGNMENT['actor'], 'status': 'draft',
        'relevant_laws': [{'law_id': LAW['id'], 'quote': LAW['text'],
            'applies_to': [ASSIGNMENT['actor']], 'relevance_type': 'direct',
            'confidence': 'high',
            'notes': 'One-way multilane road with other vehicle; selected source-bound comparison is following versus same-lane passing.'}],
        'borderline_excluded': []}
    r1 = put('relevance_batch.json', relevance)
    r2 = put('relevance.json', relevance)
    judgment = {'phrase': 'abreast of or overtake or pass another vehicle within the same traffic lane',
                'note': 'Require original full-body lane and longitudinal order; consent and subsection 3 cannot be inferred from adjacency.'}
    params = [
        {'name': 'rider_target_speed_mps', 'kind': 'controller', 'range_or_domain': [3, 5]},
        {'name': 'other_vehicle_speed_mps', 'kind': 'controller', 'range_or_domain': [3]},
        {'name': 'rider_vehicle_class', 'kind': 'world_setup', 'range_or_domain': ['motorcycle']},
        {'name': 'other_vehicle_class', 'kind': 'world_setup', 'range_or_domain': ['motor_vehicle']},
        {'name': 'subsection_3_pair_eligibility', 'kind': 'world_setup',
         'range_or_domain': ['inapplicable_to_motorcycle_car_pair']},
    ]
    template = {'template_id': TEMPLATE, 'law_id': LAW['id'], 'actor': ASSIGNMENT['actor'],
        'quote': LAW['text'], 'status': 'draft',
        'structure': {'law_id': LAW['id'],
            'activation': {'condition': 'Person drives a motorcycle, moped or trimobile with another vehicle within the same traffic lane.',
                           'numeric_conditions': []},
            'obligation': {'type': 'must_not',
                           'description': 'Do not drive abreast of, overtake or pass the other vehicle within that lane.',
                           'numeric_conditions': []},
            'exceptions': [{'source_clause': 'Except as provided in subsection 3; motorcycles and mopeds may, with consent of the drivers, be operated no more than two abreast in a single traffic lane.',
                            'condition': 'Two motorcycle or moped drivers consent and no more than two ride abreast.',
                            'effect': 'Permitted abreast operation; not applicable to a motorcycle-car pair.'}],
            'timing': {'description': 'Compare original complete body overlap and behind-to-ahead episode at 20 Hz over 30 seconds.',
                       'numeric_conditions': []},
            'judgment_calls_needed': [judgment]},
        'parameter_refs': params}
    r3 = put('template.json', template)
    r4 = put('judgment-observables-1.json', {'template_id': TEMPLATE,
        'phrase': judgment['phrase'], 'note': judgment['note'], 'status': 'draft',
        'observable_requirements': {'observables': [
            {'name': name, 'unit': 'structured',
             'description': 'Original Native actor bodies, class and same-lane episode'}
            for name in ('ru.motorcycle', 'ru.moped', 'st.lane', 'rel.occupies',
                         'rel.longitudinal_overlap', 'drv.overtaking', 'rel.bearing',
                         'ru.motor_vehicle', 'rel.surface_gap')],
            'context_inputs': [{'name': 'subsection_3_exception', 'unit': 'source text',
                                'description': 'Class-pair and consent source review'}],
            'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [],
            'limitations': [judgment['note'], 'Actual Native pass, pixels and classification require original physical review.']}})
    binding = {'cell_id': 'C146108', 'actor': ASSIGNMENT['actor'], 'status': 'draft',
        'established_contexts': [],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(param, used_by_laws=[LAW['id']]) for param in params]}
    r5 = put('bindings.json', binding)
    recording = json.loads((ROOT / 'construction.json').read_text())['recording_description']
    cases = [{'case_id': ROOT.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Unselected same-lane source context.',
        'variable_assignments': {p['name']: {'kind': p['kind'], 'value': None,
                                             'unit': 'categorical'} for p in params},
        'unresolved_judgment_calls': [], 'recording_description': recording}]
    for rank, (case_id, speed, action) in enumerate(zip(CASES, (3, 5),
                                                       ('following', 'pass')), 1):
        cases.append({'case_id': case_id, 'target_law_id': LAW['id'],
            'target_type': 'judgment_sweep',
            'rationale': 'Original full-body source comparison of same-lane following and passing; legal judgment remains separate.',
            'variable_assignments': {
                'rider_target_speed_mps': {'kind': 'controller', 'value': speed, 'unit': 'm/s'},
                'other_vehicle_speed_mps': {'kind': 'controller', 'value': 3, 'unit': 'm/s'},
                'rider_vehicle_class': {'kind': 'world_setup', 'value': 'motorcycle', 'unit': 'categorical'},
                'other_vehicle_class': {'kind': 'world_setup', 'value': 'motor_vehicle', 'unit': 'categorical'},
                'subsection_3_pair_eligibility': {'kind': 'world_setup',
                    'value': 'inapplicable_to_motorcycle_car_pair', 'unit': 'categorical'}},
            'unresolved_judgment_calls': [judgment['phrase']],
            'paired_probe_id': ROOT.name + '__same_lane_comparison',
            'deliberate_differences': ['rider_target_speed_mps'],
            'probe': {'primary_variable': 'rider_target_speed_mps',
                      'comparison_or_standard': 'Original full-body following versus pass order',
                      'target_value_or_branch': action},
            'recording_description': recording, 'selection_rank': rank})
    r6 = put('cases.json', {'cell_id': 'C146108', 'actor': ASSIGNMENT['actor'],
        'status': 'draft', 'sweep_specs': [{
            'sweep_id': ROOT.name + '__same_lane_comparison',
            'target_law_id': LAW['id'], 'status': 'incomplete',
            'judgment_refs': [judgment],
            'rationale': 'Controlled source-bound following and pass comparison.',
            'missing_inputs': ['Original Native physical capture and independent review.']}],
        'sweeps_expanded': True, 'cases': cases})
    put('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': ROOT.name,
        'stages': {'relevance_batch': r1, 'relevance': r2, 'template': r3,
                   'judgment_observables': [r4], 'bindings': r5, 'cases': r6}})
    print('Two exact motorcycle semantic proposals written')


if __name__ == '__main__':
    main()
