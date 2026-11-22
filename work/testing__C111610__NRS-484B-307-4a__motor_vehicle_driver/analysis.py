"""Saved-only measurements of an ego-facing arrow and adjacent-crosswalk turn.

Input JSONL is a proposed Native export. This module never opens CARLA or assigns
a legal verdict; it rejects stale sources and unsupported observational claims.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from runner import bounds, lawful_occupants, load_scene, overlaps, sole_turn_arrow

SOURCES = ('turn-history.jsonl', 'intersection-context.json', 'video_frames.jsonl')


def _verified(attempt, acquisition, name):
    path = attempt / name
    record = acquisition.get(name, {})
    if not path.is_file() or record.get('kind') != 'original_native':
        raise ValueError('Missing required source: ' + name)
    if record.get('sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError('stale original Native source: ' + name)
    return path


def _rows(path, frame_key='frame'):
    values = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(values) < 3:
        raise ValueError('original frame history is too short')
    previous = None
    for row in values:
        frame, time_s = row.get(frame_key), row.get('time_s')
        if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
            raise ValueError('invalid original frame/time')
        if previous and (frame <= previous[0] or time_s <= previous[1]):
            raise ValueError('original frame/time ordering changed')
        previous = frame, time_s
    return values


def measure(attempt, expected_case, scene_path=None):
    attempt = Path(attempt)
    scene = load_scene(scene_path or attempt / 'scene.json')
    if expected_case not in ('crosswalk_clear_turn', 'crosswalk_occupied_yield'):
        raise ValueError('unknown exact case')
    if not scene['case_id'].endswith('__' + expected_case):
        raise ValueError('scene identity does not match exact case')
    if scene['crosswalk_setup'] != ('clear' if expected_case == 'crosswalk_clear_turn' else 'occupied'):
        raise ValueError('scene setup does not match exact case')
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    paths = {name: _verified(attempt, acquisition, name) for name in SOURCES}
    context = json.loads(paths['intersection-context.json'].read_text())
    for name in ('map_source', 'adjacent_crosswalk_source', 'ego_route_source',
                 'facing_head_source', 'lawful_presence_method'):
        if not context.get(name):
            raise ValueError('original intersection context missing ' + name)
    if context.get('facing_head_id') != scene['facing_head_id']:
        raise ValueError('original facing-head identity changed')
    if context.get('adjacent_crosswalk_bounds_m') != scene['adjacent_crosswalk_bounds_m']:
        raise ValueError('adjacent-crosswalk geometry changed')
    if (context.get('duration_s') != scene['duration_s'] or
            context.get('camera_profile') != 'overview1080-capability'):
        raise ValueError('original duration or camera profile changed')
    rows = _rows(paths['turn-history.jsonl'])
    frames = _rows(paths['video_frames.jsonl'], 'carla_frame')
    if len(rows) != round(scene['duration_s'] * scene['rate_hz']):
        raise ValueError('original turn history does not cover planned duration')
    entry_sha = None
    if expected_case == 'crosswalk_occupied_yield':
        if context.get('pedestrian_entry_source') != 'pedestrian-entry.jsonl':
            raise ValueError('original pedestrian Walk entry source missing')
        entry_path = _verified(attempt, acquisition, 'pedestrian-entry.jsonl')
        entry = _rows(entry_path)
        if (entry[-1]['frame'] >= rows[0]['frame'] or
                not overlaps(entry[-1].get('person_body_vertices_m'),
                             scene['adjacent_crosswalk_bounds_m'])):
            raise ValueError('original Walk entry did not precede crosswalk occupancy')
        if any((r.get('pedestrian_signal_head_id') != scene['pedestrian_signal_head_id'] or
                str(r.get('walk_state', '')).split('.')[-1].lower() != 'walk')
               for r in entry):
            raise ValueError('original pedestrian Walk indication not sustained through entry')
        entry_sha = acquisition['pedestrian-entry.jsonl']['sha256']
    elif context.get('pedestrian_entry_source'):
        raise ValueError('clear case unexpectedly contains pedestrian entry source')
    if len(rows) != len(frames):
        raise ValueError('video frame map differs from turn history')
    occupied_frames, held_frames, moving_frames, crossing_frames = [], [], [], []
    headings = []
    for index, (row, video) in enumerate(zip(rows, frames)):
        frame = row['frame']
        if ((video['carla_frame'], video['time_s']) != (frame, row['time_s']) or
                video.get('video_frame') != index):
            raise ValueError('video frame does not map to original turn frame')
        sole_turn_arrow(row.get('facing_signal', {}), scene, frame)
        ego = row.get('ego', {})
        body = ego.get('body_vertices_m')
        left, bottom, right, top = bounds(body)
        speed, brake = ego.get('speed_mps'), ego.get('brake')
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError('original ego speed missing')
        if type(brake) not in (int, float) or not 0 <= brake <= 1:
            raise ValueError('original ego brake missing')
        if not ego.get('source_ref') or not ego.get('heading_source'):
            raise ValueError('original ego body or heading source missing')
        heading = ego.get('heading_deg')
        if type(heading) not in (int, float) or not math.isfinite(heading):
            raise ValueError('original ego heading missing')
        headings.append(heading)
        persons = row.get('pedestrians')
        traffic = row.get('other_traffic')
        if not isinstance(persons, list) or not isinstance(traffic, list):
            raise ValueError('original participant inventory missing')
        occupants = lawful_occupants(persons, scene)
        if persons and any(p.get('lawful_presence_source') !=
                           'pedestrian-entry.jsonl and original Walk head' for p in persons):
            raise ValueError('pedestrian presence not bound to verified Walk entry')
        for vehicle in traffic:
            if not vehicle.get('source_ref') or not vehicle.get('lawful_presence_source'):
                raise ValueError('other intersection traffic source missing')
        if any(v.get('lawfully_using_intersection') is True for v in traffic):
            raise ValueError('other lawful traffic violates fixed pair condition')
        if occupants:
            occupied_frames.append(frame)
            if right > scene['turn_entry_x_m'] or speed > .15 or brake < .5:
                raise ValueError('ego did not hold before occupied-crosswalk turn entry')
            held_frames.append(frame)
        if speed > .15:
            moving_frames.append(frame)
        if bottom < scene['adjacent_crosswalk_bounds_m'][3] and top > scene['adjacent_crosswalk_bounds_m'][1]:
            crossing_frames.append(frame)
    if expected_case == 'crosswalk_clear_turn' and occupied_frames:
        raise ValueError('clear case contains lawful adjacent-crosswalk occupant')
    if expected_case == 'crosswalk_occupied_yield' and not occupied_frames:
        raise ValueError('occupied case has no observed lawful occupant')
    if not moving_frames or not crossing_frames:
        raise ValueError('left-turn movement through adjacent crosswalk not observed')
    heading_change = (headings[-1] - headings[0] + 180) % 360 - 180
    if not 45 <= heading_change <= 135:
        raise ValueError('observed ego heading does not establish authored left turn')
    if expected_case == 'crosswalk_occupied_yield' and max(occupied_frames) >= min(crossing_frames):
        raise ValueError('ego entered crosswalk before lawful occupant cleared')
    return {'format': 'worker-left-arrow-crosswalk-measurements',
            'case': expected_case, 'frame_count': len(rows),
            'lawful_occupancy_frames': occupied_frames,
            'yield_hold_frames': held_frames, 'moving_frames': moving_frames,
            'turn_crosswalk_frames': crossing_frames,
            'observed_heading_change_deg': heading_change,
            'sources': {**{name: acquisition[name]['sha256'] for name in SOURCES},
                        **({'pedestrian-entry.jsonl': entry_sha} if entry_sha else {})},
            'legal_right_of_way_verdict': 'unresolved'}


def build_report(attempt):
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    case_id = config['selected_case_id']
    case = case_id.removeprefix(config['assignment_id'] + '__')
    if case_id != config['assignment_id'] + '__' + case:
        raise ValueError('saved exact case does not belong to assignment')
    value = measure(attempt, case, attempt / 'scene.json')
    sources = value['sources']
    return {'format': 'worker-analysis-report',
            'measurements': {
                'arrow_direction_measurement': {'value': {
                    'frame_count': value['frame_count'],
                    'observed_heading_change_deg': value['observed_heading_change_deg'],
                    'moving_frames': value['moving_frames'],
                    'legal_direction_verdict': 'unresolved'},
                    'method': 'measure', 'sources': sources},
                'adjacent_crosswalk_yield_measurement': {
                    'value': value, 'method': 'measure', 'sources': sources}},
            'limitations': ['Lawful entry and right-of-way require independent review.',
                            'Realized CARLA geometry and pixels require physical review.'],
            'analysis_complete': True, 'legal_verdict_claimed': False}


def saved_result(attempt, report):
    from worker_exchange.native_output import physical_result, validate_result
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    planned = construction['recording_description']
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    history = _verified(attempt, acquisition, 'turn-history.jsonl')
    rows = _rows(history)
    frame_map = _verified(attempt, acquisition, 'video_frames.jsonl')
    frames = _rows(frame_map, 'carla_frame')
    if len(rows) != len(frames) or any(
            (row['frame'], row['time_s']) != (frame['carla_frame'], frame['time_s'])
            for row, frame in zip(rows, frames)):
        raise ValueError('original camera/turn frame join changed')
    context = json.loads(_verified(attempt, acquisition, 'intersection-context.json').read_text())
    output = attempt / 'channels'
    output.mkdir(exist_ok=True)
    streams = {
        'ego_body_heading_history': [(r['time_s'], r['ego']) for r in rows],
        'facing_arrow_history': [(r['time_s'], r['facing_signal']) for r in rows],
        'pedestrian_body_lawful_history': [(r['time_s'], r['pedestrians']) for r in rows],
        'other_traffic_history': [(r['time_s'], r['other_traffic']) for r in rows],
        'crosswalk_geometry': [(r['time_s'], context['crosswalk_vertices_m']) for r in rows],
        'turn_route': [(r['time_s'], context['route_waypoints']) for r in rows],
        'camera_frame_map': [(r['time_s'], frame) for r, frame in zip(rows, frames)]}
    evidence = []
    for channel in planned['channels']:
        name = channel['name']
        if name not in streams:
            raise ValueError('unsupported declared channel: ' + name)
        path = output / (name + '.jsonl')
        with path.open('x') as stream:
            for time_s, value in streams[name]:
                stream.write(json.dumps({'time_s': time_s, 'value': value},
                                        allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(path.relative_to(attempt))})
    context_path = output / 'context.json'
    with context_path.open('x') as stream:
        stream.write(json.dumps({'intersection_context': context,
            'pedestrian_entry_source_sha256':
                acquisition.get('pedestrian-entry.jsonl', {}).get('sha256')},
            allow_nan=False) + '\n')
    for item in planned['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': str(context_path.relative_to(attempt))})
    value = report['measurements']['adjacent_crosswalk_yield_measurement']['value']
    target = (bool(value['yield_hold_frames']) if value['case'] ==
              'crosswalk_occupied_yield' else bool(value['turn_crosswalk_frames']))
    result = {'case_id': config['selected_case_id'], 'measured_values': value,
        'target_checks': [{'target': 'observed turn and source-grounded adjacent-crosswalk yield',
            'requested': True, 'measured': target, 'method': 'measure', 'tolerance': 0,
            'matched': target, 'physical_cause_confirmed': False,
            'cause_evidence': value['sources']}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Saved source assessment pending physical review',
        'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
        'video_references': ['overview.mkv', 'approach.mkv',
                             'reference_corner.mkv', 'driver_reference.mkv'],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': planned, 'recording_evidence': evidence,
        'realized_observables': {}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case')
    parser.add_argument('--scene')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.case:
        result = measure(args.attempt, args.case, args.scene)
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    else:
        report = build_report(args.attempt)
        result = saved_result(args.attempt, report)
        report['physical_checks'] = result['physical_checks']
        report['realized_observables'] = result['realized_observables']
        with (Path(args.attempt) / 'result.json').open('x') as stream:
            stream.write(json.dumps(result, indent=2) + '\n')
        with Path(args.output).open('x') as stream:
            stream.write(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
