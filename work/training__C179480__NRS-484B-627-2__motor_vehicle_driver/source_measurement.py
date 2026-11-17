"""Source-bound motion measurements for roadway-stop analysis.

The inputs are original synchronized per-frame actor samples produced by the
future Native runner. This module reports observations, never a legal verdict.
"""
import json
from math import isfinite
from pathlib import Path


REQUIRED = {'frame', 'ego_speed_mps', 'ego_on_roadway', 'ego_lane_overlap',
            'following_speed_mps', 'following_gap_m'}


def load_rows(path):
    rows = []
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    if not rows:
        raise ValueError('Missing original actor history')
    for index, row in enumerate(rows):
        if not REQUIRED <= set(row):
            raise ValueError('Missing required actor source field')
        if row['frame'] != index:
            raise ValueError('Actor frame join is incomplete')
        if type(row['ego_on_roadway']) is not bool or type(row['ego_lane_overlap']) is not bool:
            raise ValueError('Roadway and lane readback must be Boolean')
        for key in ('ego_speed_mps', 'following_speed_mps', 'following_gap_m'):
            value = row[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
                raise ValueError('Invalid original actor measurement: ' + key)
    return rows


def measure(rows, *, fps=20, stop_tolerance_mps=0.05):
    if fps != 20 or not 0 < stop_tolerance_mps <= 0.1:
        raise ValueError('Pinned frame rate or engineering stop tolerance changed')
    if not rows:
        raise ValueError('Missing original actor history')
    stopped = [row for row in rows if row['ego_speed_mps'] <= stop_tolerance_mps]
    roadway_stop = [row for row in stopped if row['ego_on_roadway']]
    overlap_stop = [row for row in roadway_stop if row['ego_lane_overlap']]
    following = [row['following_speed_mps'] for row in rows]
    gaps = [row['following_gap_m'] for row in rows]
    return {
        'sample_count': len(rows),
        'fps': fps,
        'engineering_stop_tolerance_mps': stop_tolerance_mps,
        'complete_stop_observed': bool(stopped),
        'roadway_stop_frames': [row['frame'] for row in roadway_stop],
        'roadway_lane_overlap_frames': [row['frame'] for row in overlap_stop],
        'following_initial_speed_mps': following[0],
        'following_min_speed_mps': min(following),
        'following_speed_drop_mps': max(0.0, following[0] - min(following)),
        'following_min_gap_m': min(gaps),
        'normal_reasonable_movement_impeded': 'independent_original_source_review_required',
        'safe_operation_necessity': 'independent_original_source_review_required',
        'compliance_with_law': 'independent_original_source_review_required',
    }


def analyze(path):
    return measure(load_rows(path))
