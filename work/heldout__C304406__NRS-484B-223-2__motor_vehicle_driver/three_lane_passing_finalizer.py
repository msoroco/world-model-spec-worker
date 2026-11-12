"""Saved-only passing geometry from retained 20 Hz actor and lane sources."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from shapely.geometry import Polygon
from three_lane_finalizer import analyze as analyze_lanes, build_result as build_lane_result
from three_lane_passing import center_clearance, projected_distance


def _source(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure_passing_sources(attempt):
    root = Path(attempt)
    names = ('passing_frames.jsonl', 'three_lane_frames.jsonl',
             'three_lane_context.json', 'three_lane_map_readback.json',
             'trace.jsonl', 'video_frames.jsonl')
    paths = {name: _source(root, name) for name in names}
    passing = _rows(paths['passing_frames.jsonl'][0])
    lanes = _rows(paths['three_lane_frames.jsonl'][0])
    if len(passing) < 2 or len(passing) != len(lanes):
        raise ValueError('Original passing and lane frame counts differ')
    observations = []
    for row, lane in zip(passing, lanes):
        if ((row.get('frame'), row.get('time_s')) !=
                (lane.get('frame'), lane.get('time_s')) or
                row.get('ego_actor_id') != lane.get('ego_actor_id') or
                row.get('target_actor_id') == row.get('ego_actor_id')):
            raise ValueError('Original passing actor/frame identity differs')
        target_body = Polygon(row['target_corners_xy'])
        right_lane = Polygon(lane['lane_polygons_xy']['right'])
        if not target_body.is_valid or target_body.area <= 0 or not right_lane.is_valid:
            raise ValueError('Original passing target body or lane invalid')
        fraction = target_body.intersection(right_lane).area / target_body.area
        if fraction < 0.75:
            raise ValueError('Constructed passing target left right lane')
        forward = lane['road_travel_tangent_xy']
        ego_xy = row['ego_center_xy']
        target_xy = row['target_center_xy']
        gap, _ = projected_distance(ego_xy, forward, target_xy)
        clear = center_clearance(row['right_lane_center_xy'], forward,
                                 row['center_lane_center_xy'], row['other_vehicle_bodies'],
                                 clear_m=row['clear_target_m'])
        observations.append({'frame': row['frame'], 'time_s': row['time_s'],
                             'ego_target_longitudinal_gap_m': gap,
                             'target_right_lane_fraction': fraction,
                             'center_engineering_interval_clear': clear['engineering_interval_clear'],
                             'center_blocked_actors': clear['blocked_actors']})
    return {'format': 'worker-three-lane-passing-observation',
            'sources': {name: digest for name, (_, digest) in paths.items()},
            'observations': observations,
            'gap_changes_sign': observations[0]['ego_target_longitudinal_gap_m'] > 0 and
                                observations[-1]['ego_target_longitudinal_gap_m'] < 0,
            'highway_clearly_visible': None, 'legal_safe_distance': None,
            'passing_exception_legal_judgment': None}


def analyze(attempt):
    report = analyze_lanes(attempt)
    if not report['case_id'].endswith('__center_passing_clear'):
        raise ValueError('Wrong exact passing case identity')
    measured = measure_passing_sources(attempt)
    report['measurements']['passing_observation'] = {
        'method': 'measure_passing_sources', 'value': measured,
        'sources': measured['sources']}
    return report


def build_result(attempt, report):
    result = build_lane_result(attempt, report)
    measured = report['measurements']['passing_observation']['value']
    channel = Path(attempt) / 'passing_observation.jsonl'
    if channel.exists():
        raise ValueError('Retain prior derived passing channel')
    channel.write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                               for row in measured['observations']))
    result['measured_values']['passing_observation'] = measured
    result['recording_evidence'].append({
        'name': 'passing_observation', 'unit': 'meters and body overlap',
        'reference': channel.name, 'sha256': sha256(channel.read_bytes()).hexdigest()})
    result['realized_observables']['passing_observation'] = {
        'unit': 'meters', 'method': 'original target and ego bodies at 20 Hz',
        'time_window': 'all original frames', 'statistic': 'initial_to_final_gap',
        'reference': channel.name,
        'value': [measured['observations'][0]['ego_target_longitudinal_gap_m'],
                  measured['observations'][-1]['ego_target_longitudinal_gap_m']],
        'sample_window_s': [measured['observations'][0]['time_s'],
                            measured['observations'][-1]['time_s']]}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior passing analysis')
    report = analyze(args.attempt)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
