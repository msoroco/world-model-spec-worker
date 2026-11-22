"""Build explicit synthetic source packets for C111088 CPU diagnostics only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from geometry import INTERSECTION, body, ego_y, other_x, overlap

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
BASE = 'training__C111088__NRS-484B-307-5a__motor_vehicle_driver'
SCAFFOLD = REPO / 'work/training__C110812__NRS-484B-113-2__motor_vehicle_driver/selected-diagnostic-condition_a.json'


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create(suffix):
    present = suffix == 'true'
    template = json.loads(SCAFFOLD.read_text())
    native, bodies, mappings, trace, evidence = [], [], [], [], []
    for index in range(840):
        frame, time_s = index + 100, (index + 1) / 20
        ego_center_y = ego_y(index, present)
        other_center_x = other_x(index) if present else -24.0
        ego_body = body(1.75, ego_center_y, 'north')
        other_body = body(other_center_x, -1.75, 'east')
        occupied = overlap(other_body, INTERSECTION) > 0
        speed = max(0.0, (ego_y(min(index + 1, 839), present) - ego_y(index, present)) * 20)
        signal = {'native_actor_id': 17, 'native_state': 'Green' if index >= 100 else 'Red',
                  'authored_aspect': 'green_straight_arrow',
                  'authored_aspect_source': 'road.xodr subtype 2',
                  'facing_ego_native_survey': True, 'pixel_aspect_verified': False}
        other = {'native_actor_id': 18, 'native_body_xy_m': other_body,
                 'within_intersection_or_adjacent_crosswalk': occupied,
                 'prior_green_entry_observed': present and index >= 72,
                 'west_native_signal_actor_id': 19,
                 'west_native_state': 'Red' if index >= 100 else 'Green'}
        sample = {'native_frame': frame, 'time_s': time_s,
                  'native_center_xy_m': [1.75, ego_center_y], 'native_yaw_deg': 90.0,
                  'native_body_xy_m': ego_body, 'speed_mps': speed,
                  'speed_provenance': 'synthetic_native_sample',
                  'governing_signal': signal, 'other_vehicle': other,
                  'controller_request': {'route': 'straight', 'brake': 1.0 if present and occupied else 0.0,
                                         'target_speed_m_s': 0.0 if present and occupied else 4.0,
                                         'yielding_to_actor_ids': ['18'] if present and occupied else [],
                                         'turn_command': 0.0}}
        native.append(sample)
        bodies.append({'frame': frame, 'time_s': time_s,
                       'body_vertices_m': [[x, y, 0] for x, y in ego_body]})
        mappings.append({'video_frame': index, 'native_frame': frame,
                         'carla_frame': frame, 'time_s': time_s})
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': 1.75, 'y': ego_center_y, 'z': .5},
                      'position_m': [1.75, ego_center_y, .5],
                      'heading_deg': 90.0, 'speed_mps': speed,
                      'speed_mph': speed / .44704,
                      'control': {'throttle': 0.0, 'brake': 1.0 if present and occupied else 0.0,
                                  'hand_brake': False, 'steer': 0.0},
                      'speed_provenance': 'synthetic_native_sample'})
        evidence.append({'original_frame': frame, 'recording_time_s': time_s,
                         'replay_frame': frame, 'replay_simulation_time_s': time_s,
                         'actor_id': 107,
                         'ego': {'body_vertices_m': [[x, y, 0] for x, y in ego_body],
                                 'position_m': [1.75, ego_center_y, .5],
                                 'heading_deg': 90.0, 'speed_mps': speed,
                                 'speed_provenance': 'synthetic_native_sample'},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 3, 'section_id': 0,
                                                       'lane_id': -1, 's_m': max(0.0, ego_center_y + 30)}}})
    geometry = {'native_map_sha256': '0' * 64,
                'intersection_bounds_xy_m': list(INTERSECTION),
                'adjacent_crosswalk_xy_m': [[-3.5, -12], [3.5, -12], [3.5, -10], [-3.5, -10]],
                'stop_line_y_m': -14.0, 'authored_aspect': 'green_straight_arrow',
                'pixel_aspect_verified': False, 'synthetic_diagnostic': True}
    geometry['surveyed_arrow_intersection'] = {
        'intersection_bounds_xy_m': geometry['intersection_bounds_xy_m'],
        'adjacent_crosswalk_xy_m': geometry['adjacent_crosswalk_xy_m'],
        'authored_aspect': 'green_straight_arrow',
        'original_native_or_pixel_survey': False, 'synthetic_diagnostic': True}
    trace_text = lines(trace)
    template['files'].update({
        'road_geometry.json': json.dumps(geometry, separators=(',', ':')),
        'aspect-review.json': json.dumps({'review_kind': 'synthetic_fixture_aspect',
            'original_pixel_reviewed': False, 'diagnostic_only': True,
            'first_video_frame': 100, 'last_video_frame': 839}, separators=(',', ':')),
        'native_samples.jsonl': lines(native), 'body_history.jsonl': lines(bodies),
        'video_frames.jsonl': lines(mappings), 'trace.jsonl': trace_text,
        'capture/evidence.jsonl': lines(evidence),
        'capture/manifest.json': json.dumps({'frames': 840, 'extraction_confirmed': True,
            'synthetic_diagnostic': True, 'sources': {
                'road.xodr': sha(PACKAGE / 'native/road.xodr'),
                'trace.jsonl': hashlib.sha256(trace_text.encode()).hexdigest()}},
            separators=(',', ':')),
        'capture/recorder_info.txt': 'Create 107: vehicle.lincoln.mkz_2020\nSynthetic CPU diagnostic. No CARLA recording.\n',
    })
    for video in template['videos']:
        video['color'] = 'black'
    target = PACKAGE / f'diagnostic-{suffix}.json'
    target.write_text(json.dumps(template, separators=(',', ':'), allow_nan=False) + '\n')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input-assignment.json',
                           'source': f'inputs/{BASE}/assignment.json',
                           'sha256': sha(REPO / 'inputs' / BASE / 'assignment.json')}],
              'generator': {'source': str(target.relative_to(REPO)), 'sha256': sha(target)}}
    (PACKAGE / f'diagnostic-{suffix}-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    return {'suffix': suffix, 'spec_bytes': target.stat().st_size, 'spec_sha256': sha(target)}


if __name__ == '__main__':
    print(json.dumps([create(s) for s in ('false', 'true')], indent=2))
