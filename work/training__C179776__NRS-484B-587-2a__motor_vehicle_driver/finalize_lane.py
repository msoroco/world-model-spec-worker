"""Saved original-source lane-footprint analysis; no legal verdict."""

import argparse
import hashlib
import json
import math
from pathlib import Path


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('designation-source.json', 'road.xodr', 'native-road-readback.json',
           'native-raw-actors.jsonl', 'control-intent.jsonl', 'trace.jsonl',
           'video_frames.jsonl')


def digest(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def analyze(attempt):
    attempt = Path(attempt)
    hashes = {name: digest(attempt / name) for name in SOURCES}
    videos = {name + '.mkv': digest(attempt / (name + '.mkv')) for name in CAMERAS}
    designation = json.loads((attempt / 'designation-source.json').read_text())
    road = json.loads((attempt / 'native-road-readback.json').read_text())
    if not all(designation.get(key) for key in ('public_authority_source',
                                                'highway_boundary_source',
                                                'access_restriction_source',
                                                'vehicle_class_source',
                                                'emergency_event_source',
                                                'sign_source')):
        raise ValueError('Original controlled-access designation source missing')
    if road.get('source_kind') != 'original_native_map_readback' or len(road.get('lanes', [])) != 9:
        raise ValueError('Original Native lane/shoulder map readback missing')
    if road.get('designation_source_sha256') != hashes['designation-source.json']:
        raise ValueError('Original designation source hash differs')
    if {(row.get('road_id'), row.get('lane_id')) for row in road['lanes']} != {(1, 1), (1, 2), (1, -1)}:
        raise ValueError('Original Native lane inventory differs')
    raw, controls, trace, frames = (
        load_lines(attempt / name) for name in
        ('native-raw-actors.jsonl', 'control-intent.jsonl',
         'trace.jsonl', 'video_frames.jsonl'))
    if not all(len(rows) == 600 for rows in (raw, controls, trace, frames)):
        raise ValueError('Expected 600 original-source frames')
    case_id = raw[0].get('case_id')
    if not case_id or not case_id.startswith('training__C179776__NRS-484B-587-2a__motor_vehicle_driver__'):
        raise ValueError('Frozen exact case source differs')
    outside = shoulder = 0
    measured = []
    actor_ids = set()
    for i, (actor_row, command, movement, frame) in enumerate(zip(raw, controls, trace, frames)):
        native = frame.get('native_frame')
        elapsed = frame.get('time_s')
        if (frame.get('video_frame') != i or type(native) is not int or
                type(elapsed) not in (int, float) or
                abs(elapsed - i / 20) > 1e-4 or
                frame.get('camera_native_frames') != {name: native for name in CAMERAS}):
            raise ValueError('Original camera frame/time map differs')
        if (actor_row.get('video_frame') != i or command.get('video_frame') != i or
                actor_row.get('native_frame') != native or command.get('native_frame') != native or
                movement.get('frame') != native or actor_row.get('case_id') != case_id or
                any(abs(row.get('time_s', -999) - elapsed) > 1e-4
                    for row in (actor_row, command, movement))):
            raise ValueError('Original actor/control/trace frame join differs')
        actors = actor_row.get('actors')
        if not isinstance(actors, list) or len(actors) != 1 or actors[0].get('role') != 'ego':
            raise ValueError('Original subject identity missing')
        ego = actors[0]
        actor_ids.add(ego.get('actor_id'))
        if len(actor_ids) != 1 or ego.get('blueprint_id') is None:
            raise ValueError('Original subject continuity missing')
        for key in ('x_m', 'y_m', 'yaw_deg', 'bbox_half_length_m',
                    'bbox_half_width_m', 'speed_mps'):
            if type(ego.get(key)) not in (int, float) or not math.isfinite(ego[key]):
                raise ValueError('Original subject body source missing')
        if ego['bbox_half_length_m'] <= 0 or ego['bbox_half_width_m'] <= 0:
            raise ValueError('Original subject body extent missing')
        yaw = math.radians(ego['yaw_deg'])
        half_y = (abs(math.sin(yaw)) * ego['bbox_half_length_m'] +
                  abs(math.cos(yaw)) * ego['bbox_half_width_m'])
        low, high = ego['y_m'] - half_y, ego['y_m'] + half_y
        is_outside = low < -4.0 or high > 4.0
        is_shoulder = low >= 4.0 and high <= 6.0
        outside += is_outside
        shoulder += is_shoulder
        measured.append({'time_s': elapsed, 'native_frame': native,
                         'footprint_y_min_m': low, 'footprint_y_max_m': high,
                         'outside_marked_lane': is_outside,
                         'fully_paved_shoulder': is_shoulder,
                         'original_body_source': 'native-raw-actors.jsonl',
                         'original_map_source': 'native-road-readback.json'})
    return {'case_id': case_id, 'source_sha256': hashes, 'video_sha256': videos,
            'frame_count': 600, 'outside_marked_lane_frames': outside,
            'fully_paved_shoulder_frames': shoulder, 'rows': measured,
            'emergency_required': None, 'subsection_3_authorization': None,
            'signed_class_shoulder_condition': None,
            'physical_original_verified': False, 'legal_verdict': None}


def measure_lane_footprint(analysis):
    names = ('designation-source.json', 'road.xodr',
             'native-road-readback.json', 'native-raw-actors.jsonl',
             'video_frames.jsonl')
    return {'value': {'outside_marked_lane_frames': analysis['outside_marked_lane_frames'],
                      'fully_paved_shoulder_frames': analysis['fully_paved_shoulder_frames'],
                      'emergency_required': analysis['emergency_required'],
                      'subsection_3_authorization': analysis['subsection_3_authorization'],
                      'signed_class_shoulder_condition': analysis['signed_class_shoulder_condition'],
                      'legal_verdict': None},
            'method': 'measure_lane_footprint',
            'sources': {name: analysis['source_sha256'][name] for name in names}}


def finalize(attempt, output):
    from worker_exchange.native_output import physical_result, write_result

    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Saved original analysis already exists')
    analysis = analyze(attempt)
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=True)
    channel = channels / 'lane-footprint.jsonl'
    channel.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': row},
                                          sort_keys=True) + '\n' for row in analysis['rows']))
    for name, expected in analysis['source_sha256'].items():
        if digest(attempt / name) != expected:
            raise ValueError('Original source changed during saved analysis: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    planned_recording = config.get('recording_description')
    if planned_recording:
        designation = json.loads((attempt / 'designation-source.json').read_text())
        road = json.loads((attempt / 'native-road-readback.json').read_text())
        context = attempt / 'context.json'
        if not context.exists():
            context.write_text(json.dumps({'designation_source': designation,
                                           'native_road_readback': road},
                                          sort_keys=True) + '\n')
        stream_values = {item['name']: [] for item in planned_recording['channels']}
        for row in analysis['rows']:
            t = row['time_s']
            lane_id = 2 if row['fully_paved_shoulder'] else 1
            values = {
                'st.controlled_access': {'road_id': 1, 'designation_source': designation['public_authority_source'], 'designation_verified': False},
                'st.lane': {'road_id': 1, 'lane_id': lane_id, 'marked_travel_bounds_y_m': [0, 4]},
                'st.lane_marking': {'lane_edge_y_m': 4, 'pixel_verified': False},
                'rel.occupies': {'footprint_y_min_m': row['footprint_y_min_m'], 'footprint_y_max_m': row['footprint_y_max_m'], 'outside_marked_lane': row['outside_marked_lane']},
                'st.shoulder': {'paved': None, 'bounds_y_m': [4, 6], 'surface_pixel_verified': False},
                'dev.regulatory_sign': {'source': designation['sign_source'], 'shoulder_use_permitted': None, 'pixel_verified': False},
                'ru.emergency_vehicle': {'source': designation['vehicle_class_source'], 'is_emergency_vehicle': None},
                'ru.official_vehicle': {'source': designation['vehicle_class_source'], 'is_official_vehicle': None},
                'ru.transit_bus': {'source': designation['vehicle_class_source'], 'is_transit_bus': None},
                'drv.responding_emergency': {'source': designation['emergency_event_source'], 'emergency_required': None}}
            for name in stream_values:
                stream_values[name].append({'time_s': t, 'value': values[name]})
        for name, rows in stream_values.items():
            (channels / (name + '.jsonl')).write_text(''.join(
                json.dumps(row, sort_keys=True) + '\n' for row in rows))
        recording_evidence = [
            {'name': item['name'], 'unit': item['unit'],
             'reference': 'channels/' + item['name'] + '.jsonl'}
            for item in planned_recording['channels']]
        recording_evidence += [
            {'name': item['name'], 'unit': item['unit'],
             'reference': 'context.json'}
            for item in planned_recording['context_inputs']]
    else:
        planned_recording = {'channels': [
            {'name': 'lane_footprint', 'unit': 'structured',
             'sampling_rate_hz': 20,
             'method': 'original body extent plus Native map lane/shoulder boundaries',
             'time_window': 'all 600 original frames',
             'reference_frame': 'original CARLA road',
             'uncertainty': 'body/map/pixel review pending'}],
             'context_inputs': ['designation-source.json', 'native-road-readback.json'],
             'limitations': ['no original authority or physical acceptance claim']}
        recording_evidence = [{'name': 'lane_footprint', 'unit': 'structured',
                               'reference': 'channels/lane-footprint.jsonl'}]
    result = {'case_id': analysis['case_id'],
              'measured_values': {'outside_marked_lane_frames': analysis['outside_marked_lane_frames'],
                                  'fully_paved_shoulder_frames': analysis['fully_paved_shoulder_frames']},
              'target_checks': [{'target': 'source-observed lane footprint',
                                 'requested': None,
                                 'measured': analysis['outside_marked_lane_frames'],
                                 'method': 'original body, map and frame join',
                                 'tolerance': None, 'matched': None,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(analysis['source_sha256'])}],
              'setup_confirmed': False, 'behavior_attempted': True,
              'maneuver_completed': False,
              'termination_reason': 'Saved footprint measured; physical and legal review pending',
              'physical_failure_flags': ['marking_pixels_and_authority_unreviewed'],
              'trace_reference': 'trace.jsonl',
              'video_references': list(analysis['video_sha256']),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': planned_recording,
              'recording_evidence': recording_evidence,
              'realized_observables': {'outside_marked_lane_frames': {
                  'value': analysis['outside_marked_lane_frames'], 'unit': 'count',
                  'method': 'source-joined full-body footprint',
                  'time_window': 'all 600 original frames', 'statistic': 'count',
                  'reference': 'channels/lane-footprint.jsonl'}},
              'accepted': False, 'legal_verdict_claimed': False}
    write_result(attempt, physical_result(attempt, result))
    report = {key: value for key, value in analysis.items() if key != 'rows'}
    report['format'] = 'c179776-saved-lane-analysis-v1'
    report['measurements'] = {'lane_footprint': measure_lane_footprint(analysis)}
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
