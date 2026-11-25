"""Build source-faithful canonical stage proposals for paragraph (a)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'NRS-484B-210-1'
TEMPLATE = LAW + '@motor_vehicle_driver'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment_path = ROOT / 'inputs' / AID / 'assignment.json'
    assignment = json.loads(assignment_path.read_text())
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    quote = assignment['law']['text']
    folder = HERE / 'proposals'
    channel_specs = [
        ('ego_target_identity', 'actor IDs', 'Distinct original Native ego and target actor identities'),
        ('relative_longitudinal_order', 'm', 'Original actor stations before, during and after passing'),
        ('relative_lateral_order', 'm', 'Original right-positive actor offsets during passing'),
        ('target_left_signal', 'boolean', 'Actual original target light-state readback per frame'),
        ('target_left_motion', 'frame sequence', 'Actual target heading and left lateral displacement'),
        ('intersection_bounds', 'm', 'Original map intersection station interval and crossing frames'),
        ('paved_surface_occupation', 'boolean', 'Original actor footprint within source paved bounds'),
        ('road_direction_and_lane_count', 'source record', 'Original two-way road and marked lane topology review'),
        ('original_road_and_intersection', 'source record', 'Hash-bound public-highway, intersection and paved corridor review'),
        ('ego_target_identity_and_order', 'frame sequence', 'Original actor IDs and relative longitudinal/lateral body positions'),
        ('target_left_signal_state', 'boolean', 'Original target light-state readback on pass frames'),
        ('target_left_turn_motion', 'frame sequence', 'Original target lateral displacement and heading on pass frames'),
        ('pass_and_pavement_history', 'frame sequence', 'Original ego and target body footprints, pass interval and paved bounds'),
        ('four_camera_frame_join', 'frame sequence', 'Original synchronized front, rear, left and right media frame identities'),
    ]
    description = {
        'channels': [{'name': name, 'unit': unit, 'method': method,
                      'sampling_rate_hz': 20,
                      'time_window': 'Full original 45-second intersection right-pass episode',
                      'reference_frame': 'Original Native map station and 20 Hz frame map',
                      'uncertainty': 'Physical route, left motion/signal and view quality need original source review.'}
                     for name, unit, method in channel_specs],
        'context_inputs': [
            {'name': 'reviewed_map_packet', 'unit': 'source record',
             'method': 'Original OpenDRIVE SHA, road/intersection/pavement and world centerline anchors'},
            {'name': 'reviewed_vehicle_setup', 'unit': 'source record',
             'method': 'Original actor footprint, distinct identities, controller setup and four camera mounts'}],
        'limitations': [
            'Requested signal and turn behavior do not establish observed behavior.',
            'Paragraph (b), (c), (d) and subsection 4 alternatives remain separately unresolved.',
            'No legal verdict or physical acceptance is inferred from CPU fixtures.']}
    for row in plan['cases']:
        row['recording_description'] = description
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'both actor bodies, paved right corridor and intersection',
             'interval': 'startup through pass and clearance'},
            {'view': 'approach', 'subject': 'target left signal and relative approach',
             'interval': 'approach through pass'},
            {'view': 'reference_corner', 'subject': 'intersection bounds and paved surface occupation',
             'interval': 'entry through clearance'},
            {'view': 'driver_reference', 'subject': 'ego and target right-side ordering',
             'interval': 'approach through clearance'}]}
    plan['source_observation_mapping'] = {}
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    relevance = {'cell_id': 'C110264', 'actor': 'motor_vehicle_driver', 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': ['motor_vehicle_driver'],
                                    'relevance_type': 'paragraph (a) right pass near an intersection with target left turn or signal',
                                    'confidence': 'medium',
                                    'notes': 'Public highway, paved corridor, observed target action and other alternatives need original review.'}],
                 'borderline_excluded': []}
    relevance_ref = write(folder / 'relevance.json', relevance)
    judgment_specs = [
        ('driver of the vehicle overtaken is making or signaling to make a left turn',
         'Determine actual target light state or turn motion during the observed right pass.',
         'target_left_signal_state'),
        ('overtake and pass upon the right',
         'Determine original ego/target order and lateral position, not a requested route.',
         'ego_target_identity_and_order'),
        ('upon a highway',
         'Review original road status, pavement, intersection and other permission alternatives.',
         'original_road_and_intersection'),
    ]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': 'motor_vehicle_driver',
                'status': 'draft', 'quote': quote,
                'structure': {
                    'law_id': LAW,
                    'activation': {'condition': 'A driver overtakes and passes a separate vehicle on the right near an intersection.',
                                   'numeric_conditions': []},
                    'obligation': {'description': 'Paragraph (a) permits this right pass when the overtaken driver is making or signaling a left turn; other alternatives are separately unresolved.',
                                   'type': 'permission', 'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'Observe target signal or left turn during the original right-pass interval.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                              for phrase, note, _ in judgment_specs]},
                'parameter_refs': [
                    {'name': 'target_behavior_request', 'kind': 'controller',
                     'range_or_domain': 'left_signal, left_turn or neither; observed behavior is separately measured'},
                    {'name': 'reviewed_right_pass_site', 'kind': 'world_setup',
                     'range_or_domain': 'original two-way intersection map with source-reviewed paved right corridor'}]}
    template_ref = write(folder / 'template.json', template)
    unit_lookup = {name: unit for name, unit, _ in channel_specs}
    judgments = []
    for number, (phrase, note, observable) in enumerate(judgment_specs, 1):
        judgments.append(write(folder / f'judgment-{number}.json', {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': observable, 'unit': unit_lookup[observable],
                                 'description': note}],
                'context_inputs': [{'name': 'reviewed_map_packet', 'unit': 'source record',
                                    'description': 'Retain original OpenDRIVE and independent highway/pavement review.'}],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': observable, 'unit': unit_lookup[observable],
                                     'description': 'Retain original 20 Hz actors and camera source hashes.'}],
                'limitations': ['Controller intent and synthetic fixtures do not establish physical or legal outcome.']}}))
    binding = {'cell_id': 'C110264', 'actor': 'motor_vehicle_driver', 'status': 'draft',
               'established_contexts': ['intersection right-pass study'],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': x['name'], 'kind': x['kind'],
                                        'range_or_domain': x['range_or_domain'],
                                        'used_by_laws': [LAW]} for x in template['parameter_refs']]}
    binding_ref = write(folder / 'bindings.json', binding)
    stage_cases = [{'case_id': AID + '__baseline', 'target_law_id': None,
                    'target_type': 'baseline', 'status': 'draft',
                    'rationale': 'Shared original map, actor, paved corridor and four-camera capture setup.',
                    'variable_assignments': {
                        'target_behavior_request': {'kind': 'controller', 'value': 'neither'},
                        'reviewed_right_pass_site': {'kind': 'world_setup', 'value': 'source_reviewed'}},
                    'recording_description': description,
                    'unresolved_judgment_calls': [x[0] for x in judgment_specs]}]
    for row in plan['cases']:
        suffix = row['case_id'].removeprefix(AID + '__')
        pair = ('left_signal_presence' if suffix == 'left_signal' else
                'left_turn_motion_presence' if suffix == 'left_turn' else 'shared_neither_baseline')
        stage_cases.append({'case_id': row['case_id'], 'target_law_id': LAW,
                            'target_type': 'judgment_sweep', 'status': 'draft',
                            'rationale': 'Exact target signal/motion contrast; original behavior and legal outcome remain unresolved.',
                            'paired_probe_id': pair,
                            'deliberate_differences': ['target_behavior_request'],
                            'variable_assignments': {
                                'target_behavior_request': {'kind': 'controller', 'value': suffix},
                                'reviewed_right_pass_site': {'kind': 'world_setup', 'value': 'source_reviewed'}},
                            'unresolved_judgment_calls': [x[0] for x in judgment_specs],
                            'recording_description': description,
                            'probe': {'primary_variable': 'target_behavior_request',
                                      'comparison_or_standard': 'Actual signal and motion from original pass frames; no legal cutoff.',
                                      'target_value_or_branch': suffix}})
    sweeps = [{'sweep_id': f'c110264-judgment-{i}', 'target_law_id': LAW,
               'judgment_refs': [{'phrase': phrase, 'note': note}],
               'status': 'incomplete',
               'rationale': 'Original road review and Native physical observations are pending.',
               'missing_inputs': ['reviewed original map and physical Native observations']}
              for i, (phrase, note, _) in enumerate(judgment_specs, 1)]
    cases_ref = write(folder / 'cases.json', {'cell_id': 'C110264',
                                             'actor': 'motor_vehicle_driver',
                                             'status': 'draft', 'sweeps_expanded': True,
                                             'cases': stage_cases, 'sweep_specs': sweeps})
    write(folder / 'semantic-index.json', {'format': 'worker-semantic-delivery',
          'assignment_id': AID,
          'source': {'path': str(assignment_path.relative_to(ROOT)),
                     'sha256': hashlib.sha256(assignment_path.read_bytes()).hexdigest()},
          'stages': {'relevance_batch': relevance_ref, 'relevance': relevance_ref,
                     'template': template_ref, 'judgment_observables': judgments,
                     'bindings': binding_ref, 'cases': cases_ref},
          'status': 'draft_local_source_and_physical_review_pending'})


if __name__ == '__main__':
    main()
