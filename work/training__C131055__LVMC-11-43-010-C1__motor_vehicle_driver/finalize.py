"""Fail-closed saved-source lane and exit analysis; no legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from measure_roundabout_lane import CAMERAS, FRAMES, measure
from roundabout_scene import LANES, intent

ASSIGNMENT = 'training__C131055__LVMC-11-43-010-C1__motor_vehicle_driver'
SOURCES = ('native-raw-actors.jsonl', 'control-intent.jsonl',
           'video_frames.jsonl', 'trace.jsonl', 'roundabout-map-readback.json',
           'road.xodr', 'config.json')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def analyze(attempt):
    attempt = Path(attempt)
    for name in (*SOURCES, *(camera + '.mkv' for camera in sorted(CAMERAS))):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    case_id = config.get('selected_case_id')
    if (case_id not in {ASSIGNMENT + '__' + name for name in LANES} or
            config.get('case_id', case_id) != case_id or
            config.get('law_id') != 'LVMC-11-43-010-C1' or
            config.get('cell_id') != 'C131055' or
            config.get('actor') != 'motor_vehicle_driver' or
            (config.get('rate_hz'), config.get('duration_s'), config.get('frames')) != (20, 30, 600)):
        raise ValueError('Exact saved case identity or profile differs')
    case = case_id[len(ASSIGNMENT) + 2:]
    if config.get('case', {}).get('case_id') != case_id:
        raise ValueError('Sealed source exit intention missing')
    raw, controls, frames, trace = (read_rows(attempt / name) for name in SOURCES[:4])
    if any(len(stream) != FRAMES for stream in (raw, controls, frames, trace)):
        raise ValueError('Incomplete 600-frame original source join')
    readback = json.loads((attempt / 'roundabout-map-readback.json').read_text())
    if (readback.get('source_kind') != 'native_map_readback' or
            {row.get('road_id') for row in readback.get('samples', [])} != set(range(1, 8))):
        raise ValueError('Original Native seven-road map readback missing')
    root = ET.fromstring((attempt / 'road.xodr').read_text())
    roads = {int(road.get('id')): road for road in root.findall('road')}
    if set(roads) != set(range(1, 8)) or any(
            {lane.get('id') for lane in roads[road_id].findall('lanes/laneSection/right/lane')}
            != {'-1', '-2'} for road_id in range(1, 5)):
        raise ValueError('Original Native two-lane ring topology missing')
    if any(roads[road_id].find('planView/geometry/arc') is None for road_id in range(1, 5)):
        raise ValueError('Original Native ring arcs missing')
    curvature = [float(roads[road_id].find('planView/geometry/arc').get('curvature'))
                 for road_id in range(1, 5)]
    widths = [[float(lane.find('width').get('a')) for lane in
               roads[road_id].findall('lanes/laneSection/right/lane')]
              for road_id in range(1, 5)]
    if (any(not math.isfinite(k) or k <= 0 or abs(k - curvature[0]) > 1e-6
            for k in curvature) or
            any(len(row) != 2 or any(not math.isfinite(w) or w <= 0 for w in row)
                or row != widths[0] for row in widths)):
        raise ValueError('Original Native lane radius or widths differ')
    reference_radius = 1 / curvature[0]
    lane_width = widths[0][0]
    if abs(widths[0][1] - lane_width) > 1e-6:
        raise ValueError('Original Native ring lane widths differ')
    hashes = {name: digest(attempt / name) for name in SOURCES}
    rows = []
    angle = None
    prior_angle = None
    previous_time = None
    previous_native = None
    body_ids = set()
    for i, (actor_row, command, frame, movement) in enumerate(zip(raw, controls, frames, trace)):
        native = frame.get('native_frame')
        elapsed = frame.get('time_s')
        if (frame.get('video_frame') != i or type(native) is not int or
                type(elapsed) not in (int, float) or not math.isfinite(elapsed) or
                (previous_native is not None and native <= previous_native) or
                (previous_time is not None and elapsed <= previous_time)):
            raise ValueError('Original frame/time map missing or unordered')
        previous_native, previous_time = native, elapsed
        if abs(elapsed - i / 20) > 1e-4:
            raise ValueError('Original Native capture cadence differs')
        if (actor_row.get('video_frame') != i or command.get('video_frame') != i or
                actor_row.get('native_frame') != native or command.get('native_frame') != native or
                movement.get('frame') != native or
                any(abs(stream.get('time_s', -999) - elapsed) > 1e-4
                    for stream in (actor_row, command, movement))):
            raise ValueError('Original actor/control/trace frame join differs')
        mapped = frame.get('camera_native_frames')
        if not isinstance(mapped, dict) or set(mapped) != CAMERAS or any(
                mapped[name] != native for name in CAMERAS):
            raise ValueError('Four-camera original frame join differs')
        if actor_row.get('case_id') != case_id:
            raise ValueError('Original actor case differs')
        actors = actor_row.get('actors')
        if not isinstance(actors, list) or len(actors) != 1 or actors[0].get('role') != 'ego':
            raise ValueError('Original subject actor source missing')
        ego = actors[0]
        body_ids.add(ego.get('actor_id'))
        if (len(body_ids) != 1 or ego.get('blueprint_id') is None or
                any(type(ego.get(key)) not in (int, float) or not math.isfinite(ego[key])
                    for key in ('x_m', 'y_m', 'yaw_deg', 'speed_mps',
                                'bbox_half_length_m', 'bbox_half_width_m')) or
                ego['bbox_half_length_m'] <= 0 or ego['bbox_half_width_m'] <= 0):
            raise ValueError('Original subject body or motion source missing')
        road_id = ego.get('road_id')
        if road_id == 5:
            phase = 'entry'
        elif road_id in (1, 2, 3, 4):
            phase = 'circulation'
        elif road_id in (6, 7):
            phase = 'exit'
        else:
            raise ValueError('Original subject roadway phase unobserved')
        if command.get('requested_phase') != phase:
            raise ValueError('Requested and observed roadway phase differ')
        if command.get('exit_intent') != intent(case):
            raise ValueError('Original control intent differs from selected exit')
        x, y = ego['x_m'], ego['y_m']
        unwrapped = None
        if phase == 'circulation':
            theta = math.atan2(y, x)
            if prior_angle is None:
                angle = theta
            else:
                angle += math.atan2(math.sin(theta - prior_angle), math.cos(theta - prior_angle))
            prior_angle = theta
            unwrapped = angle
        rows.append({'video_frame': i, 'native_frame': native, 'time_s': i / 20,
                     'source_cameras': {name: i for name in CAMERAS}, 'phase': phase,
                     'ego_x_m': x, 'ego_y_m': y, 'ego_heading_deg': ego['yaw_deg'],
                     'unwrapped_angle_rad': unwrapped})
    if case.startswith('u_turn') and any(row['phase'] == 'exit' and
                                          raw[i]['actors'][0]['road_id'] != 7
                                          for i, row in enumerate(rows)):
        raise ValueError('U-turn original exit road differs')
    if not case.startswith('u_turn') and any(row['phase'] == 'exit' and
                                              raw[i]['actors'][0]['road_id'] != 6
                                              for i, row in enumerate(rows)):
        raise ValueError('Left-turn original exit road differs')
    context = {'source_kind': 'original_native_roundabout_readback',
               'roundabout_topology_verified': True, 'exit_intention_sourced': True,
               'exit_intent': intent(case),
               'left_lane_center_radius_m': reference_radius + lane_width / 2,
               'right_lane_center_radius_m': reference_radius + 1.5 * lane_width,
               'lane_half_width_m': lane_width / 2 - 0.5,
               'native_map_sha256': hashes['road.xodr'],
               'roundabout_lanes_sha256': hashes['roundabout-map-readback.json'],
               'entry_exit_links_sha256': hashes['road.xodr'],
               'ego_body_sha256': hashes['native-raw-actors.jsonl'],
               'ego_motion_sha256': hashes['trace.jsonl'],
               'exit_intention_sha256': hashes['config.json'],
               'camera_manifest_sha256': hashes['video_frames.jsonl']}
    measured = measure(context, rows)
    return {'case_id': case_id, 'source_sha256': hashes,
            'video_sha256': {name + '.mkv': digest(attempt / (name + '.mkv'))
                             for name in CAMERAS}, 'measurement': measured,
            'rows': rows, 'recording_description': config['recording_description']}


def measure_roundabout_context(analysis):
    hashes = analysis['source_sha256']
    return {'value': {'ring_road_ids': [1, 2, 3, 4],
                      'entry_road_id': 5, 'left_turn_exit_road_id': 6,
                      'u_turn_exit_road_id': 7,
                      'body_and_pixel_review_complete': False},
            'method': 'measure_roundabout_context',
            'sources': {name: hashes[name] for name in
                        ('road.xodr', 'roundabout-map-readback.json')}}


def measure_exit_intent(analysis):
    hashes = analysis['source_sha256']
    measurement = analysis['measurement']
    return {'value': {'exit_intent': measurement['exit_intent'],
                      'angular_sweep_rad': measurement['angular_sweep_rad'],
                      'exit_heading_deg': measurement['exit_heading_deg'],
                      'legal_result': None},
            'method': 'measure_exit_intent',
            'sources': {name: hashes[name] for name in
                        ('control-intent.jsonl',
                         'native-raw-actors.jsonl', 'video_frames.jsonl')}}


def measure_lane_use(analysis):
    hashes = analysis['source_sha256']
    measurement = analysis['measurement']
    return {'value': {'left_lane_frame_count': measurement['left_lane_frame_count'],
                      'right_lane_frame_count': measurement['right_lane_frame_count'],
                      'lane_change_count': measurement['lane_change_count'],
                      'legal_result': None},
            'method': 'measure_lane_use',
            'sources': {name: hashes[name] for name in
                        ('road.xodr', 'roundabout-map-readback.json',
                         'native-raw-actors.jsonl', 'video_frames.jsonl')}}


def finalize(attempt, output):
    from worker_exchange.native_output import physical_result, write_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Retain prior saved analysis; choose a fresh attempt')
    analysis = analyze(attempt)
    channels = attempt / 'channels'
    channels.mkdir()
    references = []
    for name in ('roundabout_lane_occupancy', 'entry_exit_intent', 'ego_pose'):
        reference = 'channels/' + name + '.jsonl'
        with (attempt / reference).open('x') as stream:
            for row in analysis['rows']:
                stream.write(json.dumps({'time_s': row['time_s'], 'value': row},
                                        allow_nan=False) + '\n')
        references.append({'name': name,
                           'unit': 'm,deg' if name == 'ego_pose' else 'structured',
                           'reference': reference})
    context_reference = 'channels/context_roundabout_topology.json'
    (attempt / context_reference).write_text(json.dumps({
        'context_roundabout_topology': {
            'source_sha256': {name: analysis['source_sha256'][name] for name in
                              ('road.xodr', 'roundabout-map-readback.json')},
            'ring_road_ids': [1, 2, 3, 4], 'entry_road_id': 5,
            'exit_road_ids': [6, 7], 'physical_review_complete': False}},
        indent=2) + '\n')
    references.append({'name': 'context_roundabout_topology',
                       'unit': 'structured', 'reference': context_reference})
    for name, expected in analysis['source_sha256'].items():
        if digest(attempt / name) != expected:
            raise ValueError('Original source changed during analysis: ' + name)
    measurement = analysis['measurement']
    result = {'case_id': analysis['case_id'], 'measured_values': {'roundabout_lane': measurement},
              'target_checks': [{'target': 'source-observed ring lane and intended exit',
                                 'requested': analysis['case_id'], 'measured': measurement,
                                 'method': 'original map/actor/control/frame joined lane meter',
                                 'tolerance': None, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(analysis['source_sha256'])}],
              'setup_confirmed': False, 'behavior_attempted': True,
              'maneuver_completed': False,
              'termination_reason': 'Saved lane and exit measured; physical and legal review remain',
              'physical_failure_flags': ['full_body_pixels_and_lane_boundary_unreviewed'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in sorted(CAMERAS)],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': analysis['recording_description'],
              'recording_evidence': references,
              'realized_observables': {'left_lane_frame_count': {
                  'value': measurement['left_lane_frame_count'],
                  'unit': 'count', 'method': 'source-bound 600-frame lane meter',
                  'time_window': '600 original Native frames', 'statistic': 'all',
                  'reference': 'channels/roundabout_lane_occupancy.jsonl'}},
              'accepted': False, 'legal_verdict_claimed': False}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    report = {'format': 'c131055-saved-lane-analysis-v1',
              'case_id': analysis['case_id'],
              'source_sha256': analysis['source_sha256'],
              'video_sha256': analysis['video_sha256'],
              'measurements': {'roundabout_context': measure_roundabout_context(analysis),
                               'exit_intent': measure_exit_intent(analysis),
                               'lane_use': measure_lane_use(analysis)},
              'measurement': measurement,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
              'physical_checks': result['physical_checks'],
              'provenance_kind': result['provenance_kind'],
              'diagnostic_fixture': result['diagnostic_fixture']}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
