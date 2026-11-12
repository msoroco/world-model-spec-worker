"""Capture original ego/lead body and speed samples without legal event labels."""

import json
from math import hypot, isfinite
from pathlib import Path


def _actor(actor):
    transform = actor.get_transform()
    location = transform.location
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(transform)
    corners = [[float(vertex.x), float(vertex.y), float(vertex.z)]
               for vertex in vertices]
    if len(corners) != 8:
        raise ValueError('Expected eight original vehicle body corners')
    return {
        'actor_id': int(actor.id),
        'position_m': [float(location.x), float(location.y), float(location.z)],
        'yaw_deg': float(transform.rotation.yaw),
        'velocity_mps': [float(velocity.x), float(velocity.y), float(velocity.z)],
        'speed_mps': hypot(float(velocity.x), float(velocity.y)),
        'body_corners_m': corners,
    }


def sample(frame, time_s, ego, lead, *, requested_phase, map_speed_limit_kmh=None):
    if type(frame) is not int or frame < 0 or not isfinite(float(time_s)):
        raise ValueError('Invalid original frame identity')
    if ego.id == lead.id:
        raise ValueError('Subject and lead identities must differ')
    row = {'frame': frame, 'time_s': float(time_s),
           'ego': _actor(ego), 'lead': _actor(lead),
           'requested_phase': str(requested_phase),
           'map_speed_limit_kmh': map_speed_limit_kmh,
           'speed_limit_sign_physically_verified': False,
           'too_close_legal_judgment': None,
           'immediate_hazard_legal_judgment': None}
    return row


def write_samples(path, rows):
    path = Path(path)
    if path.exists():
        raise ValueError('Retain prior original following samples')
    if not rows:
        raise ValueError('No original following samples')
    previous = None
    for row in rows:
        if previous is not None and (
                row['frame'] != previous['frame'] + 1 or
                abs(row['time_s'] - previous['time_s'] - .05) > 1e-4):
            raise ValueError('Following source not continuous at 20 Hz')
        previous = row
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                            for row in rows))
    return path
