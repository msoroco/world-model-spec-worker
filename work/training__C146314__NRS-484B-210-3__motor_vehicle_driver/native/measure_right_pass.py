"""Source-bound CPU diagnostic of right-pass timing and paved footprint."""

import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(folder):
    folder = Path(folder)
    sources = json.loads((folder / 'sources.json').read_text())
    if sources.get('kind') != 'synthetic_cpu_right_pass':
        raise ValueError('Synthetic provenance differs')
    for name in ('geometry.json', 'actors.jsonl'):
        if digest(folder / name) != sources['sha256'][name]:
            raise ValueError('Source hash differs: ' + name)
    geometry = json.loads((folder / 'geometry.json').read_text())
    if geometry != {'paved_y_m': [-4.0, 4.0], 'right_shoulder_y_m': [4.0, 6.0], 'right_shoulder_paved': False,
                    'ego_width_m': 1.8, 'ego_length_m': 4.5, 'lead_length_m': 4.5}:
        raise ValueError('Paved-surface geometry differs')
    rows = [json.loads(line) for line in (folder / 'actors.jsonl').read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Expected 600 Native frames')
    pass_frames = right_pass_frames = off_paved_frames = concurrent_frames = 0
    first_pass = last_pass = None
    for i, row in enumerate(rows):
        if row['frame'] != 1000 + i or abs(row['time_s'] - i / 20) > 1e-8:
            raise ValueError('Native frame/time join differs')
        if set(row['actors']) != {'ego', 'lead'}:
            raise ValueError('Ego/lead source missing')
        ego, lead = row['actors']['ego'], row['actors']['lead']
        half_total_length = (geometry['ego_length_m'] + geometry['lead_length_m']) / 2
        passing = abs(ego['x_m'] - lead['x_m']) <= half_total_length
        right = ego['y_m'] > lead['y_m']
        off = ego['y_m'] + geometry['ego_width_m'] / 2 > geometry['paved_y_m'][1] or ego['y_m'] - geometry['ego_width_m'] / 2 < geometry['paved_y_m'][0]
        pass_frames += passing
        right_pass_frames += passing and right
        off_paved_frames += off
        concurrent_frames += passing and right and off
        if passing:
            first_pass = row['frame'] if first_pass is None else first_pass
            last_pass = row['frame']
    return {'source_kind': sources['kind'], 'source_sha256': sources['sha256'], 'frame_count': 600, 'rate_hz': 20,
            'pass_overlap_frames': pass_frames, 'right_pass_overlap_frames': right_pass_frames,
            'off_paved_footprint_frames': off_paved_frames,
            'right_pass_and_off_paved_frames': concurrent_frames,
            'first_pass_overlap_frame': first_pass, 'last_pass_overlap_frame': last_pass,
            'required_off_pavement_for_pass': 'unresolved', 'physical_native_verified': False,
            'legal_verdict_claimed': False}
