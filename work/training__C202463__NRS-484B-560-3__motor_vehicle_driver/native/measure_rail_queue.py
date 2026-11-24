"""Source-bound CPU diagnostic of rail-stop position and queue arrangement."""

import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(folder):
    folder = Path(folder)
    source = json.loads((folder / 'sources.json').read_text())
    if source.get('kind') != 'synthetic_cpu_rail_stop_queue':
        raise ValueError('Synthetic provenance differs')
    for name in ('geometry.json', 'gate.jsonl', 'actors.jsonl'):
        if digest(folder / name) != source['sha256'][name]:
            raise ValueError('Source hash differs: ' + name)
    geo = json.loads((folder / 'geometry.json').read_text())
    if geo != {'rail_crossing_x_m': 0.0, 'right_highway_edge_y_m': 3.5,
               'total_marked_lanes': 2, 'vehicle_width_m': 1.8, 'vehicle_length_m': 4.5}:
        raise ValueError('Rail highway geometry differs')
    gate = [json.loads(x) for x in (folder / 'gate.jsonl').read_text().splitlines()]
    actors = [json.loads(x) for x in (folder / 'actors.jsonl').read_text().splitlines()]
    if len(gate) != len(actors) or len(gate) != 600:
        raise ValueError('Expected 600 Native frames per source')
    stopped_gate_frames = abreast_frames = 0
    min_right_edge_gap = None
    for i, (signal, row) in enumerate(zip(gate, actors)):
        if any(item['frame'] != 1000 + i or abs(item['time_s'] - i / 20) > 1e-8 for item in (signal, row)):
            raise ValueError('Native gate/actor frame join differs')
        if signal.get('kind') != 'rail_gate' or signal.get('indication') not in ('stop', 'release'):
            raise ValueError('Rail gate indication missing')
        if set(row['actors']) != {'ego', 'other'}:
            raise ValueError('Ego/other vehicle source missing')
        ego, other = row['actors']['ego'], row['actors']['other']
        if signal['indication'] == 'stop' and ego['speed_mps'] == 0 and other['speed_mps'] == 0:
            stopped_gate_frames += 1
            right_gap = geo['right_highway_edge_y_m'] - (ego['y_m'] + geo['vehicle_width_m'] / 2)
            min_right_edge_gap = right_gap if min_right_edge_gap is None else min(min_right_edge_gap, right_gap)
            longitudinal_overlap = abs(ego['x_m'] - other['x_m']) < geo['vehicle_length_m']
            lateral_separate = abs(ego['y_m'] - other['y_m']) >= geo['vehicle_width_m']
            abreast_frames += longitudinal_overlap and lateral_separate
    return {'source_kind': source['kind'], 'source_sha256': source['sha256'],
            'frame_count': 600, 'rate_hz': 20, 'stopped_during_gate_stop_frames': stopped_gate_frames,
            'minimum_right_edge_gap_m': round(min_right_edge_gap, 6) if min_right_edge_gap is not None else None,
            'abreast_two_queue_frames': abreast_frames, 'total_marked_lanes': geo['total_marked_lanes'],
            'stopping_requirement_authority_verified': False, 'rightmost_possible_judgment': 'unresolved',
            'two_lanes_legal_judgment': 'unresolved', 'physical_native_verified': False,
            'legal_verdict_claimed': False}
