"""Saved, frame-aligned traffic comparison; no legal necessity inference."""
from __future__ import annotations

import json
import math
from pathlib import Path

IDENTITY_KEYS = ('map_sha256', 'route_sha256', 'controller_sha256', 'candidate_id', 'seed')


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing saved motion source: ' + path.name)
    result = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(result) != 480:
        raise ValueError('Controlled motion source must contain 480 frames')
    return result


def polygon(value):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError('Motion footprint must have four vertices')
    if any(not isinstance(p, list) or len(p) != 2 or
           any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
               for v in p) for p in value):
        raise ValueError('Motion footprint has invalid coordinates')
    center = (sum(p[0] for p in value) / 4, sum(p[1] for p in value) / 4)
    ordered = sorted(value, key=lambda p: math.atan2(p[1] - center[1], p[0] - center[0]))
    turns = []
    for i in range(4):
        a, b, c = ordered[i], ordered[(i + 1) % 4], ordered[(i + 2) % 4]
        turns.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
    if min(turns) <= 1e-8:
        raise ValueError('Motion footprint is not a convex four-vertex body')
    return ordered


def overlap(a, b):
    """Separating-axis test on Native horizontal footprint polygons."""
    for shape in (a, b):
        for index in range(4):
            p, q = shape[index], shape[(index + 1) % 4]
            axis = (-(q[1] - p[1]), q[0] - p[0])
            if math.hypot(*axis) < 1e-8:
                raise ValueError('Degenerate motion footprint')
            ap = [v[0] * axis[0] + v[1] * axis[1] for v in a]
            bp = [v[0] * axis[0] + v[1] * axis[1] for v in b]
            if max(ap) < min(bp) or max(bp) < min(ap):
                return False
    return True


def inspect(absent_dir, present_dir):
    absent_dir, present_dir = Path(absent_dir), Path(present_dir)
    absent_identity = json.loads((absent_dir / 'capture_identity.json').read_text())
    present_identity = json.loads((present_dir / 'capture_identity.json').read_text())
    if any(absent_identity.get(key) != present_identity.get(key) or
           absent_identity.get(key) in (None, '') for key in IDENTITY_KEYS):
        raise ValueError('Controlled pair construction identity differs')
    if absent_identity.get('actor_present') is not False or present_identity.get('actor_present') is not True:
        raise ValueError('Controlled pair actor polarity differs')
    absent = rows(absent_dir / 'native_samples.jsonl')
    present = rows(present_dir / 'native_samples.jsonl')
    actor = rows(present_dir / 'other_actor_history.jsonl')
    if (absent_dir / 'other_actor_history.jsonl').exists():
        raise ValueError('Absent case unexpectedly has actor history')
    if any(a.get('video_frame') != i or p.get('video_frame') != i or
           not isinstance(a.get('time_s'), (int, float)) or
           not isinstance(p.get('time_s'), (int, float)) or
           abs(a['time_s'] - p['time_s']) > .026 or
           p.get('native_frame') != c.get('native_frame') or
           abs(p['time_s'] - c.get('time_s', -999)) > .001
           for i, (a, p, c) in enumerate(zip(absent, present, actor))):
        raise ValueError('Controlled pair original frame/time join differs')
    if any(abs(absent[0]['native_center_xy_m'][j] - present[0]['native_center_xy_m'][j]) > .1
           for j in (0, 1)) or abs(absent[0]['observed_speed_mps'] - present[0]['observed_speed_mps']) > .2:
        raise ValueError('Controlled pair initial ego state differs')
    if any(not isinstance(r.get('observed_speed_mps'), (int, float)) or
           not math.isfinite(r['observed_speed_mps']) or
           not isinstance(r.get('observed_velocity_xy_mps'), list) or
           len(r['observed_velocity_xy_mps']) != 2 or
           any(not isinstance(v, (int, float)) or not math.isfinite(v)
               for v in r['observed_velocity_xy_mps'])
           for r in absent + present):
        raise ValueError('Controlled pair ego velocity readback differs')
    if any(not isinstance(r.get('velocity_xy_mps'), list) or len(r['velocity_xy_mps']) != 2 or
           any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in r['velocity_xy_mps'])
           for r in actor):
        raise ValueError('Controlled pair actor velocity readback differs')
    hypothetical = []
    observed = []
    for index, (a, p, c) in enumerate(zip(absent, present, actor)):
        actor_body = polygon(c.get('body_xy_m'))
        if overlap(polygon(a.get('native_body_xy_m')), actor_body):
            hypothetical.append(index)
        if overlap(polygon(p.get('native_body_xy_m')), actor_body):
            observed.append(index)
    onset = [i for i, row in enumerate(present) if row.get('conflict_brake_override') is True and
             (i == 0 or present[i - 1].get('conflict_brake_override') is not True)]
    if (len(onset) != 1 or onset[0] == 0 or
            present[onset[0]].get('applied_brake', 0) <= 0 or
            present[onset[0]]['observed_speed_mps'] >= present[onset[0] - 1]['observed_speed_mps']):
        raise ValueError('Controlled pair has no measured conflict brake response')
    if not hypothetical or observed or onset[0] >= hypothetical[0]:
        raise ValueError('Controlled no-brake path does not isolate avoided overlap')
    return {'format': 'lvmc-controlled-traffic-pair-v1',
            'common_identity': {key: absent_identity[key] for key in IDENTITY_KEYS},
            'frames': len(absent), 'brake_onset_video_frame': onset[0],
            'absent_ego_present_actor_overlap_frames': hypothetical,
            'present_ego_present_actor_overlap_frames': observed,
            'interpretation': 'saved path overlap diagnostic only; physical collision and statutory necessity require independent review'}
