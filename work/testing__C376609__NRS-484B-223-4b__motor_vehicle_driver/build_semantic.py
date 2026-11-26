"""Author source-grounded draft semantics for nine exclusive-right-turn-lane probes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-484B-223-4b'
PROPOSALS = HERE / 'proposals'


def put(name, value):
    PROPOSALS.mkdir(exist_ok=True)
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def assign(value):
    return {'kind': 'world_setup', 'value': value, 'unit': 'source request'}


def build():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if len(plan['cases']) != 9 or len(plan['comparisons']) != 8:
        raise ValueError('nine exact cases and eight comparisons required')
    ids = [c['case_id'] for c in plan['cases']]
    for case in plan['cases']:
        case['kind'] = 'delivery'
        case['new_capture_selected'] = True
        case['construction_status'] = 'source_gated_native_bundle_cpu_preparation'
    plan['selected_branch'] = plan['selected_branches'][0]['branch']
    plan['observations'] = [
        {'name': 'public_highway_and_lane_design', 'method': 'reviewed source hash and Native map identity', 'source': 'original site packet'},
        {'name': 'exclusive_right_turn_control', 'method': 'reviewed lane design and control source', 'source': 'original site packet'},
        {'name': 'intersection_entry_and_exit', 'method': 'reviewed entry/exit station survey and 20 Hz original trace', 'source': 'original site and Native attempt'},
        {'name': 'independent_route_intent', 'method': 'independent pre-entry route declaration', 'source': 'original source packet'},
        {'name': 'original_lane_and_vehicle_motion', 'method': '20 Hz original lane ID and body readback', 'source': 'original Native attempt'},
        {'name': 'sightline_and_four_camera_pixels', 'method': 'reviewed sightline and original synchronized RGB frames', 'source': 'original Native attempt'}]
    source = 'inputs/' + AID + '/assignment.json'
    plan['requirement_dispositions'] = [
        {'disposition_index': 0, 'requirement': 'highway designed to provide a single right lane used only for turning', 'source': source, 'status': 'selected_required', 'case_ids': ids, 'evidence_or_gap': 'reviewed original highway/lane survey pending'},
        {'disposition_index': 1, 'requirement': 'vehicle driven in the right turn lane', 'source': source, 'status': 'selected_required', 'case_ids': ids, 'evidence_or_gap': 'original 20 Hz lane occupancy pending'},
        {'disposition_index': 2, 'requirement': 'not travel through an intersection', 'source': source, 'status': 'selected_required', 'case_ids': ids, 'evidence_or_gap': 'reviewed intersection bounds and original trajectory pending'}]
    plan['source_observation_mapping'] = {}
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 45,
                           'composition': 'synchronized_four_view_primary',
                           'coverage': [{'view': x, 'subject': 'right-turn lane, ego route and intersection boundaries', 'interval': 'first through final original frame'}
                                        for x in ('overview', 'approach', 'reference_corner', 'driver_reference')],
                           'limitation': 'Original map and motion are required; camera view does not replace lane design survey.'}
    plan['planning_status'] = 'nine_selected_source_gated_cpu_preparation'
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    quote = plan['law_text']
    relevance = {'cell_id': plan['cell_id'], 'actor': plan['actor'], 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote, 'applies_to': [plan['actor']], 'confidence': 'high'}],
                 'borderline_excluded': []}
    relevance_ref = put('relevance.json', relevance)
    put('relevance-batch.json', relevance)
    template_id = LAW + '@' + plan['actor']
    parameters = [{'name': name, 'kind': 'world_setup', 'range_or_domain': domain, 'unit': 'source request'}
                  for name, domain in (('lane_design_request', 'single exclusive right turn, nonexclusive or multiple turn lanes'),
                                       ('ego_lane_request', 'right, adjacent through or right then adjacent before entry'),
                                       ('route_request', 'through, right turn or stop before'),
                                       ('intersection_request', 'non-alley or alley source designation'),
                                       ('sightline_request', 'blind or clear source survey'))]
    template_ref = put('template.json', {'template_id': template_id, 'law_id': LAW, 'actor': plan['actor'],
        'status': 'draft', 'quote': quote, 'structure': {
            'law_id': LAW,
            'activation': {'condition': 'Highway designed with one right lane used only for turning; vehicle driven in that lane.', 'numeric_conditions': []},
            'obligation': {'description': 'Vehicle in that right turn lane must not travel through an intersection.', 'type': 'must_not', 'numeric_conditions': []},
            'exceptions': [], 'timing': {'description': 'During original lane occupancy and intersection entry/departure.', 'numeric_conditions': []},
            'judgment_calls_needed': []}, 'parameter_refs': parameters})
    bindings_ref = put('bindings.json', {'cell_id': plan['cell_id'], 'actor': plan['actor'], 'status': 'draft',
        'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}], 'context_refs': [],
        'fixed_parameters': [], 'variable_parameters': [dict(x, used_by_laws=[LAW]) for x in parameters]})
    base = plan['cases'][0]
    def recording(case):
        suffix = case['case_id'].removeprefix(AID + '__')
        return json.loads((HERE / ('construction-selected-' + suffix + '.json')).read_text())['recording_description']
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline', 'status': 'draft',
                'rationale': 'Common public-highway intersection and motor vehicle require original site and motion review.',
                'variable_assignments': {name: assign(base[name]) for name in ('lane_design_request', 'ego_lane_request', 'route_request', 'intersection_request', 'sightline_request')},
                'unresolved_judgment_calls': ['Original lane design and travel-through are unreviewed'],
                'recording_description': recording(base)}
    selected = [baseline]
    for case in plan['cases']:
        suffix = case['case_id'].removeprefix(AID + '__')
        typ = 'violating_attempt' if suffix == 'exclusive_right_through_blind' else 'compliant_attempt' if suffix == 'exclusive_right_turn_blind' else 'boundary_probe'
        selected.append({'case_id': case['case_id'], 'target_law_id': LAW, 'target_type': typ,
            'status': 'draft', 'rationale': 'Controlled route/lane/design boundary; original facts and legal verdict remain unreviewed.',
            'paired_probe_id': 'exclusive-right-turn-lane-travel-through',
            'deliberate_differences': [x for x in ('lane_design_request', 'ego_lane_request', 'route_request', 'intersection_request', 'sightline_request') if case[x] != base[x]],
            'variable_assignments': {name: assign(case[name]) for name in ('lane_design_request', 'ego_lane_request', 'route_request', 'intersection_request', 'sightline_request')},
            'unresolved_judgment_calls': ['Original lane design and travel-through are unreviewed'],
            'recording_description': recording(case),
            'probe': {'primary_variable': 'route_request', 'comparison_or_standard': 'fixed source-reviewed highway, actor and cameras except deliberate variation',
                      'target_value_or_branch': suffix}})
    cases_ref = put('cases.json', {'cell_id': plan['cell_id'], 'actor': plan['actor'], 'status': 'draft',
                                  'sweep_specs': [], 'sweeps_expanded': True, 'cases': selected})
    put('semantic-index.json', {'format': 'worker-semantic-delivery', 'assignment_id': AID,
        'stages': {'relevance_batch': relevance_ref, 'relevance': relevance_ref, 'template': template_ref,
                   'judgment_observables': [], 'bindings': bindings_ref, 'cases': cases_ref},
        'status': 'source_gated_draft'})
    return len(selected)


if __name__ == '__main__':
    print('semantic draft entries:', build())
