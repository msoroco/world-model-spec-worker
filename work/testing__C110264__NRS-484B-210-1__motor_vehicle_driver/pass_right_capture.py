"""Collect source-shaped Native rows for a right pass at 20 Hz.

The local CARLA runner must supply actual snapshot and sensor callback rows and
the shared native_output.FrameMap object. This module is a CPU-testable join;
it does not assert that a requested maneuver was physically completed.
"""
from __future__ import annotations

import math

CAMERAS = ('front', 'rear', 'left', 'right')
ACTOR_FIELDS = ('ego_s_m', 'target_s_m', 'ego_lateral_m', 'target_lateral_m',
                'ego_speed_mps', 'target_speed_mps', 'target_left_signal',
                'target_heading_deg', 'ego_paved', 'target_paved')
NUMERIC = ('ego_s_m', 'target_s_m', 'ego_lateral_m', 'target_lateral_m',
           'ego_speed_mps', 'target_speed_mps', 'target_heading_deg')


def collect_native_trace(rows: list[dict], road: dict, ego_id: int,
                         target_id: int, frame_map: object,
                         expected_frames: int = 900) -> dict:
    """Join original actor and camera samples to an exact Native frame clock."""
    if expected_frames < 8 or len(rows) != expected_frames:
        raise ValueError('complete original frame count required')
    if not isinstance(ego_id, int) or not isinstance(target_id, int) or ego_id == target_id:
        raise ValueError('distinct original actor IDs required')
    if (road.get('source_kind') != 'original_native_map_geometry' or
            not road.get('public_highway_observed') or
            not road.get('two_way_observed')):
        raise ValueError('source-reviewed road context required')
    if not isinstance(road.get('actor_half_width_m'), (int, float)) or road['actor_half_width_m'] <= 0:
        raise ValueError('source actor footprint required')
    first_native = rows[0].get('native_frame_id')
    first_time = rows[0].get('elapsed_seconds')
    if not isinstance(first_native, int) or not isinstance(first_time, (int, float)):
        raise ValueError('original clock origin required')
    frames = []
    for index, sample in enumerate(rows):
        native = sample.get('native_frame_id')
        elapsed = sample.get('elapsed_seconds')
        if native != first_native + index or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed):
            raise ValueError('Native frame identity or clock gap')
        t_s = elapsed - first_time
        if abs(t_s - index / 20) > 0.002:
            raise ValueError('Native 20 Hz clock mismatch')
        if sample.get('ego_id') != ego_id or sample.get('target_id') != target_id:
            raise ValueError('actor identity drift')
        missing = [key for key in ACTOR_FIELDS if key not in sample]
        if missing:
            raise ValueError('missing original actor fields: ' + ', '.join(missing))
        if any(not isinstance(sample[key], (int, float)) or not math.isfinite(sample[key])
               for key in NUMERIC):
            raise ValueError('nonfinite or nonnumeric original actor value')
        if not isinstance(sample['target_left_signal'], bool):
            raise ValueError('original left signal must be boolean')
        cameras = sample.get('camera_frame_ids')
        if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
            raise ValueError('all four original camera frame IDs required')
        if any(cameras[name] != native for name in CAMERAS):
            raise ValueError('camera frame does not join Native frame')
        frame = {'frame': index, 't_s': index / 20, 'native_frame_id': native,
                 'camera_frame_ids': cameras.copy()}
        frame.update({key: sample[key] for key in ACTOR_FIELDS})
        frames.append(frame)
    # Do not write a partial frame map when a later actor or sensor row fails.
    for index, sample in enumerate(rows):
        frame_map.append(sample['native_frame_id'], sample['elapsed_seconds'],
                         original_index=index,
                         camera_frame_ids=sample['camera_frame_ids'].copy())
    return {'source_kind': 'original_native_actor_trace', 'fps': 20,
            'ego_id': ego_id, 'target_id': target_id,
            'road': {key: value for key, value in road.items() if key != 'source_kind'},
            'frames': frames, 'physical_acceptance_claimed': False}
