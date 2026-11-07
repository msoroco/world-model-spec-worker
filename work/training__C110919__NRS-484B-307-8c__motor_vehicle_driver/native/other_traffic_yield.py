"""CPU join for a lawful other-traffic conflict and the ego turn event."""
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(ego_source: Path, ego_sha256: str, traffic_source: Path,
            traffic_sha256: str) -> dict:
    if sha(ego_source) != ego_sha256 or sha(traffic_source) != traffic_sha256:
        raise ValueError('Saved source bytes differ')
    ego = json.loads(ego_source.read_text())
    traffic = json.loads(traffic_source.read_text())
    if ego.get('source_kind') != 'synthetic_cpu' or traffic.get('source_kind') != 'synthetic_cpu':
        raise ValueError('This CPU proof requires synthetic saved sources')
    if ego.get('case') != traffic.get('case'):
        raise ValueError('Traffic history belongs to another case')
    rows = traffic.get('frames')
    ego_rows = ego.get('frames')
    if not isinstance(rows, list) or len(rows) != 480 or not isinstance(ego_rows, list) or len(ego_rows) != 480:
        raise ValueError('Full 480-frame histories are required')
    occupied = []
    entry = None
    actor = traffic.get('actor_id')
    if not isinstance(actor, int) or actor <= 0:
        raise ValueError('Other-traffic actor identity is missing')
    for i, (car, other) in enumerate(zip(ego_rows, rows)):
        if car.get('frame') != i or car.get('video_frame') != i or car.get('native_frame') != i:
            raise ValueError('Ego frame join differs')
        if other.get('frame') != i or other.get('native_frame') != i or other.get('video_frame') != i:
            raise ValueError('Other-traffic frame join differs')
        if abs(other.get('time_s', -1) - i / 20) > 1e-8 or abs(car.get('time_s', -1) - i / 20) > 1e-8:
            raise ValueError('Frame timestamp differs')
        if other.get('actor_id') != actor or other.get('lawful_intersection_user') is not True:
            raise ValueError('Other-traffic identity or lawful-use source is missing')
        if type(other.get('conflict_occupied')) is not bool:
            raise ValueError('Other-traffic occupancy source is missing')
        if other['conflict_occupied']:
            occupied.append(i)
        if car.get('ego_turn_entered') is True and entry is None:
            entry = i
    if not occupied or entry is None:
        raise ValueError('Traffic conflict or ego turn event is missing')
    last = max(occupied)
    if entry <= last:
        raise ValueError('Ego entered before other traffic cleared')
    return {'case': ego['case'], 'ego_source_sha256': ego_sha256,
            'traffic_source_sha256': traffic_sha256, 'frames': 480,
            'other_actor_id': actor, 'turn_entry_frame': entry,
            'last_other_traffic_conflict_frame': last,
            'other_traffic_clearance_s': round((entry-last)/20, 3),
            'yielded_to_other_traffic_in_synthetic_source': True,
            'original_native_observed': False, 'legal_verdict': None}
