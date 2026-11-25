"""Saved-only original position and map direction analysis; no legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from roundabout_direction import measure

FRAMES = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('native-raw-actors.jsonl', 'control-intent.jsonl', 'video_frames.jsonl',
           'trace.jsonl', 'roundabout-map-readback.json', 'road.xodr')
RING_ROADS = {21, 23}
CHANNELS = ('raw_ego_motion', 'raw_other_motion', 'frame_join', 'st.roundabout',
            'rel.occupies', 'kin.heading', 'kin.position', 'kin.yaw_rate',
            'drv.wrong_way')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def analyze(attempt):
    attempt = Path(attempt)
    for name in (*SOURCES, 'config.json', *(n + '.mkv' for n in CAMERAS)):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    case = config.get('case_id')
    if (case not in ('training__C238396__LVMC-11-43-010-A__motor_vehicle_driver__probe_a',
                     'training__C238396__LVMC-11-43-010-A__motor_vehicle_driver__probe_b') or
            config.get('selected_case_id') != case or config.get('law_id') != 'LVMC-11-43-010-A' or
            config.get('cell_id') != 'C238396' or config.get('rate_hz') != 20 or
            config.get('duration_s') != 30):
        raise ValueError('Exact saved case contract differs')
    actors, controls, frames, trace = (rows(attempt / name) for name in SOURCES[:4])
    if any(len(stream) != FRAMES for stream in (actors, controls, frames, trace)):
        raise ValueError('Incomplete 600-frame original source join')
    map_source = json.loads((attempt / 'roundabout-map-readback.json').read_text())
    roads = {item.get('road_id') for item in map_source.get('samples', [])}
    if map_source.get('source_kind') != 'native_map_readback' or roads != RING_ROADS:
        raise ValueError('Native roundabout map readback missing')
    meter_rows, ego_rows, other_rows = [], [], []
    ids = {}
    for i, (actor, intent, frame, motion) in enumerate(zip(actors, controls, frames, trace)):
        native, t = frame.get('native_frame'), frame.get('time_s')
        if (frame.get('video_frame') != i or not isinstance(native, int) or
                not isinstance(t, (float, int)) or not math.isfinite(t) or
                actor.get('video_frame') != i or intent.get('video_frame') != i or
                actor.get('native_frame') != native or intent.get('native_frame') != native or
                motion.get('frame') != native or
                abs(actor.get('time_s', -100) - t) > 1e-4 or
                abs(intent.get('time_s', -100) - t) > 1e-4 or
                abs(motion.get('time_s', -100) - t) > 1e-4 or
                (i and (native <= frames[i-1]['native_frame'] or t <= frames[i-1]['time_s']))):
            raise ValueError('Original frame/time identity differs')
        if set(frame.get('camera_native_frames', {})) != set(CAMERAS) or any(
                value != native for value in frame['camera_native_frames'].values()):
            raise ValueError('Four-camera original frame join differs')
        by_role = {item.get('role'): item for item in actor.get('actors', [])}
        if actor.get('case_id') != case or set(by_role) != {'ego', 'other'} or len(actor['actors']) != 2:
            raise ValueError('Original participant source missing')
        for role, item in by_role.items():
            if item.get('actor_id') is None or not item.get('blueprint_id'):
                raise ValueError('Original actor identity missing')
            if role in ids and ids[role] != item['actor_id']:
                raise ValueError('Original actor identity changed')
            ids[role] = item['actor_id']
            if any(not isinstance(item.get(key), (float, int)) or not math.isfinite(item[key])
                   for key in ('x_m', 'y_m', 'yaw_deg', 'speed_mps',
                               'bbox_half_length_m', 'bbox_half_width_m')):
                raise ValueError('Original actor motion absent or nonfinite')
        ego, other = by_role['ego'], by_role['other']
        ego_rows.append(ego)
        other_rows.append(other)
        meter_rows.append({'frame': i, 'time_s': t, 'source_kind': 'original_native',
                           'inside_roundabout': ego.get('road_id') in RING_ROADS,
                           'ego_xy_m': [ego['x_m'], ego['y_m']]})
    metric = measure(meter_rows, 'original_native')
    return {'format': 'c238396-saved-direction-meter-v1', 'case_id': case,
            'source_sha256': {n: sha(attempt / n) for n in SOURCES},
            'video_sha256': {n + '.mkv': sha(attempt / (n + '.mkv')) for n in CAMERAS},
            'actor_ids': ids, 'frames': FRAMES, 'direction': metric,
            'ego_rows': ego_rows, 'other_rows': other_rows,
            'physical_completion_claimed': False, 'legal_verdict_claimed': False}


def measure_roundabout_context(measurement):
    return {'value': {'ring_road_ids': [21, 23], 'original_boundary_review_complete': False},
            'method': 'measure_roundabout_context',
            'sources': {n: measurement['source_sha256'][n] for n in
                        ('roundabout-map-readback.json', 'road.xodr')}}


def measure_circulation_direction(measurement):
    return {'value': {'translational_direction':
                      measurement['direction']['translational_direction'],
                      'signed_radial_cross_sum_m2':
                      measurement['direction']['signed_radial_cross_sum_m2'],
                      'legal_result': None}, 'method': 'measure_circulation_direction',
            'sources': {n: measurement['source_sha256'][n] for n in
                        ('native-raw-actors.jsonl', 'video_frames.jsonl')}}


def finalize(attempt, output):
    from worker_exchange.native_output import write_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior saved analysis/result')
    measurement = analyze(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    frames = rows(attempt / 'video_frames.jsonl')
    egos, others = measurement['ego_rows'], measurement['other_rows']
    values = {name: [] for name in CHANNELS}
    for i, (ego, other) in enumerate(zip(egos, others)):
        yaw = ego['yaw_deg']
        before = egos[i-1]['yaw_deg'] if i else yaw
        yaw_rate = math.degrees(math.atan2(math.sin(math.radians(yaw-before)),
                                           math.cos(math.radians(yaw-before)))) * 20
        values['raw_ego_motion'].append(ego)
        values['raw_other_motion'].append(other)
        values['frame_join'].append(frames[i])
        values['st.roundabout'].append({'ring_road_ids': [21, 23],
            'source_map_readback': True, 'boundary_review_complete': False})
        values['rel.occupies'].append({'ego_road_id': ego.get('road_id'),
            'other_road_id': other.get('road_id'),
            'ego_ring_projection': ego.get('road_id') in RING_ROADS})
        values['kin.heading'].append({'yaw_deg': yaw, 'direction_from_heading': None})
        values['kin.position'].append({'x_m': ego['x_m'], 'y_m': ego['y_m'],
            'roundabout_center_xy_m': [22, 0]})
        values['kin.yaw_rate'].append({'yaw_rate_deg_s': yaw_rate,
            'corroborating_only': True})
        values['drv.wrong_way'].append({'translational_direction':
            measurement['direction']['translational_direction'],
            'original_boundary_review_complete': False})
    channels = attempt / 'channels'
    if channels.exists():
        raise ValueError('Derived channels already exist')
    channels.mkdir()
    for name, series in values.items():
        with (channels / (name + '.jsonl')).open('x') as stream:
            for frame, value in zip(frames, series):
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': value}) + '\n')
    (channels / 'roundabout_map.json').write_text(json.dumps({'roundabout_map': {
        'source': 'roundabout-map-readback.json',
        'source_sha256': measurement['source_sha256']['roundabout-map-readback.json']}},
        indent=2) + '\n')
    for name, digest in measurement['source_sha256'].items():
        if sha(attempt / name) != digest:
            raise ValueError('Original source changed during finalization: ' + name)
    direction = measurement['direction']['translational_direction']
    result = {'case_id': measurement['case_id'],
        'measured_values': {'direction_diagnostic': {k: v for k, v in measurement.items()
            if k not in ('ego_rows', 'other_rows')}},
        'target_checks': [{'target': 'source-observed within-roundabout translational direction',
            'requested': config['requested_direction'], 'measured': direction,
            'method': 'signed radial cross product of consecutive original positions',
            'tolerance': 0,
            'matched': direction == config['requested_direction'],
            'physical_cause_confirmed': False,
            'cause_evidence': list(measurement['source_sha256'])}],
        'setup_confirmed': False, 'behavior_attempted': True,
        'maneuver_completed': False,
        'termination_reason': 'Saved direction measured; actual roundabout boundary and pixels require original review',
        'physical_failure_flags': ['original_boundary_pixels_and_jurisdiction_unreviewed'],
        'trace_reference': 'trace.jsonl',
        'video_references': [n + '.mkv' for n in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': ([{'name': n, 'unit': 'structured',
            'reference': 'channels/' + n + '.jsonl'} for n in CHANNELS] +
            [{'name': 'roundabout_map', 'unit': 'source_record',
              'reference': 'channels/roundabout_map.json'}]),
        'realized_observables': {'signed_radial_cross_sum_m2': {'value':
            measurement['direction']['signed_radial_cross_sum_m2'],
            'unit': 'm2', 'method': 'signed radial cross product',
            'time_window': '600 original frames', 'statistic': 'consistent step sign',
            'reference': 'channels/kin.position.jsonl'}},
        'accepted': False, 'legal_verdict_claimed': False}
    write_result(attempt, result)
    report = {'format': 'c238396-saved-direction-measurements-v1',
              'case_id': measurement['case_id'],
              'measurements': {'roundabout_context': measure_roundabout_context(measurement),
                               'circulation_direction': measure_circulation_direction(measurement)},
              'diagnostic': {k: v for k, v in measurement.items()
                             if k not in ('ego_rows', 'other_rows')},
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
