"""Source-backed parking pose preparation, separate from the legal decision."""
from __future__ import annotations

import json
import math
from pathlib import Path

from saved_measure import process


def assess(attempt, config, *, allow_fixture=False):
    attempt = Path(attempt)
    measured = process(attempt, config, allow_fixture=allow_fixture)
    geometry = json.loads((attempt / 'road_geometry.json').read_text())
    samples = [json.loads(x) for x in (attempt / 'native_samples.jsonl').read_text().splitlines()]
    bodies = [json.loads(x) for x in (attempt / 'body_history.jsonl').read_text().splitlines()]
    # Engineering containment in the authored 6 m by 3 m bay; it is not a
    # statutory angle tolerance. Rotate each observed vertex into bay axes.
    heading = math.radians(geometry['bay_heading_deg'])
    forward = (math.cos(heading), math.sin(heading))
    lateral = (-forward[1], forward[0])
    center = geometry['bay_center_xy_m']
    out_of_bay = 0
    for body in bodies:
        for x, y, _ in body['body_vertices_m']:
            offset = (x - center[0], y - center[1])
            longitudinal = sum(a*b for a, b in zip(offset, forward))
            transverse = sum(a*b for a, b in zip(offset, lateral))
            if abs(longitudinal) > geometry['bay_extent_length_m']/2 or \
                    abs(transverse) > geometry['bay_extent_width_m']/2:
                out_of_bay += 1
                break
    speeds = [row['ego_speed_mps'] for row in samples]
    # 0.1 m/s is an engineering at-rest diagnostic, not a legal threshold.
    stationary = max(speeds) <= .1
    status = 'met' if not out_of_bay and stationary else 'not_met'
    return {'format': 'c385967-physical-preparation-v1',
            'case_id': config['case_id'], 'status': status,
            'source_kind': measured['source_kind'], 'source_hashes': measured['source_hashes'],
            'frames': len(samples), 'body_frames_outside_authored_bay': out_of_bay,
            'maximum_speed_mps': max(speeds), 'at_rest_engineering_cap_mps': .1,
            'city_permission_verified': False, 'legal_angle_tolerance_defined': False,
            'legal_verdict': None,
            'original_physical_completion_claimed': status == 'met' and
                measured['source_kind'] == 'original_native_capture'}
