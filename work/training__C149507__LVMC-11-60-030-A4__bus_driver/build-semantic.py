"""Author source-specific canonical semantic proposals for selected bus loading pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'LVMC-11-60-030-A4'
ACTOR = 'bus_driver'
PLAN = json.loads((HERE / 'case-plan.json').read_text())
TEXT = PLAN['source_law']['text']
TID = LAW + '@' + ACTOR
REC = json.loads((HERE / 'config.json').read_text())['recording_description']
J = [
    {'phrase': 'approximately parallel', 'note': 'Curb heading difference is measured, but the statute supplies no numeric angular threshold; original geometry needs independent review.'},
    {'phrase': 'unduly impede', 'note': 'Other vehicle speed and delay are measured, but the statute supplies no numerical undue-impedance cutoff; traffic context needs independent review.'},
]


def write(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': 'C149507', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'direct', 'confidence': 'high',
            'notes': 'Frozen one-way-road bus loading with following vehicle; non-tour bus, public street and qualifying location remain original-source gated.'}],
        'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance-batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    structure = {'law_id': LAW,
        'activation': {'condition': 'Operator of a bus other than a tour bus enters a bus stop, bus stand, passenger loading zone or origin or destination point on a public street and stops to load or unload passengers or baggage.', 'numeric_conditions': []},
        'obligation': {'type': 'must', 'description': 'When stopped to load or unload, right-hand front wheel is not farther than eighteen inches from curb and bus is approximately parallel so as not to unduly impede other vehicular traffic.', 'numeric_conditions': [{'variable': 'wheel_gap', 'operator': '<=', 'value': 18, 'unit': 'inch'}]},
        'exceptions': [{'source_clause': 'other than a tour bus', 'condition': 'tour bus', 'effect': 'Excluded from this paragraph; bus classification requires source review.'}],
        'timing': {'description': 'Assess position when stopped for passenger or baggage loading or unloading.', 'numeric_conditions': []},
        'judgment_calls_needed': J}
    params = [
        {'name': 'vehicle_scope', 'kind': 'world_setup', 'range_or_domain': 'source-reviewed non-tour bus'},
        {'name': 'loading_location', 'kind': 'world_setup', 'range_or_domain': 'source-reviewed bus stop on public street'},
        {'name': 'curb_and_traffic', 'kind': 'world_setup', 'range_or_domain': 'surveyed curb and following vehicle'},
        {'name': 'wheel_gap_target_m', 'kind': 'controller', 'range_or_domain': [0.30, 0.4572, 0.70]},
        {'name': 'observed_loading_position', 'kind': 'subject_behavior', 'range_or_domain': 'original wheel/curb/heading and traffic readback'},
    ]
    template = {'template_id': TID, 'law_id': LAW, 'actor': ACTOR,
        'quote': TEXT, 'status': 'draft', 'structure': structure, 'parameter_refs': params}
    refs['template'] = write('template.json', template)
    refs['judgment_observables'] = []
    for index, item in enumerate(J):
        angular = index == 0
        observables = {'observables': [{'name': 'bus_wheel_and_pose' if angular else 'other_vehicle_motion', 'unit': 'structured',
            'description': 'Original bus-to-curb heading geometry' if angular else 'Original following-vehicle motion and delay'}],
            'context_inputs': [{'name': 'bus_zone_review', 'unit': 'structured', 'description': 'Source-reviewed non-tour bus, public street, qualifying bus stop, curb and traffic.'}],
            'sweep_dimensions': [{'name': 'bus_wheel_and_pose' if angular else 'other_vehicle_motion', 'unit': 'structured',
                'description': 'Controlled wheel gap with heading and traffic context held fixed; no invented legal cutoff.'}],
            'landmarks': [],
            'recording_needs': [{'name': 'curb_and_zone_geometry', 'unit': 'structured', 'description': 'Surveyed curb and source video.'},
                                {'name': 'bus_wheel_and_pose', 'unit': 'structured', 'description': 'Original bus wheel, heading and stopped loading.'}],
            'limitations': ['Independent original-source judgment remains required; measurement is not a legal verdict.']}
        refs['judgment_observables'].append(write(f'judgment-observables-{index + 1}.json',
            {'template_id': TID, 'phrase': item['phrase'], 'note': item['note'], 'status': 'draft',
             'observable_requirements': observables}))
    binding = {'cell_id': 'C149507', 'actor': ACTOR, 'status': 'draft',
        'established_contexts': ['Frozen one-way-road load/unload cell with other vehicle; original bus and public-street location review required.'],
        'law_refs': [{'template_id': TID, 'binding_kind': 'direct'}], 'context_refs': [],
        'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[LAW]) for item in params]}
    refs['bindings'] = write('bindings.json', binding)
    common = {item['name']: {'kind': item['kind'], 'value': None if item['name'] == 'observed_loading_position' else
        ('non_tour_bus' if item['name'] == 'vehicle_scope' else
         'bus_stop_on_public_street' if item['name'] == 'loading_location' else
         'surveyed_curb_and_following_vehicle' if item['name'] == 'curb_and_traffic' else 0.30)} for item in params}
    selected = []
    for suffix, target in (('probe_1', 0.30), ('probe_2', 0.70), ('probe_3', 0.4572)):
        assignments = json.loads(json.dumps(common))
        assignments['wheel_gap_target_m']['value'] = target
        selected.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW,
            'target_type': 'boundary_probe',
            'rationale': 'Compare source-measured right-front-wheel gap across the statutory eighteen-inch value while holding bus scope, loading location, heading and traffic context fixed; no legal verdict.',
            'variable_assignments': assignments,
            'unresolved_judgment_calls': [item['phrase'] for item in J],
            'epsilon_used': {'value': 0.005, 'unit': 'm', 'rationale': 'Engineering measurement tolerance for requested wheel placement, not a statutory tolerance or legal classification.'},
            'recording_description': REC,
            'paired_probe_id': AID + '__wheel_gap_comparison',
            'deliberate_differences': ['wheel_gap_target_m'],
            'probe': {'primary_variable': 'wheel_gap_target_m',
                'comparison_or_standard': 'Source-measured right-front-wheel gap relative to 18 inches',
                'target_value_or_branch': target,
                'threshold_ref': 'obligation.numeric_conditions[0]',
                'operator': '<=', 'unit': 'inch', 'test_value': 18 if suffix == 'probe_3' else target / 0.0254},
            'deterministic_branch': {'source_clause': TEXT,
                'judgment_context': [{'phrase': item['phrase'], 'note': item['note'],
                    'status': 'fixed_assumption',
                    'reason': 'Original heading and following-traffic source review is held fixed across the wheel-gap pair; physical outcome is audited after capture.',
                    'world_setup_refs': ['vehicle_scope', 'loading_location', 'curb_and_traffic']} for item in J]}})
    cases = {'cell_id': 'C149507', 'actor': ACTOR, 'status': 'draft', 'sweeps_expanded': True,
        'cases': [{'case_id': AID + '__neutral_baseline', 'target_law_id': None,
            'target_type': 'baseline', 'rationale': 'Unselected common context reference; no legal label.',
            'variable_assignments': common, 'unresolved_judgment_calls': [],
            'recording_description': REC}] + selected,
        'sweep_specs': [{'sweep_id': LAW + '-wheel-gap-and-traffic', 'target_law_id': LAW,
            'judgment_refs': J, 'status': 'incomplete',
            'rationale': 'Approximately parallel and undue impedance lack numeric legal cutoffs.',
            'missing_inputs': ['Original Native bus classification, zone, curb, loading activity and traffic review not in frozen inputs.']}]}
    refs['cases'] = write('cases.json', cases)
    write('semantic-index.json', {'format': 'worker-semantic-delivery', 'assignment_id': AID, 'stages': refs})
    print(json.dumps({'selected_cases': [item['case_id'] for item in selected]}, sort_keys=True))


if __name__ == '__main__':
    main()
