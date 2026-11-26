"""Author draft source-faithful semantic stages for C149470 diagnostic cases."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'LVMC-11-60-030-A4'
ACTOR = 'bus_driver'
TEMPLATE = LAW + '@' + ACTOR
NAMES = ('bus_stop_below', 'bus_stop_at', 'bus_stop_above',
         'bus_stand_baggage', 'passenger_zone_unload',
         'origin_point_load', 'destination_point_unload')


def write(name, value):
    path = HERE / 'proposals' / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
    quote = assignment['law']['text']
    relevance = {'cell_id': 'C149470', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': [ACTOR], 'confidence': 'high'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance.json', relevance)
    write('relevance-batch.json', relevance)
    judgments = [
        ('approximately parallel to the curb',
         'Original bus heading, curb tangent and camera views need independent review.',
         'camera_frame_identity'),
        ('not to unduly impede the movement of other vehicular traffic',
         'Original traffic trajectories and available movement need independent review.',
         'other_traffic')]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
                'status': 'draft', 'quote': quote,
                'structure': {
                    'law_id': LAW,
                    'activation': {'condition': 'Operator of a non-tour bus enters a listed loading place on a public street and stops to load or unload passengers or baggage.',
                                   'numeric_conditions': []},
                    'obligation': {'description': 'At stopped loading, position the right-hand front wheel no farther than eighteen inches from the curb, with the bus approximately parallel, without unduly impeding other vehicular traffic.',
                                   'type': 'must',
                                   'numeric_conditions': [{'variable': 'wheel_curb_distance_m',
                                                           'operator': '<=', 'value': .4572,
                                                           'unit': 'm'}]},
                    'exceptions': [],
                    'timing': {'description': 'Evaluate the stopped passenger or baggage loading interval.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                              for phrase, note, _ in judgments]},
                'parameter_refs': [
                    {'name': 'wheel_curb_distance_m', 'kind': 'world_setup',
                     'range_or_domain': 'requested distance in metres; actual source interval measured separately', 'unit': 'm'},
                    {'name': 'location_kind', 'kind': 'world_setup',
                     'range_or_domain': 'bus stop, bus stand, passenger loading zone, origin or destination point', 'unit': 'category'},
                    {'name': 'loading_activity', 'kind': 'world_setup',
                     'range_or_domain': 'passenger or baggage loading or unloading', 'unit': 'category'},
                    {'name': 'heading_request_deg', 'kind': 'world_setup',
                     'range_or_domain': 'engineering bus approach heading request, 0 to 8 degrees', 'unit': 'deg'},
                    {'name': 'traffic_lateral_request_m', 'kind': 'world_setup',
                     'range_or_domain': 'engineering separate traffic route offset, 2 to 4 metres', 'unit': 'm'},
                    {'name': 'bus_curb_angle_deg', 'kind': 'world_setup',
                     'range_or_domain': 'pending original stopped bus heading measurement', 'unit': 'deg'},
                    {'name': 'traffic_speed_mps', 'kind': 'world_setup',
                     'range_or_domain': 'pending original separate traffic speed measurement', 'unit': 'm/s'}]}
    template_ref = write('template.json', template)
    judgment_refs = []
    for number, (phrase, note, channel) in enumerate(judgments):
        judgment_refs.append(write(f'judgment-{number}.json', {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': channel, 'unit': 'source observation',
                                 'description': note}],
                'context_inputs': [], 'sweep_dimensions': [
                    {'name': 'bus_curb_angle_deg' if channel == 'camera_frame_identity' else 'traffic_speed_mps',
                     'unit': 'deg' if channel == 'camera_frame_identity' else 'm/s',
                     'description': 'Original stopped-loading physical stream; no legal predicate'}],
                'landmarks': [],
                'recording_needs': [{'name': channel,
                                     'unit': 'frame ID' if channel == 'camera_frame_identity' else 'm/s',
                                     'description': note}],
                'limitations': ['Physical observations do not resolve the legal phrase; original reviewed source and independent judgment remain required.']}}))
    binding = {'cell_id': 'C149470', 'actor': ACTOR, 'status': 'draft',
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [dict(item, used_by_laws=[LAW])
                                       for item in template['parameter_refs']]}
    binding_ref = write('bindings.json', binding)
    first = json.loads((HERE / 'construction-compatibility-bus_stop_below.json').read_text())
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'status': 'draft',
                'rationale': 'Shared source-bound non-tour-bus loading baseline without a legal finding.',
                'variable_assignments': {
                    'wheel_curb_distance_m': {'kind': 'world_setup', 'value': .4472, 'unit': 'm'},
                    'location_kind': {'kind': 'world_setup', 'value': 'bus_stop', 'unit': 'category'},
                    'loading_activity': {'kind': 'world_setup', 'value': 'passenger_loading', 'unit': 'category'},
                    'heading_request_deg': {'kind': 'world_setup', 'value': 0.0, 'unit': 'deg'},
                    'traffic_lateral_request_m': {'kind': 'world_setup', 'value': 3.0, 'unit': 'm'},
                    'bus_curb_angle_deg': {'kind': 'world_setup', 'value': 'pending_original_measurement', 'unit': 'deg'},
                    'traffic_speed_mps': {'kind': 'world_setup', 'value': 'pending_original_measurement', 'unit': 'm/s'}},
                'unresolved_judgment_calls': [x[0] for x in judgments],
                'recording_description': first['recording_description']}
    cases = [baseline]
    from bus_curb import CASES
    by_name = {case.name: case for case in CASES}
    for name in NAMES:
        case = by_name[name]
        construction = json.loads((HERE / f'construction-compatibility-{name}.json').read_text())
        boundary = name in NAMES[:3]
        case_id = AID + '__' + name
        cases.append({'case_id': case_id, 'target_law_id': LAW,
                      'target_type': 'boundary_probe', 'status': 'draft',
                      'rationale': 'Requested distance and listed-place probe; original measurements and legal judgments remain open.',
                      'paired_probe_id': 'eighteen_inch_boundary' if boundary else 'listed_place_activity',
                      'deliberate_differences': ['wheel_curb_distance_m'] if boundary else ['location_kind', 'loading_activity'],
                      'variable_assignments': {
                          'wheel_curb_distance_m': {'kind': 'world_setup', 'value': case.target_distance_m, 'unit': 'm'},
                          'location_kind': {'kind': 'world_setup', 'value': case.location, 'unit': 'category'},
                          'loading_activity': {'kind': 'world_setup', 'value': case.activity, 'unit': 'category'},
                          'heading_request_deg': {'kind': 'world_setup', 'value': 0.0, 'unit': 'deg'},
                          'traffic_lateral_request_m': {'kind': 'world_setup', 'value': 3.0, 'unit': 'm'},
                          'bus_curb_angle_deg': {'kind': 'world_setup', 'value': 'pending_original_measurement', 'unit': 'deg'},
                          'traffic_speed_mps': {'kind': 'world_setup', 'value': 'pending_original_measurement', 'unit': 'm/s'}},
                      'unresolved_judgment_calls': [x[0] for x in judgments],
                      'recording_description': construction['recording_description'],
                      'probe': {'primary_variable': 'wheel_curb_distance_m' if boundary else 'location_kind',
                                'comparison_or_standard': 'Requested setup only; compare original stopped-loading source measurements and retain qualitative judgments.',
                                'target_value_or_branch': case.target_distance_m if boundary else case.location,
                                **({'threshold_ref': 'obligation.numeric_conditions[0]',
                                    'operator': '<=', 'unit': 'm',
                                    'test_value': case.target_distance_m} if boundary else {})},
                      **({'epsilon_used': {'value': .01, 'unit': 'm',
                                           'rationale': 'Engineering probe separation about the exact eighteen-inch conversion.'}} if boundary else {})})
    sweeps = []
    for name, judgment, variable, observable, unit, start, stop, spacing, statistic in (
        ('parallel_source_review', judgments[0], 'heading_request_deg',
         'bus_curb_angle_deg', 'deg', 0.0, 8.0, 4.0, 'max'),
        ('traffic_impediment_source_review', judgments[1], 'traffic_lateral_request_m',
         'traffic_speed_mps', 'm/s', 2.0, 4.0, 1.0, 'min')):
        phrase, note, _ = judgment
        assignments = dict(baseline['variable_assignments'])
        assignments.update({
            'heading_request_deg': {'kind': 'world_setup', 'value': 0.0, 'unit': 'deg'},
            'traffic_lateral_request_m': {'kind': 'world_setup', 'value': 3.0, 'unit': 'm'}})
        sweeps.append({'sweep_id': AID + '__' + name, 'target_law_id': LAW,
            'judgment_refs': [{'phrase': phrase, 'note': note}], 'status': 'complete',
            'mode': 'one_dimensional',
            'rationale': 'Fixed engineering position requests for original physical coverage; no legal cutoff or verdict is inferred.',
            'axes': [{'variable': variable, 'observable': observable, 'unit': unit,
                'min': start, 'max': stop, 'spacing': spacing,
                'measurement': {'method': 'Original source-sealed stopped-loading bus heading relative to curb or separate vehicular traffic speed',
                    'time_window': 'original 20 Hz stopped loading interval', 'statistic': statistic},
                'range_rationale': 'Bounded route geometry supported by bus_curb.py and source-gated fixture tests; engineering coverage only.',
                'spacing_rationale': 'Distinct route geometry requests for observable physical variation; no legal judgment boundary.',
                'feasibility_evidence': 'bus_curb.py route construction and synthetic 900-frame measurement fixtures'}],
            'landmarks': [], 'variable_assignments': assignments,
            'recording_description': first['recording_description'],
            'production_source_requirements': [
                'reviewed original public-street location, curb tangent and bus pose',
                'reviewed separate other-traffic route and movement',
                'retained original 20 Hz bus, traffic, loading and four camera histories']})
    proposal = {'cell_id': 'C149470', 'actor': ACTOR, 'status': 'draft',
                'sweep_specs': sweeps, 'sweeps_expanded': False, 'cases': cases}
    sys.path.insert(0, str(ROOT / 'runtime'))
    from scenario_pipeline.batch_pipeline.sweeps import expand_sweeps
    expand_sweeps(proposal, [template], binding)
    cases_ref = write('cases.json', proposal)
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                   'assignment_id': AID,
                                   'stages': {'relevance_batch': relevance_ref,
                                              'relevance': relevance_ref,
                                              'template': template_ref,
                                              'judgment_observables': judgment_refs,
                                              'bindings': binding_ref,
                                              'cases': cases_ref},
                                   'status': 'complete_source_gated_engineering_sweeps'})


if __name__ == '__main__':
    main()
