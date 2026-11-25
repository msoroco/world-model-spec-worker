"""Saved-only Native finalizer for the exact crest observations.

This consumes sealed acquisition files and emits derived Native outputs. The
source packets and original videos are never changed by this analysis.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_crest import ONE_WAY_AUTHORITY, REQUIRED_SOURCES, measure, source_inventory


def _write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(value)


def analyze(attempt_dir, *, assignment_id, case_id, expected_frames=900,
            recording_description=None):
    from scenario_pipeline.worker_exchange.native_output import frame_record, validate_result

    attempt = Path(attempt_dir).resolve()
    manifest = attempt / 'source-hashes.json'
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError('sealed original source manifest missing')
    manifest_bytes = manifest.read_bytes()
    hashes = json.loads(manifest_bytes)
    source_inventory(hashes, case_id, expected_frames)
    observation = measure(attempt, hashes, case_id=case_id,
                          assignment_id=assignment_id, expected_frames=expected_frames)
    frame_rows = [json.loads(line) for line in (attempt / 'frames.jsonl').read_text().splitlines()]
    ray_rows = [json.loads(line) for line in (attempt / 'crest-rays.jsonl').read_text().splitlines()]
    if recording_description is None:
        config = json.loads((attempt / 'config.json').read_text(encoding='utf-8'))
        recording_description = config['case']['recording_description']
    if not isinstance(recording_description, dict):
        raise ValueError('recording description is missing')
    for name in ('video_frames.jsonl', 'result.json', 'crest-derived-trace.jsonl'):
        if (attempt / name).exists():
            raise ValueError('retain prior derived output; choose a fresh analysis stage')

    trace = []
    mapping = []
    for index, (body, ray) in enumerate(zip(frame_rows, ray_rows)):
        frame = body['frame']
        time_s = body['timestamp_s']
        trace.append({'frame': frame, 'time_s': time_s,
                      'ego_body_corners_signed_m': body['ego_body_corners_signed_m'],
                      'opposing_body_distance_m': body['opposing_body_distance_m'],
                      'opposing_body_corner_ray_hits': ray['body_corner_ray_hits']})
        mapping.append(frame_record(index, frame, time_s,
                                    camera_frames={name: frame for name in
                                                   ('overview', 'approach', 'reference_corner', 'driver_reference')}))

    recording_evidence = []
    context = json.loads((attempt / 'lane-context.json').read_text())
    profile_path = attempt / 'road-profile.json'
    profile = json.loads(profile_path.read_text()) if profile_path.is_file() else None
    channel_values = {
        'ego_center_offset_m': lambda body, ray: min(body['ego_body_corners_signed_m']),
        'ego_body_corners_signed_m': lambda body, ray: body['ego_body_corners_signed_m'],
        'opposing_body_distance_m': lambda body, ray: body['opposing_body_distance_m'],
        'opposing_body_corner_ray_hits': lambda body, ray: ray['body_corner_ray_hits'],
        'original_lane_directions': lambda body, ray: {
            'lane_allocation': context['lane_allocation'],
            'opposing_lane_source_ref': context.get('opposing_lane_source_ref'),
            'one_way_authority': context.get('one_way_authority')},
        'crest_grade_profile': lambda body, ray: profile['grade_proxy'] if profile else None,
        'ego_left_side_body_history': lambda body, ray: body['ego_body_corners_signed_m'],
        'opposing_vehicle_route_and_body': lambda body, ray: {
            'distance_m': body['opposing_body_distance_m'],
            'body_vertices_m': body.get('opposing_body_vertices_m'),
            'route_index': body.get('opposing_route_index'),
            'actor_source_ref': body['opposing_source_ref']},
        'driver_view_proxy_and_visibility': lambda body, ray: {
            'corner_ray_hits': ray['body_corner_ray_hits'],
            'ray_source_ref': ray['ray_source_ref']},
        'highway_one_way_context': lambda body, ray: {
            'highway_source_ref': context['highway_source_ref'],
            'lane_allocation': context['lane_allocation'],
            'one_way_authority': context.get('one_way_authority')},
        'frame_and_camera_join': lambda body, ray: {
            'frame': body['frame'],
            'camera_frames': {name: body['frame'] for name in
                ('overview', 'approach', 'reference_corner', 'driver_reference')}},
    }
    for channel in recording_description.get('channels', []):
        name = channel['name']
        if name not in channel_values:
            raise ValueError('unimplemented original crest recording channel: ' + name)
        if name == 'crest_grade_profile' and profile is None:
            raise ValueError('Missing required source: road-profile.json')
        reference = 'channels/' + name + '.jsonl'
        path = attempt / reference
        path.parent.mkdir(exist_ok=True)
        _write_new(path, ''.join(json.dumps({'time_s': body['timestamp_s'],
                            'value': channel_values[name](body, ray)}, sort_keys=True) + '\n'
                                 for body, ray in zip(frame_rows, ray_rows)))
        recording_evidence.append({'name': name, 'unit': channel['unit'],
                                   'reference': reference})
    context_values = {
        'lane_allocation': lambda context: context['lane_allocation'],
        'highway_source_ref': lambda context: context['highway_source_ref'],
        'center_reference_source_ref': lambda context: context['center_reference_source_ref'],
    }
    for item in recording_description.get('context_inputs', []):
        name = item['name']
        if name not in context_values:
            raise ValueError('unimplemented original crest recording context: ' + name)
        reference = 'channels/' + name + '.json'
        path = attempt / reference
        path.parent.mkdir(exist_ok=True)
        _write_new(path, json.dumps({name: context_values[name](context)},
                                    sort_keys=True) + '\n')
        recording_evidence.append({'name': name, 'unit': item['unit'],
                                   'reference': reference})

    expected_left = not case_id.endswith('__right_crest_obstructed')
    expected_blocked = not case_id.endswith('__left_crest_clear')
    measured_left = bool(observation['ego_body_left_side_frames'])
    measured_blocked = bool(observation['all_corner_rays_blocked_frames'])
    checks = []
    for target, requested, measured in (
            ('left-side body motion', expected_left, measured_left),
            ('all-corner proxy-ray blockage', expected_blocked, measured_blocked),
            ('body and view condition on one original frame', True,
             bool(observation['body_and_view_target_frames']))):
        checks.append({'target': target, 'requested': requested,
                       'measured': measured, 'method': 'sealed Native body/ray/frame join',
                       'tolerance': 0, 'matched': requested == measured,
                       'physical_cause_confirmed': False,
                       'cause_evidence': observation['source_sha256']})
    result = {'case_id': case_id, 'measured_values': observation,
              'target_checks': checks, 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Original crest packets measured; physical and legal review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [f'{name}.mkv' for name in
                                   ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': recording_description,
              'recording_evidence': recording_evidence, 'realized_observables': {}}
    validate_result(result)
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != hashlib.sha256(manifest_bytes).hexdigest():
        raise ValueError('original source manifest changed during analysis')
    if any(hashlib.sha256((attempt / name).read_bytes()).hexdigest() != digest
           for name, digest in hashes.items()):
        raise ValueError('original source changed during analysis')
    derived_trace = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in trace)
    core_trace = attempt / 'trace.jsonl'
    if core_trace.exists():
        existing = [json.loads(line) for line in core_trace.read_text().splitlines() if line]
        if len(existing) != len(trace) or any(
                row.get('frame') != target['frame'] or
                abs(row.get('time_s', -1) - target['time_s']) > 1e-4
                for row, target in zip(existing, trace)):
            raise ValueError('original Core trace differs from crest frame identities')
    else:
        _write_new(core_trace, derived_trace)
    _write_new(attempt / 'crest-derived-trace.jsonl', derived_trace)
    _write_new(attempt / 'video_frames.jsonl', ''.join(json.dumps(row, sort_keys=True) + '\n' for row in mapping))
    _write_new(attempt / 'result.json', json.dumps(result, indent=2, sort_keys=True) + '\n')
    return {'format': 'c104084-crest-saved-analysis-v1',
            'case_id': case_id, 'source_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'observation': observation, 'native_result': 'result.json',
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--assignment')
    parser.add_argument('--case')
    args = parser.parse_args()
    config = json.loads((Path(args.attempt) / 'config.json').read_text())
    assignment = args.assignment or config['assignment_id']
    case = args.case or config['selected_case_id']
    if args.assignment and args.assignment != config['assignment_id']:
        raise ValueError('finalizer assignment differs from selected config')
    if args.case and args.case != config['selected_case_id']:
        raise ValueError('finalizer case differs from selected config')
    report = analyze(args.attempt, assignment_id=assignment, case_id=case)
    _write_new(Path(args.output), json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
