"""Source-cited engineering event candidates from original following samples.

These triggers help locate review frames. A map speed limit is not proof of a
physical sign, a headway threshold is not the legal too-close standard, and a
time-to-collision threshold is not the legal immediate-hazard standard.
"""

from hashlib import sha256
import json
from math import cos, sin, pi, isfinite
from pathlib import Path


def _geometry(row):
    ego, lead = row['ego'], row['lead']
    angle = ego['yaw_deg'] * pi / 180
    forward = (cos(angle), sin(angle))
    left = (-forward[1], forward[0])
    origin = ego['position_m']
    project = lambda point, axis: (point[0] - origin[0])*axis[0] + (point[1] - origin[1])*axis[1]
    ego_front = max(project(v, forward) for v in ego['body_corners_m'])
    lead_rear = min(project(v, forward) for v in lead['body_corners_m'])
    lateral = abs(project(lead['position_m'], left))
    gap_m = lead_rear - ego_front
    speed = ego['speed_mps']
    closing = speed - lead['speed_mps']
    return {'longitudinal_body_gap_m': gap_m,
            'lateral_center_offset_m': lateral,
            'headway_s': gap_m / speed if speed > .1 else None,
            'closing_ttc_s': gap_m / closing if closing > .1 and gap_m > 0 else None}


def derive(source_path):
    path = Path(source_path)
    raw = path.read_bytes()
    if not raw:
        raise ValueError('Missing original following source')
    source_sha = sha256(raw).hexdigest()
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows) < 3:
        raise ValueError('Following event detection needs original frame history')
    candidates = []
    seen = set()
    previous = None
    for row in rows:
        frame, time_s = row['frame'], row['time_s']
        if previous is not None and (frame != previous[0] + 1 or
                                     abs(time_s - previous[1] - .05) > 1e-4):
            raise ValueError('Following event source not continuous at 20 Hz')
        previous = frame, time_s
        geometry = _geometry(row)
        phase = row['requested_phase']
        speed = row['ego']['speed_mps']
        limit = row.get('map_speed_limit_kmh')
        if (limit is not None and isfinite(float(limit)) and float(limit) > 0
                and speed > float(limit)/3.6 + .5 and 'speed' not in seen):
            candidates.append((row, 'speed', 'measured speed above map limit by 0.5 m/s engineering margin'))
            seen.add('speed')
        if (phase in ('first_closing_request', 'second_closing_request')
                and geometry['lateral_center_offset_m'] < 3
                and geometry['longitudinal_body_gap_m'] > 0
                and geometry['headway_s'] is not None
                and geometry['headway_s'] < 1.5 and phase not in seen):
            candidates.append((row, 'too_close',
                               'original body headway under 1.5 s engineering review trigger'))
            seen.add(phase)
        if (geometry['lateral_center_offset_m'] < 3
                and geometry['closing_ttc_s'] is not None
                and geometry['closing_ttc_s'] < 2
                and 'hazard' not in seen):
            candidates.append((row, 'hazard',
                               'positive closing body TTC under 2 s engineering review trigger'))
            seen.add('hazard')
    result = []
    for index, (row, category, trigger) in enumerate(candidates):
        event = {'frame': row['frame'], 'category': category,
                 'occurrence_id': 'native-candidate-' + str(index),
                 'source_ref': path.name, 'source_sha256': source_sha,
                 'review_status': 'unreviewed_native_geometry_candidate',
                 'engineering_trigger': trigger}
        if category == 'hazard':
            event['target_type'] = 'vehicle'
        result.append(event)
    return result


def write_candidates(source_path, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Retain prior event candidate source')
    events = derive(source_path)
    destination.write_text(json.dumps(events, indent=2) + '\n')
    return events
