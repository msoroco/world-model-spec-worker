"""Retain exact source observations for crossroads entry without a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

CASE = '__CASE__'
SOURCES = ('actor-history.json', 'road-context.json', 'video_frames.jsonl',
           'trace.jsonl', 'crossing_history.jsonl', 'capture/evidence.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def measure_entry(attempt):
    attempt = Path(attempt)
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    context = json.loads((attempt / 'road-context.json').read_text())
    raw = json.loads((attempt / 'actor-history.json').read_text())
    diagnostic = context.get('source_kind') == 'synthetic_cpu_diagnostic'
    if (context.get('source_kind') not in ('synthetic_cpu_diagnostic', 'original_native') or
            context.get('official_device_governance_verified') is not False or
            raw.get('case_id') != CASE or raw.get('synthetic') is not diagnostic):
        raise ValueError('Source context or provenance differs')
    rows = raw['rows']
    mapping = records(attempt / 'video_frames.jsonl')
    trace = records(attempt / 'trace.jsonl')
    crossing = records(attempt / 'crossing_history.jsonl')
    evidence = records(attempt / 'capture/evidence.jsonl')
    if any(len(stream) != 600 for stream in (rows, mapping, trace, crossing, evidence)):
        raise ValueError('Expected 600 source-joined frames')
    ego_entry = other_entry = ego_exit = other_exit = None
    for frame, (row, video, pose, body_row, observed) in enumerate(zip(rows, mapping, trace, crossing, evidence)):
        time = frame / 20
        native = row.get('native_frame', frame)
        if (row['frame'] != frame or video['video_frame'] != frame or
                video['native_frame'] != native or pose['frame'] != frame or
                observed['original_frame'] != native or
                body_row.get('frame') != frame or
                body_row.get('ego_vertices_m') != row['ego']['body_xyz_m'] or
                body_row.get('other_vertices_m') != row['other']['body_xyz_m'] or
                any(abs(item['time_s'] - time) > .01 for item in (row, video, pose)) or
                abs(observed['recording_time_s'] - row['time_s']) > 1e-6):
            raise ValueError('Original actor/video/trace/evidence join differs')
        ego, other = row['ego']['body_xyz_m'], row['other']['body_xyz_m']
        if ego_entry is None and max(point[0] for point in ego) >= -20:
            ego_entry = time
        if other_entry is None and max(point[1] for point in other) >= -20:
            other_entry = time
        if ego_exit is None and min(point[0] for point in ego) >= 20:
            ego_exit = time
        if other_exit is None and min(point[1] for point in other) >= 20:
            other_exit = time
    if any(value is None for value in (ego_entry, other_entry, ego_exit, other_exit)):
        raise ValueError('Both recorded bodies must traverse the intersection')
    metric = {'frames': 600, 'ego_front_entry_s': ego_entry,
              'other_front_entry_s': other_entry,
              'ego_rear_exit_s': ego_exit, 'other_rear_exit_s': other_exit,
              'ego_minus_other_front_entry_s': round(ego_entry - other_entry, 6),
              'priority_entered_first_measured': other_entry < ego_entry,
              'priority_present_at_ego_entry': other_exit > ego_entry,
              'ego_yield_legally_determined': False,
              'official_device_governance_verified': False,
              'right_of_way_legally_determined': False}
    return metric, rows, trace, context


def channel_value(name, row, pose, context, metric):
    ego, other = row['ego'], row['other']
    ego_body, other_body = ego['body_xyz_m'], other['body_xyz_m']
    ego_front = max(point[0] for point in ego_body)
    other_front = max(point[1] for point in other_body)
    if name == 'ego_body':
        return ego_body
    if name == 'other_body':
        return other_body
    if name == 'st.intersection':
        return {'authored_connector_road_ids': [251, 254],
                'native_junction_verified': False}
    if name == 'st.lane_enters':
        return {'ego_authored_highway_roads': context['ego_highway_roads'],
                'other_authored_highway_roads': context['other_highway_roads'],
                'native_lane_projection_verified': False}
    if name == 'drv.entering_intersection':
        return {'ego_front_at_boundary': ego_front >= -20,
                'other_front_at_boundary': other_front >= -20,
                'ego_front_x_m': ego_front, 'other_front_y_m': other_front}
    if name == 'drv.arrival_order':
        return {'ego_front_entry_s': metric['ego_front_entry_s'],
                'other_front_entry_s': metric['other_front_entry_s'],
                'ego_minus_other_entry_s': metric['ego_minus_other_front_entry_s'],
                'priority_entered_first_measured': metric['priority_entered_first_measured']}
    if name == 'rel.bearing':
        return {'other_minus_ego_xyz_m': [b - a for a, b in zip(
                    ego['center_xyz_m'], other['center_xyz_m'])],
                'ego_heading_deg': pose['heading_deg'],
                'native_approach_bearing_verified': False}
    if name == 'drv.yields_to':
        return {'ego_observed_speed_mps': ego['speed_mps'],
                'other_observed_speed_mps': other['speed_mps'],
                'other_front_at_boundary': other_front >= -20,
                'right_of_way_verdict_unknown': True}
    if name == 'drv.approaching':
        return {'ego_x_m': ego['center_xyz_m'][0],
                'approach_before_boundary': ego_front < -20}
    if name == 'drv.in_intersection':
        return {'other_body_at_ego_entry': metric['priority_present_at_ego_entry'],
                'other_rear_exit_s': metric['other_rear_exit_s']}
    if name == 'dev.traffic_signal':
        return {'authored_signal_count': row['authored_official_device_count'],
                'official_device_governance_verified': False}
    if name in ('dev.stop_sign', 'dev.yield_sign'):
        return {'authored_count': 0, 'original_governance_verified': False}
    if name == 'drv.turning':
        return {'ego_observed_heading_deg': pose['heading_deg'],
                'turn_intent_verified': False}
    if name == 'rel.oncoming':
        return {'opposite_approaches_verified': False,
                'ego_heading_deg': pose['heading_deg'],
                'other_heading_deg': other['yaw_deg'] if 'yaw_deg' in other else 90}
    raise ValueError('Unknown capture channel: ' + name)


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior analysis; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    if config['case_id'] != CASE or construction['case_id'] != CASE:
        raise ValueError('Exact diagnostic case differs')
    metric, rows, trace, context = measure_entry(attempt)
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row, pose in zip(rows, trace):
                value = channel_value(name, row, pose, context, metric)
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    outputs = ('priority_entry', 'yield_action', 'device_exclusion',
               'opposite_turn_exclusion')
    report = {'format': 'worker-analysis-report', 'case_id': CASE,
              'measurements': {name: {'method': 'measure_entry', 'value': metric,
                  'sources': {source: sha(attempt / source) for source in SOURCES}}
                  for name in outputs},
              'source_complete': True, 'diagnostic_fixture': diagnostic,
              'physical_or_legal_acceptance': False}
    result = {'case_id': CASE, 'measured_values': metric,
              'target_checks': [{'target': 'body-derived entry gap observed',
                                 'requested': True, 'measured': True,
                                 'method': 'measure_entry', 'tolerance': 0,
                                 'matched': True, 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': not diagnostic, 'behavior_attempted': not diagnostic,
              'maneuver_completed': False,
              'termination_reason': '600-frame source-bound entry observation; statutory context pending',
              'physical_failure_flags': ['Original Native entry and statutory governance unverified'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if diagnostic else 'native', 'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
