"""Source-bound CPU diagnostic of a flagger stop signal and line crossing."""

import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(folder):
    folder = Path(folder)
    source = json.loads((folder / 'sources.json').read_text())
    if source.get('kind') != 'synthetic_cpu_flagger_stop':
        raise ValueError('Synthetic provenance differs')
    for name in ('zone.json', 'signal.jsonl', 'ego.jsonl'):
        if digest(folder / name) != source['sha256'][name]:
            raise ValueError('Source hash differs: ' + name)
    zone = json.loads((folder / 'zone.json').read_text())
    if zone != {'kind': 'marked_temporary_traffic_control', 'stop_line_x_m': 0.0,
                'approach': 'x_negative_to_positive', 'signal_governs_approach': True}:
        raise ValueError('Temporary zone geometry differs')
    signals = [json.loads(line) for line in (folder / 'signal.jsonl').read_text().splitlines()]
    ego = [json.loads(line) for line in (folder / 'ego.jsonl').read_text().splitlines()]
    if len(signals) != 600 or len(ego) != 600:
        raise ValueError('Expected 600 Native frames per source')
    stop_frames = stopped_during_stop = 0
    first_stop = first_release = first_cross = None
    crossing_signal = None
    for i, (signal, vehicle) in enumerate(zip(signals, ego)):
        if any(row['frame'] != 1000 + i or abs(row['time_s'] - i / 20) > 1e-8 for row in (signal, vehicle)):
            raise ValueError('Native signal/ego frame join differs')
        if signal.get('role') != 'flagger' or signal.get('governs_ego') is not True:
            raise ValueError('Governing flagger source missing')
        if vehicle.get('actor_kind') != 'motorcycle_or_moped':
            raise ValueError('Motorcycle source missing')
        state = signal['indication']
        if state not in ('stop', 'release'):
            raise ValueError('Flagger indication differs')
        if state == 'stop':
            stop_frames += 1
            stopped_during_stop += vehicle['speed_mps'] == 0
            first_stop = signal['frame'] if first_stop is None else first_stop
        elif first_stop is not None and first_release is None:
            first_release = signal['frame']
        if first_cross is None and vehicle['x_m'] >= zone['stop_line_x_m']:
            first_cross = vehicle['frame']
            crossing_signal = state
    if first_stop is None or first_release is None or first_cross is None:
        raise ValueError('Signal or crossing event missing')
    return {'source_kind': source['kind'], 'source_sha256': source['sha256'],
            'frame_count': 600, 'rate_hz': 20, 'stop_signal_frames': stop_frames,
            'stopped_during_stop_frames': stopped_during_stop,
            'first_stop_frame': first_stop, 'first_release_frame': first_release,
            'first_stop_line_cross_frame': first_cross, 'indication_at_crossing': crossing_signal,
            'flagger_authorization_verified': False, 'physical_zone_designation_verified': False,
            'visual_signal_delivery_verified': False, 'physical_native_verified': False,
            'legal_verdict_claimed': False}
