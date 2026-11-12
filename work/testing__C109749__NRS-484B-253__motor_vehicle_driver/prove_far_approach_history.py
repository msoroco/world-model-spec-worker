"""Prove far-turn measurement over a full-duration synthetic source history.

The generated history is a CPU diagnostic, never a Native recording or legal
verdict. Original-source shaped files stay under the ignored output directory.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER))
from far_approach_observation import observe


def actor(actor_id, x, y, vx, vy):
    return {'actor_id': actor_id, 'position_xy_m': [x, y],
            'velocity_xy_mps': [vx, vy],
            'body_vertices_xy_m': [[x-1, y-1], [x+1, y-1],
                                   [x+1, y+1], [x-1, y+1]]}


def source_rows():
    rows = []
    for index in range(900):
        frame = 38033 + index
        time_s = round((index + 1) / 20, 6)
        if index <= 40:
            ego = actor(205, -12 + 0.25 * index, 0, 5, 0)
            heading = 0
        else:
            ego = actor(205, -2, -0.25 * (index-40), 0, -5)
            heading = -20 if index == 41 else -90
        oncoming = actor(307, 35 - 0.25 * index, 0, -5, 0)
        reciprocal = actor(411, 30, 12, 0, 0)
        rows.append({'frame': frame, 'time_s': time_s, 'ego': ego,
                     'oncoming': oncoming, 'reciprocal': reciprocal,
                     'ego_heading_deg': heading,
                     'ego_left_indicator': index <= 85})
    return rows


def write_jsonl(path, rows):
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                            for row in rows))


def make_sources(root, rows):
    root.mkdir(parents=True)
    config = json.loads((FOLDER / 'cases/approaching_far/config.json').read_text())
    geometry = {'native_junction_id': 17,
                'intersection_polygon_xy_m': [[-5,-5],[5,-5],[5,5],[-5,5]],
                'conflict_point_xy_m': [0,0],
                'oncoming_direction_xy': [-1,0],
                'ego_intended_maneuver': 'left_turn',
                'geometry_source': 'synthetic CPU diagnostic geometry',
                'legal_intersection_status': 'unverified'}
    (root / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    (root / 'intersection_geometry.json').write_text(json.dumps(geometry, indent=2) + '\n')
    write_jsonl(root / 'interaction_history.jsonl', rows)
    write_jsonl(root / 'video_frames.jsonl',
                [{'video_frame': i, 'carla_frame': row['frame'],
                  'native_frame': row['frame'], 'time_s': row['time_s']}
                 for i, row in enumerate(rows)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Use a fresh diagnostic output')
    positive = output / 'positive'
    rows = source_rows()
    make_sources(positive, rows)
    observed = observe(positive)
    if observed['ego_turn_start_frame'] != 38074 or observed['opposing_entry_frame'] <= 38074:
        raise ValueError('Expected source-bound far-before-entry sequence')
    if observed['turn_sample']['kinematic_time_to_conflict_s'] < 4.0:
        raise ValueError('Expected measured engineering release margin')
    close = copy.deepcopy(rows)
    for row in close:
        row['oncoming']['velocity_xy_mps'] = [-20, 0]
    make_sources(output / 'close_negative', close)
    try:
        observe(output / 'close_negative')
    except ValueError as exc:
        if 'engineering release TTC' not in str(exc):
            raise
    else:
        raise ValueError('Close approach was accepted')
    missing = output / 'missing_source_negative'
    make_sources(missing, rows)
    (missing / 'video_frames.jsonl').unlink()
    try:
        observe(missing)
    except ValueError as exc:
        if 'Missing required source: video_frames.jsonl' not in str(exc):
            raise
    else:
        raise ValueError('Missing original frame map was accepted')
    print(json.dumps({'format': 'far-approach-full-history-cpu-proof',
                      'samples': len(rows), 'rate_hz': 20, 'duration_s': 45,
                      'ego_turn_start_frame': observed['ego_turn_start_frame'],
                      'opposing_entry_frame': observed['opposing_entry_frame'],
                      'turn_sample': observed['turn_sample'],
                      'source_hashes': observed['source_hashes'],
                      'close_negative_rejected': True,
                      'missing_source_negative_rejected': True,
                      'legal_verdict_asserted': False,
                      'physical_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
