"""Exact 30-second diagonal authorization request; no official-device finding."""
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE = 20
DEVICE = 'c109166-planned-diagonal-head'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def requested(case):
    if case not in ('probe_01', 'probe_02'):
        raise ValueError('Unknown diagonal authorization case')
    authorized = case == 'probe_01'
    rows = []
    for frame in range(FRAMES):
        fraction = max(0, min(1, (frame - 100) / 240))
        center = [-6 + 12 * fraction, -6 + 12 * fraction]
        rows.append({'frame': frame, 'time_s': frame / RATE,
                     'pedestrian_xy_m': center,
                     'footprint_xy_m': [[center[0] + dx, center[1] + dy]
                                        for dx, dy in ((-.2, -.2), (-.2, .2),
                                                       (.2, -.2), (.2, .2))],
                     'device_id': DEVICE,
                     'requested_diagonal_authorization': authorized,
                     'official_device_verified': False,
                     'diagonal_authorization_originally_reviewed': False,
                     'exception_484b290_reviewed': False,
                     'source_kind': 'synthetic_scene_request',
                     'legal_verdict': None})
    return rows


def measure(source, context):
    source, context = Path(source), Path(context)
    if not source.is_file() or not context.is_file():
        raise ValueError('Diagonal source or context missing')
    state = json.loads(context.read_text())
    if (state.get('source_kind') != 'synthetic_scene_request' or
            state.get('device_id') != DEVICE or
            state.get('official_device_verified') is not False or
            state.get('exception_484b290_reviewed') is not False):
        raise ValueError('Device/context authority changed')
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    if len(rows) != FRAMES:
        raise ValueError('Full 600-frame diagonal source required')
    previous = None
    path_length = 0.0
    authorizations = set()
    for index, row in enumerate(rows):
        center, footprint = row.get('pedestrian_xy_m'), row.get('footprint_xy_m')
        if (row.get('frame') != index or row.get('time_s') != index / RATE or
                row.get('device_id') != DEVICE or
                row.get('source_kind') != 'synthetic_scene_request' or
                row.get('official_device_verified') is not False or
                row.get('diagonal_authorization_originally_reviewed') is not False or
                row.get('exception_484b290_reviewed') is not False or
                row.get('legal_verdict') is not None or
                type(row.get('requested_diagonal_authorization')) is not bool):
            raise ValueError('Frame/device/authority identity changed')
        if (not isinstance(center, list) or len(center) != 2 or
                not all(type(v) in (int, float) and math.isfinite(v) for v in center) or
                not isinstance(footprint, list) or len(footprint) != 4 or
                any(not isinstance(point, list) or len(point) != 2 or
                    not all(type(v) in (int, float) and math.isfinite(v) for v in point)
                    for point in footprint)):
            raise ValueError('Full pedestrian center/footprint missing')
        if any(abs(sum(point[k] for point in footprint) / 4 - center[k]) > 1e-8
               for k in (0, 1)):
            raise ValueError('Pedestrian center/footprint disagreement')
        if abs(center[0] - center[1]) > .05:
            raise ValueError('Pedestrian left authored diagonal corridor')
        if previous is not None:
            step = math.dist(previous, center)
            if step > .08:
                raise ValueError('Pedestrian motion discontinuity')
            path_length += step
        previous = center
        if 100 <= index < 340:
            authorizations.add(row['requested_diagonal_authorization'])
    if len(authorizations) != 1 or rows[100]['pedestrian_xy_m'] != [-6, -6] or \
            rows[340]['pedestrian_xy_m'] != [6, 6] or not 16.9 < path_length < 17.1:
        raise ValueError('Diagonal route/authorization changed')
    return {'format': 'c109166-1d-diagonal-authorization-measurement-v1',
            'frames': FRAMES, 'duration_s': 30,
            'first_entry_frame': 100, 'full_crossing_end_frame': 340,
            'path_length_m': round(path_length, 6),
            'requested_authorization_at_entry': rows[100]['requested_diagonal_authorization'],
            'requested_authorization_during_crossing': next(iter(authorizations)),
            'source_sha256': {source.name: sha(source), context.name: sha(context)},
            'official_device_verified': False,
            'physical_crossing_observed': False,
            'exception_484b290_resolved': False,
            'legal_verdict_claimed': False}
