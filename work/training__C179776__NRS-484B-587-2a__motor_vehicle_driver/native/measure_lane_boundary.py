"""Source-bound CPU diagnostic of marked-lane and paved-shoulder footprint."""

import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(folder):
    folder = Path(folder)
    source = json.loads((folder / 'sources.json').read_text())
    if source.get('kind') != 'synthetic_cpu_controlled_access_lane':
        raise ValueError('Synthetic provenance differs')
    for name in ('geometry.json', 'ego.jsonl'):
        if digest(folder / name) != source['sha256'][name]:
            raise ValueError('Source hash differs: ' + name)
    geometry = json.loads((folder / 'geometry.json').read_text())
    if geometry != {'controlled_access': True, 'marked_lanes_y_m': [[-4.0, 0.0], [0.0, 4.0]],
                    'paved_shoulder_y_m': [4.0, 6.0], 'ego_width_m': 1.8}:
        raise ValueError('Marked-lane geometry differs')
    rows = [json.loads(line) for line in (folder / 'ego.jsonl').read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Expected 600 Native frames')
    outside = shoulder = 0
    first_outside = None
    for i, row in enumerate(rows):
        if row['frame'] != 1000 + i or abs(row['time_s'] - i / 20) > 1e-8:
            raise ValueError('Native frame/time join differs')
        if row.get('actor_kind') != 'ordinary_motor_vehicle':
            raise ValueError('Vehicle source missing')
        low, high = row['y_m'] - 0.9, row['y_m'] + 0.9
        is_outside = low < -4.0 or high > 4.0
        is_shoulder = low >= 4.0 and high <= 6.0
        outside += is_outside
        shoulder += is_shoulder
        if is_outside and first_outside is None:
            first_outside = row['frame']
    return {'source_kind': source['kind'], 'source_sha256': source['sha256'],
            'frame_count': 600, 'rate_hz': 20, 'footprint_outside_marked_lanes_frames': outside,
            'footprint_fully_on_paved_shoulder_frames': shoulder, 'first_outside_frame': first_outside,
            'emergency_required': 'unresolved', 'subsection_3_authorization': 'unresolved',
            'special_vehicle_and_sign_exception': 'unresolved', 'physical_native_verified': False,
            'legal_verdict_claimed': False}
