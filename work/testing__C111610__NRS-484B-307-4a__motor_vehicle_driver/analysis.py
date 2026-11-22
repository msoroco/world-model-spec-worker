"""Saved-only measurements of an ego-facing arrow and adjacent-crosswalk turn.

Input JSONL is a proposed Native export. This module never opens CARLA or assigns
a legal verdict; it rejects stale sources and unsupported observational claims.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from runner import bounds, lawful_occupants, load_scene, sole_turn_arrow

SOURCES = ('turn-history.jsonl', 'intersection-context.json', 'video_frames.jsonl')


def _verified(attempt, acquisition, name):
    path = attempt / name
    record = acquisition.get(name, {})
    if not path.is_file() or record.get('kind') != 'original_native':
        raise ValueError('missing original Native source: ' + name)
    if record.get('sha256') != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError('stale original Native source: ' + name)
    return path


def _rows(path):
    values = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(values) < 3:
        raise ValueError('original frame history is too short')
    previous = None
    for row in values:
        frame, time_s = row.get('frame'), row.get('time_s')
        if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
            raise ValueError('invalid original frame/time')
        if previous and (frame <= previous[0] or time_s <= previous[1]):
            raise ValueError('original frame/time ordering changed')
        previous = frame, time_s
    return values


def measure(attempt, expected_case, scene_path=None):
    attempt = Path(attempt)
    scene = load_scene(scene_path)
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
    rows = _rows(paths['turn-history.jsonl'])
    frames = _rows(paths['video_frames.jsonl'])
    if len(rows) != len(frames):
        raise ValueError('video frame map differs from turn history')
    occupied_frames, held_frames, moving_frames, crossing_frames = [], [], [], []
    for row, video in zip(rows, frames):
        frame = row['frame']
        if (video['frame'], video['time_s']) != (frame, row['time_s']):
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
        persons = row.get('pedestrians')
        traffic = row.get('other_traffic')
        if not isinstance(persons, list) or not isinstance(traffic, list):
            raise ValueError('original participant inventory missing')
        occupants = lawful_occupants(persons, scene)
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
    if expected_case == 'crosswalk_occupied_yield' and max(occupied_frames) >= min(crossing_frames):
        raise ValueError('ego entered crosswalk before lawful occupant cleared')
    return {'format': 'worker-left-arrow-crosswalk-measurements',
            'case': expected_case, 'frame_count': len(rows),
            'lawful_occupancy_frames': occupied_frames,
            'yield_hold_frames': held_frames, 'moving_frames': moving_frames,
            'turn_crosswalk_frames': crossing_frames,
            'sources': {name: acquisition[name]['sha256'] for name in SOURCES},
            'legal_right_of_way_verdict': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--scene')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = measure(args.attempt, args.case, args.scene)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
