"""Saved-only roadway rest measurement; no legal or physical acceptance verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from source_audit import extract, road_edge_context
from parking_measure import measure as measure_angles

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
REQUIRED = ('native_samples.jsonl', 'video_frames.jsonl', 'trace.jsonl',
            'capture/evidence.jsonl', 'road_geometry.json',
            'road_edge_survey.json', 'activity_context.json', 'body_history.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(attempt, relative):
    path = attempt / relative
    if not path.is_file():
        raise ValueError('Missing required source: ' + relative)
    return path


def rows(attempt, relative):
    return [json.loads(line) for line in source(attempt, relative).read_text().splitlines()]


def decoded_frames(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    check = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, timeout=120)
    if check.returncode or not check.stdout.strip().isdigit():
        raise ValueError('Camera decode failed: ' + path.name)
    return int(check.stdout.strip())


def assess_rest(samples, bodies, geometry, source_hashes):
    """Engineering at-rest event from the final five saved seconds, not a legal cutoff."""
    sources = dict(source_hashes)
    method = 'source-joined final five-second vehicle body, pose and speed assessment'
    if not samples or not bodies or len(samples) != len(bodies) or len(samples) < 100:
        return {'status': 'unverified', 'method': method, 'sources': sources,
                'missing_evidence': ['complete synchronized Native sample/body interval']}
    try:
        tail = list(zip(samples[-100:], bodies[-100:]))
        if any(sample['native_frame'] != body['native_frame'] or
               abs(sample['time_s'] - body['time_s']) > .001 for sample, body in tail):
            raise ValueError('Native body and pose identity join differs')
        centers = [sample['ego_center_xy_m'] for sample, _ in tail]
        speeds = [float(sample['ego_speed_mps']) for sample, _ in tail]
        vertices = [body['body_vertices_m'] for _, body in tail]
        edge_x = float(geometry['edge_x_m'])
        complete = all(0 < vertex[0] < edge_x for body in vertices for vertex in body)
        drift = max(math.dist(centers[0], center) for center in centers)
        maximum_speed = max(speeds)
        met = complete and drift <= .15 and maximum_speed <= .15
        return {'status': 'met' if met else 'not_met', 'method': method,
                'sources': sources, 'intervals': [{'first_frame': tail[0][0]['native_frame'],
                    'last_frame': tail[-1][0]['native_frame']}],
                'details': {'all_body_vertices_inside_roadway': complete,
                    'maximum_center_drift_m': drift, 'maximum_speed_mps': maximum_speed,
                    'engineering_position_tolerance_m': .15,
                    'engineering_speed_tolerance_mps': .15,
                    'not_a_legal_threshold': True}}
    except (ValueError, TypeError, KeyError, IndexError) as error:
        return {'status': 'unverified', 'method': method, 'sources': sources,
                'missing_evidence': [str(error)]}


def measure_roadway_rest_geometry(attempt, config, joined):
    observations = joined['observations']
    return {'value': {'final_edge_angle_deg': observations[-1]['edge_parallel_angle_deg'],
        'final_lawful_heading_angle_deg': observations[-1]['lawful_traffic_heading_angle_deg'],
        'final_speed_mps': observations[-1]['speed_mps'],
        'samples': len(observations), 'no_legal_angle_cutoff': True},
        'method': 'measure_roadway_rest_geometry',
        'sources': {name: sha(attempt/name) for name in
            ('native_samples.jsonl', 'video_frames.jsonl', 'road_geometry.json',
             'road_edge_survey.json')}}


def measure_activity_source_context(attempt, config, joined):
    activity = json.loads(source(attempt, 'activity_context.json').read_text())
    samples = rows(attempt, 'native_samples.jsonl')
    count = sum(row.get('passenger_actor_id') is not None for row in samples)
    return {'value': {'requested_activity': activity['activity_requested'],
        'passenger_body_samples': count,
        'actual_activity_review_required': True},
        'method': 'measure_activity_source_context',
        'sources': {name: sha(attempt/name) for name in
            ('native_samples.jsonl', 'activity_context.json', 'body_history.jsonl')}}


def measure_chapter_exception_context(attempt, config, joined):
    survey = json.loads(source(attempt, 'road_edge_survey.json').read_text())
    return {'value': {'status': survey['chapter_exception_status'],
        'source_refs': survey['chapter_exception_source_refs'],
        'independent_applicability_review_required': True},
        'method': 'measure_chapter_exception_context',
        'sources': {name: sha(attempt/name) for name in
            ('road_edge_survey.json', 'activity_context.json')}}


def derive_channels(attempt, description, samples, frames, bodies, measured, survey, geometry):
    folder = attempt / 'channels'
    folder.mkdir(exist_ok=True)
    context = {'road_edge_survey': survey, 'activity_context':
        json.loads((attempt/'activity_context.json').read_text())}
    (folder/'context.json').write_text(json.dumps(context, indent=2, allow_nan=False)+'\n')
    for channel in description['channels']:
        name = channel['name']
        values = []
        for row, frame, body, observation in zip(samples, frames, bodies, measured['observations']):
            by_name = {
                'native_pose_extract': row,
                'road_edge_tangent': geometry['edge_tangent_xy'],
                'lawful_traffic_direction': geometry['lawful_traffic_direction_xy'],
                'edge_parallel_angle_deg': observation['edge_parallel_angle_deg'],
                'lawful_traffic_heading_angle_deg': observation['lawful_traffic_heading_angle_deg'],
                'kin.heading': row['ego_front_yaw_deg'],
                'kin.speed': row['ego_speed_mps'],
                'drv.standing_or_parked': {'requested': row['requested_activity'],
                    'passenger_actor_id': row.get('passenger_actor_id'),
                    'actual_activity_review_required': True},
                'st.roadway': {'native_road_id': row.get('native_road_id'),
                    'native_lane_id': row.get('native_lane_id'),
                    'roadway_class': geometry['roadway_class']},
                'st.road_edge': {'source_id': geometry['roadway_boundary_source_id'],
                    'edge_x_m': geometry['edge_x_m']},
                'st.lane_direction': geometry['lawful_traffic_direction_xy'],
                'rel.occupies': {'center_xy_m': row['ego_center_xy_m'],
                    'body_vertices_m': body['body_vertices_m'],
                    'passenger_body_vertices_m': body.get('passenger_body_vertices_m')},
                'st.parking_space': {'chapter_exception_status': survey['chapter_exception_status'],
                    'parking_permission_source_id': survey['parking_permission_source_id']},
            }
            if name not in by_name:
                raise ValueError('Unsupported saved channel: ' + name)
            values.append(json.dumps({'time_s': frame['time_s'],
                                      'value': by_name[name]}, allow_nan=False))
        (folder/(name+'.jsonl')).write_text('\n'.join(values)+'\n')


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior finalization; use a fresh attempt')
    for relative in REQUIRED:
        source(attempt, relative)
    config = json.loads(source(attempt, 'config.json').read_text())
    if config['duration_frames'] != 600 or config['rate_hz'] != 20:
        raise ValueError('Exact synchronized window changed')
    samples, frames = rows(attempt, 'native_samples.jsonl'), rows(attempt, 'video_frames.jsonl')
    traces, evidence = rows(attempt, 'trace.jsonl'), rows(attempt, 'capture/evidence.jsonl')
    bodies = rows(attempt, 'body_history.jsonl')
    if any(len(items) != 600 for items in (samples, frames, traces, evidence, bodies)):
        raise ValueError('Original source frame count differs')
    for index, (sample, frame, trace, item, body) in enumerate(zip(samples, frames, traces, evidence, bodies)):
        native = sample['native_frame']
        if frame['video_frame'] != index or any(n != native for n in (
                frame['native_frame'], trace['frame'], item['original_frame'], body['native_frame'])):
            raise ValueError('Original source/frame join differs')
        if any(abs(float(t)-sample['time_s']) > .001 for t in (
                frame['time_s'], trace['time_s'], item['recording_time_s'], body['time_s'])):
            raise ValueError('Original source/time join differs')
    fixture = (attempt/'fixture-marker.json').is_file()
    if fixture:
        marker = json.loads(source(attempt, 'fixture-marker.json').read_text())
        if marker.get('format') != 'synthetic_cpu_fixture':
            raise ValueError('Invalid diagnostic fixture marker')
    pose = extract(config['case_id'], attempt/'native_samples.jsonl',
        attempt/'video_frames.jsonl', attempt/'road_geometry.json',
        attempt/'road_edge_survey.json', allow_fixture=fixture)
    context = road_edge_context(attempt/'road_geometry.json', allow_fixture=fixture)
    measured = measure_angles(pose, context)
    geometry = json.loads((attempt/'road_geometry.json').read_text())
    survey = json.loads((attempt/'road_edge_survey.json').read_text())
    video_counts = {name+'.mkv': decoded_frames(attempt/(name+'.mkv')) for name in CAMERAS}
    if any(count != 600 for count in video_counts.values()):
        raise ValueError('Four-camera 600-frame source incomplete')
    description = config['recording_description']
    derive_channels(attempt, description, samples, frames, bodies, measured, survey, geometry)
    refs = [{'name': c['name'], 'unit': c['unit'],
             'reference': 'channels/'+c['name']+'.jsonl'} for c in description['channels']]
    refs += [{'name': c['name'], 'unit': c['unit'],
              'reference': 'channels/context.json'} for c in description['context_inputs']]
    final = measured['observations'][-1]
    rest_check = assess_rest(samples, bodies, geometry,
        {name: sha(attempt/name) for name in
            ('native_samples.jsonl', 'body_history.jsonl', 'road_geometry.json', 'video_frames.jsonl')})
    target = {'target': 'sampled resting orientation relative to roadway edge',
        'requested': config['rest_pose_requested'],
        'measured': {'edge_angle_deg': final['edge_parallel_angle_deg'],
                     'lawful_heading_angle_deg': final['lawful_traffic_heading_angle_deg']},
        'method': 'saved original pose and independently sourced road-edge projection',
        'tolerance': None, 'matched': False, 'physical_cause_confirmed': False,
        'cause_evidence': ['native_samples.jsonl', 'road_geometry.json']}
    result = {'case_id': config['case_id'],
        'measured_values': {'final_edge_angle_deg': final['edge_parallel_angle_deg'],
            'final_lawful_heading_angle_deg': final['lawful_traffic_heading_angle_deg'],
            'final_speed_mps': final['speed_mps']},
        'target_checks': [target], 'setup_confirmed': False,
        'behavior_attempted': not fixture, 'maneuver_completed': rest_check['status'] == 'met',
        'termination_reason': 'full saved source window analyzed',
        'physical_failure_flags': ['actual_activity_and_chapter_exception_review_required']+
            (['synthetic_fixture_not_physical'] if fixture else []),
        'trace_reference': 'trace.jsonl', 'video_references': list(video_counts),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description, 'recording_evidence': refs,
        'realized_observables': {'maximum_rest_speed_mps': {
            'value': rest_check['details']['maximum_speed_mps'], 'unit': 'm/s',
            'method': rest_check['method'], 'time_window': 'final five saved seconds',
            'statistic': 'maximum', 'reference': 'native_samples.jsonl'}}
            if rest_check['status'] == 'met' else {},
        'physical_checks': {'maneuver': rest_check},
        'provenance_kind': 'synthetic_fixture' if fixture else 'native',
        'diagnostic_fixture': fixture,
        'accepted': False, 'legal_verdict_claimed': False,
        'physical_acceptance_claimed': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    report = {'format': 'worker-roadside-saved-analysis',
        'case_id': config['case_id'], 'measurements': {
            'roadway_rest_geometry': measure_roadway_rest_geometry(attempt, config, measured),
            'activity_source_context': measure_activity_source_context(attempt, config, measured),
            'chapter_exception_context': measure_chapter_exception_context(attempt, config, measured)},
        'source_hashes': {relative: sha(attempt/relative) for relative in REQUIRED},
        'four_camera_frames': video_counts,
        'scope': 'saved source diagnostic; original physical and legal review required'}
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
