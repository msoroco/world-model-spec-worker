"""Source-bound CPU diagnostic of complete consecutive caravan clear spaces."""

import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(folder):
    folder = Path(folder)
    source = json.loads((folder / 'sources.json').read_text())
    if source.get('kind') != 'synthetic_cpu_caravan_space':
        raise ValueError('Synthetic provenance differs')
    for name in ('composition.json', 'actors.jsonl'):
        if digest(folder / name) != source['sha256'][name]:
            raise ValueError('Source hash differs: ' + name)
    composition = json.loads((folder / 'composition.json').read_text())
    if composition != {'ordered_group': ['lead', 'ego_combination', 'rear'],
                       'length_m': {'lead': 4.5, 'ego_combination': 9.0, 'rear': 4.5},
                       'ego_tows_trailer': True, 'potential_entrant_length_m': 6.0}:
        raise ValueError('Combination extent source differs')
    rows = [json.loads(line) for line in (folder / 'actors.jsonl').read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Expected 600 Native frames')
    gaps = {'lead_to_ego_combination': [], 'ego_combination_to_rear': []}
    for i, row in enumerate(rows):
        if row['frame'] != 1000 + i or abs(row['time_s'] - i / 20) > 1e-8:
            raise ValueError('Native frame/time join differs')
        actors = row.get('actors', {})
        if set(actors) != {'lead', 'ego_combination', 'rear', 'potential_entrant'}:
            raise ValueError('Complete group/entrant source missing')
        if any(actors[name]['speed_mps'] != 6.0 for name in ('lead', 'ego_combination', 'rear')):
            raise ValueError('Group speed source differs')
        for front, back, key in (('lead', 'ego_combination', 'lead_to_ego_combination'),
                                 ('ego_combination', 'rear', 'ego_combination_to_rear')):
            gap = (actors[front]['x_m'] - composition['length_m'][front] / 2) - (actors[back]['x_m'] + composition['length_m'][back] / 2)
            if gap < 0:
                raise ValueError('Consecutive group order overlaps')
            gaps[key].append(gap)
    return {'source_kind': source['kind'], 'source_sha256': source['sha256'],
            'frame_count': 600, 'rate_hz': 20,
            'minimum_clear_gap_m': {key: round(min(value), 6) for key, value in gaps.items()},
            'potential_entrant_length_m': composition['potential_entrant_length_m'],
            'minimum_static_length_surplus_m': {key: round(min(value) - composition['potential_entrant_length_m'], 6) for key, value in gaps.items()},
            'caravan_membership_verified': False, 'outside_business_district_verified': False,
            'entry_without_danger_judgment': 'unresolved', 'physical_native_verified': False,
            'legal_verdict_claimed': False}
