"""Source-bound C10316 retry metrics; synthetic proof never certifies Native pixels."""
import hashlib
import json
import math
from pathlib import Path


def measure(source, expected_sha256):
    source = Path(source)
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError('Changed fallback observation source')
    values = [json.loads(line) for line in source.read_text().splitlines()]
    if len(values) != 240 or any(row.get('source_kind') != 'synthetic_cpu_fixture' for row in values):
        raise ValueError('Synthetic retry proof requires 240 provenance-marked frames')
    previous = -1
    first_clearance = None
    tracking_exceedances = 0
    visible = {'approach': 0, 'reference_corner': 0}
    for index, row in enumerate(values):
        if row.get('native_frame') != index + 100 or row.get('time_s') != round(index / 20, 4):
            raise ValueError('Fallback observation frame/time join differs')
        if row['native_frame'] <= previous:
            raise ValueError('Fallback observation frame order differs')
        previous = row['native_frame']
        pose = row.get('pedestrian_xy_m')
        body = row.get('pedestrian_footprint_xy_m')
        if not isinstance(pose, list) or len(pose) != 2 or not isinstance(body, list) or len(body) != 4:
            raise ValueError('Missing pedestrian body source')
        if any(not isinstance(v, (int, float)) or not math.isfinite(v)
               for point in [pose, *body] for v in point):
            raise ValueError('Nonfinite pedestrian body source')
        if index == 0:
            first_clearance = max(0, -2 - max(point[0] for point in body))
        requested = row.get('requested_xy_m')
        if not isinstance(requested, list) or len(requested) != 2:
            raise ValueError('Missing requested pedestrian path')
        tracking_exceedances += math.dist(pose, requested) > .2
        views = row.get('synthetic_camera_annotation')
        if not isinstance(views, dict) or set(views) != set(visible):
            raise ValueError('Missing two-view synthetic annotation')
        for role, flag in views.items():
            if type(flag) is not bool:
                raise ValueError('Invalid synthetic visibility annotation')
            visible[role] += flag
    fractions = {role: count / 240 for role, count in visible.items()}
    return {'format': 'c10316-synthetic-fallback-measurement-v1',
            'source_kind': 'synthetic_cpu_fixture', 'source_sha256': expected_sha256,
            'spawn_clearance_m': first_clearance,
            'path_error_frames_over_0_2_m': tracking_exceedances,
            'camera_visible_fraction': fractions,
            'fallback1_trigger': first_clearance < 1,
            'fallback2_trigger': tracking_exceedances >= 10,
            'fallback3_trigger': any(value < .95 for value in fractions.values()),
            'original_native_observed': False, 'original_pixels_observed': False}
