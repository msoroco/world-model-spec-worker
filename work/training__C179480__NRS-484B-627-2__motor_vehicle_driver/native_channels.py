"""Derive C179480 motion channels from retained original actor/map rows."""
import argparse
import json
from math import isfinite
from pathlib import Path

from source_measurement import analyze_hazard, load_rows


CHANNELS = ('ego_pose', 'ego_speed', 'ego_stop_history',
            'roadway_surface_grounding', 'ego_lane_footprint',
            'following_actor_gap_history', 'following_actor_deceleration',
            'following_actor_stop_history', 'ego_velocity_history')
SAFE_CHANNELS = ('hazard_actor_state', 'ego_hazard_gap_history')


def channels_for(case):
    if case not in ('reference', 'contrast', 'safe_operation_stop'):
        raise ValueError('Unknown source case for channels')
    return CHANNELS + (SAFE_CHANNELS if case == 'safe_operation_stop' else ())


def _vector(value, length):
    return (isinstance(value, list) and len(value) == length
            and all(type(number) in (int, float) and isfinite(number)
                    for number in value))


def derive(attempt):
    attempt = Path(attempt)
    rows = load_rows(attempt/'native-actors.jsonl', attempt/'video_frames.jsonl')
    mapping = [json.loads(line) for line in
               (attempt/'video_frames.jsonl').read_text().splitlines() if line.strip()]
    map_readback = json.loads((attempt/'native-map-readback.json').read_text())
    if (map_readback.get('format') != 'c179480-original-map-readback-v1'
            or type(map_readback.get('road_id')) is not int
            or type(map_readback.get('lane_id')) is not int):
        raise ValueError('Missing original roadway map readback')
    channels = channels_for(map_readback.get('case'))
    if map_readback['case'] == 'safe_operation_stop':
        analyze_hazard(attempt/'native-actors.jsonl', attempt/'video_frames.jsonl')
    values = {name: [] for name in channels}
    previous_speed = None
    for row, frame in zip(rows, mapping):
        if (row.get('source_kind') != 'original_carla_actor_and_map_readback'
                or not _vector(row.get('ego_velocity_xyz_mps'), 3)
                or not _vector(row.get('following_velocity_xyz_mps'), 3)
                or not isinstance(row.get('ego_body_vertices_xyz_m'), list)
                or len(row['ego_body_vertices_xyz_m']) < 4
                or any(not _vector(vertex, 3) for vertex in row['ego_body_vertices_xyz_m'])
                or type(row.get('following_on_driving_lane')) is not bool
                or type(row.get('driving_road_id')) is not int
                or type(row.get('driving_lane_id')) is not int
                or row['driving_road_id'] != map_readback['road_id']
                or row['driving_lane_id'] != map_readback['lane_id']):
            raise ValueError('Missing complete original actor/map channel source')
        time_s = frame['time_s']
        body = row['ego_body_vertices_xyz_m']
        position = [row['ego_x_m'], row['ego_y_m']]
        follower_position = [row['following_x_m'], row['following_y_m']]
        delta = None if previous_speed is None else (
            row['following_speed_mps']-previous_speed) / (time_s-previous_time)
        previous_speed = row['following_speed_mps']
        previous_time = time_s
        sample = {
            'ego_pose': {'position_xy_m': position, 'yaw_deg': row['ego_yaw_deg'],
                         'body_vertices_xyz_m': body},
            'ego_speed': row['ego_speed_mps'],
            'ego_stop_history': {'speed_mps': row['ego_speed_mps'],
                                 'frame': row['frame']},
            'roadway_surface_grounding': {
                'ego_on_driving_roadway': row['ego_on_roadway'],
                'road_id': row['driving_road_id'], 'lane_id': row['driving_lane_id'],
                'map_name': map_readback['map_name']},
            'ego_lane_footprint': {
                'body_vertices_xyz_m': body,
                'driving_lane_overlap': row['ego_lane_overlap'],
                'body_lateral_min_m': row['ego_body_lateral_min_m'],
                'body_lateral_max_m': row['ego_body_lateral_max_m'],
                'lane_width_m': row['driving_lane_width_m']},
            'following_actor_gap_history': {
                'gap_m': row['following_gap_m'],
                'position_xy_m': follower_position,
                'on_driving_lane': row['following_on_driving_lane']},
            'following_actor_deceleration': {'acceleration_mps2': delta,
                                             'speed_mps': row['following_speed_mps']},
            'following_actor_stop_history': {
                'speed_mps': row['following_speed_mps'],
                'velocity_xyz_mps': row['following_velocity_xyz_mps']},
            'ego_velocity_history': row['ego_velocity_xyz_mps'],
        }
        if map_readback['case'] == 'safe_operation_stop':
            hazard = row['hazard_state']
            if (hazard['road_id'] != map_readback['road_id']
                    or hazard['lane_id'] != map_readback['lane_id']):
                raise ValueError('Hazard source differs from original driving lane')
            sample['hazard_actor_state'] = {
                'position_xyz_m': hazard['position_xyz_m'],
                'velocity_xyz_mps': hazard['velocity_xyz_mps'],
                'body_vertices_xyz_m': hazard['body_vertices_xyz_m'],
                'speed_mps': hazard['speed_mps'],
                'on_driving_lane': hazard['on_driving_lane'],
                'road_id': hazard['road_id'], 'lane_id': hazard['lane_id']}
            sample['ego_hazard_gap_history'] = hazard['ego_center_gap_m']
        for name in channels:
            values[name].append({'time_s': time_s, 'value': sample[name]})
    directory = attempt/'channels'
    directory.mkdir(exist_ok=True)
    for name, samples in values.items():
        path = directory/(name+'.jsonl')
        with path.open('x') as stream:
            for sample in samples:
                stream.write(json.dumps(sample, allow_nan=False)+'\n')
    return {'channels': list(channels), 'frames': len(rows)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(derive(args.attempt), sort_keys=True))


if __name__ == '__main__':
    main()
