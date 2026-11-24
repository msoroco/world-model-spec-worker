"""Saved-source diagonal timing diagnostic; never a physical or legal verdict."""
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE = 20
DEVICE = 'c109166-diagonal-crossing-head'


def _read(path, expected):
    path = Path(path)
    if not path.is_file():
        raise ValueError('required saved source missing: ' + path.name)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('saved source hash mismatch: ' + path.name)
    return raw


def _rows(raw, name):
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows) != FRAMES:
        raise ValueError('full 600-frame ' + name + ' source required')
    for index, row in enumerate(rows):
        if row.get('frame') != index or row.get('time_s') != index / RATE:
            raise ValueError(name + ' frame/time join failed')
    return rows


def finalize(folder, hashes, case):
    if case not in ('controlled_1', 'controlled_2'):
        raise ValueError('unknown exact case')
    required = {'pedestrian.jsonl', 'device.jsonl', 'context.json'}
    if set(hashes) != required:
        raise ValueError('all saved source hashes required')
    folder = Path(folder)
    raw = {name: _read(folder / name, hashes[name]) for name in required}
    context = json.loads(raw['context.json'])
    if (context.get('source_kind') != 'synthetic_scene_request' or
            context.get('device_id') != DEVICE or
            context.get('governs_diagonal_movement') is not True or
            context.get('official_device_original_review') != 'pending' or
            context.get('statutory_exception_review') != 'pending'):
        raise ValueError('diagonal device authority/context unestablished')
    people = _rows(raw['pedestrian.jsonl'], 'pedestrian')
    devices = _rows(raw['device.jsonl'], 'device')
    centers = []
    for index, (person, device) in enumerate(zip(people, devices)):
        center = person.get('pedestrian_xy_m')
        body = person.get('footprint_xy_m')
        if (person.get('source_kind') != 'synthetic_scene_request' or
                not isinstance(center, list) or len(center) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in center) or
                not isinstance(body, list) or len(body) != 4 or
                any(not isinstance(point, list) or len(point) != 2 or
                    any(type(v) not in (int, float) or not math.isfinite(v) for v in point)
                    for point in body)):
            raise ValueError('pedestrian full-body source invalid')
        if any(abs(sum(point[k] for point in body) / 4 - center[k]) > 1e-8
               for k in (0, 1)):
            raise ValueError('pedestrian footprint/center mismatch')
        if abs(center[0] - center[1]) > .05:
            raise ValueError('pedestrian left requested diagonal corridor')
        if (device.get('device_id') != DEVICE or
                device.get('diagonal_movement_governed') is not True or
                device.get('source_kind') != 'synthetic_scene_request' or
                device.get('device_state') not in ('diagonal_walk', 'diagonal_dont_walk')):
            raise ValueError('governing diagonal device source invalid')
        if index and math.dist(center, centers[-1]) > .08:
            raise ValueError('pedestrian motion discontinuity')
        centers.append(center)
    if centers[100] != [-6.0, -6.0] or centers[340] != [6.0, 6.0]:
        raise ValueError('requested diagonal endpoints changed')
    first = devices[100]['device_state']
    expected = 'diagonal_walk' if case == 'controlled_1' else 'diagonal_dont_walk'
    if first != expected:
        raise ValueError('first-entry requested instruction differs')
    distance = sum(math.dist(a, b) for a, b in zip(centers, centers[1:]))
    return {'format': 'c109166-287-1e-saved-source-diagnostic-v1', 'case': case,
            'frames': FRAMES, 'duration_s': FRAMES / RATE,
            'requested_first_entry_frame': 100, 'requested_first_entry_state': first,
            'path_length_m': round(distance, 6), 'source_sha256': hashes,
            'official_device_verified': False, 'diagonal_authorization_verified': False,
            'exception_484b290_resolved': False, 'physical_crossing_observed': False,
            'legal_verdict': None}
