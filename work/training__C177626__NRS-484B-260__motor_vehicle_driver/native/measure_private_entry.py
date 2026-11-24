"""Source-bound CPU diagnostic of private-way entry and highway arrival order."""

import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def first_nonnegative(rows, actor, coordinate):
    for row in rows:
        if row['actors'][actor][coordinate] >= 0:
            return row['frame']
    return None


def measure(folder):
    folder = Path(folder)
    source = json.loads((folder / 'sources.json').read_text())
    if source.get('kind') != 'synthetic_cpu_private_way_entry':
        raise ValueError('Synthetic provenance differs')
    for name in ('geometry.json', 'actors.jsonl'):
        if digest(folder / name) != source['sha256'][name]:
            raise ValueError('Source hash differs: ' + name)
    geometry = json.loads((folder / 'geometry.json').read_text())
    if geometry != {'private_way': 'y_negative_to_highway', 'highway': 'x_negative_to_positive',
                    'conflict_x_m': 0.0, 'conflict_y_m': 0.0, 'highway_vehicle_ids': ['approach_1', 'approach_2']}:
        raise ValueError('Private-way/highway geometry differs')
    rows = [json.loads(line) for line in (folder / 'actors.jsonl').read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Expected 600 Native frames')
    for i, row in enumerate(rows):
        if row['frame'] != 1000 + i or abs(row['time_s'] - i / 20) > 1e-8:
            raise ValueError('Native frame/time join differs')
        if set(row['actors']) != {'ego', 'approach_1', 'approach_2'}:
            raise ValueError('Approaching vehicle source missing')
        if row['actors']['ego']['x_m'] != 0.0:
            raise ValueError('Ego private-way alignment differs')
        for actor in geometry['highway_vehicle_ids']:
            if row['actors'][actor]['y_m'] != 0.0:
                raise ValueError('Highway vehicle alignment differs')
    ego = first_nonnegative(rows, 'ego', 'y_m')
    arrivals = {actor: first_nonnegative(rows, actor, 'x_m') for actor in geometry['highway_vehicle_ids']}
    if ego is None or any(value is None for value in arrivals.values()):
        raise ValueError('Conflict-point arrival missing')
    return {'source_kind': source['kind'], 'source_sha256': source['sha256'], 'frame_count': 600, 'rate_hz': 20,
            'ego_conflict_arrival_frame': ego, 'highway_arrival_frames': arrivals,
            'highway_vehicles_before_ego': sum(value < ego for value in arrivals.values()),
            'highway_vehicle_count': len(arrivals), 'right_of_way_verdict': 'unresolved',
            'physical_native_verified': False, 'legal_verdict_claimed': False}
