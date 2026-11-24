"""Independent original walker-body and crosswalk geometry checks.

This establishes sampled physical geometry only. Curb meaning, jurisdiction,
camera visibility and legal route classification require separate review.
"""
from __future__ import annotations

import math

from crossing_geometry import crosswalk_overlap, point, validate_scene


def audit_body_history(scene: dict, rows: list[dict], expected_frames: int = 400) -> dict:
    validate_scene(scene)
    if not isinstance(rows, list) or len(rows) != expected_frames:
        raise ValueError('complete original walker body duration missing')
    first = rows[0].get('frame')
    first_time = rows[0].get('time_s')
    actor_id = rows[0].get('actor_id')
    if type(first) is not int or type(first_time) not in (int, float) or not math.isfinite(first_time):
        raise ValueError('original frame or time missing')
    if type(actor_id) is not int:
        raise ValueError('original walker actor missing')
    overlap_frames = []
    centers = []
    for index, row in enumerate(rows):
        if row.get('frame') != first + index or row.get('actor_id') != actor_id:
            raise ValueError('original walker frame or actor join mismatch')
        time_s = row.get('time_s')
        if type(time_s) not in (int, float) or not math.isfinite(time_s) or abs(time_s - first_time - index / 20) > 0.001:
            raise ValueError('original walker 20 Hz time join mismatch')
        if row.get('source') != 'original_native' or row.get('source_kind') != 'original_native_world_vertices':
            raise ValueError('original Native body source missing')
        body = row.get('body_xy_m')
        if not isinstance(body, list) or len(body) != 4:
            raise ValueError('four original body corners missing')
        corners = [point(corner) for corner in body]
        if (math.dist(corners[0], corners[1]) < 0.1 or
            math.dist(corners[1], corners[2]) < 0.1):
            raise ValueError('degenerate walker body polygon')
        center = point(row.get('body_center_xy_m'))
        if not (min(x for x, _ in corners) <= center[0] <= max(x for x, _ in corners) and
                min(y for _, y in corners) <= center[1] <= max(y for _, y in corners)):
            raise ValueError('walker center outside body polygon bounds')
        centers.append(list(center))
        if crosswalk_overlap(corners + [corners[0]], scene['crosswalk_boundaries_xy_m']):
            overlap_frames.append(first + index)
    if bool(overlap_frames) != (scene['crosswalk_context'] == 'inside'):
        raise ValueError('original body and crosswalk context disagree')
    return {'case_id': scene['case_id'], 'first_original_frame': first,
            'last_original_frame': first + expected_frames - 1,
            'frame_count': expected_frames, 'actor_id': actor_id,
            'body_crosswalk_overlap_frames': overlap_frames,
            'body_center_first_xy_m': centers[0],
            'body_center_last_xy_m': centers[-1],
            'legal_route_classification': 'unresolved',
            'physical_visibility': 'unconfirmed'}
