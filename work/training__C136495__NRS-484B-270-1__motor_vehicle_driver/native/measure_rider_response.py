"""Source-bound rider proximity and response timing CPU diagnostic."""

import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(folder):
    folder = Path(folder)
    manifest = json.loads((folder / 'sources.json').read_text())
    if manifest.get('kind') != 'synthetic_cpu_rider_response':
        raise ValueError('Synthetic provenance differs')
    for name in ('geometry.json', 'actors.jsonl'):
        if digest(folder / name) != manifest['sha256'][name]:
            raise ValueError('Source hash differs: ' + name)
    geometry = json.loads((folder / 'geometry.json').read_text())
    if geometry != {'ego_width_m': 1.8, 'rider_width_m': 0.6, 'rider_type': 'bicycle'}:
        raise ValueError('Rider geometry differs')
    rows = [json.loads(line) for line in (folder / 'actors.jsonl').read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Expected 600 Native frames')
    near_frames = 0
    first_ego_lateral_change = None
    first_rider_speed_drop = None
    min_gap = None
    for i, row in enumerate(rows):
        if row['frame'] != 1000 + i or abs(row['time_s'] - i / 20) > 1e-8:
            raise ValueError('Native frame/time join differs')
        if set(row['actors']) != {'ego', 'rider'}:
            raise ValueError('Ego/rider source missing')
        ego, rider = row['actors']['ego'], row['actors']['rider']
        if not isinstance(ego['y_m'], (int, float)) or not isinstance(rider['y_m'], (int, float)):
            raise ValueError('Lateral source missing')
        gap = abs(rider['y_m'] - ego['y_m']) - (geometry['ego_width_m'] + geometry['rider_width_m']) / 2
        min_gap = gap if min_gap is None else min(min_gap, gap)
        near_frames += gap < 0.5
        if abs(ego['y_m']) > 0.01 and first_ego_lateral_change is None:
            first_ego_lateral_change = row['frame']
        if rider['speed_mps'] < 3.9 and first_rider_speed_drop is None:
            first_rider_speed_drop = row['frame']
    return {
        'source_kind': manifest['kind'], 'source_sha256': manifest['sha256'],
        'frame_count': 600, 'rate_hz': 20, 'near_frames': near_frames,
        'min_lateral_surface_gap_m': round(min_gap, 6),
        'first_ego_lateral_change_frame': first_ego_lateral_change,
        'first_rider_speed_drop_frame': first_rider_speed_drop,
        'rider_lawful_status': 'unresolved', 'driver_intent': 'unresolved',
        'causal_interference': 'unresolved', 'physical_native_verified': False,
        'legal_verdict_claimed': False,
    }
