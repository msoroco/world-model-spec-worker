"""Original Native actor samples for the left-turn measurement contract.

The future runner writes these rows alongside its FrameMap, after each Native
tick. This module never supplies fixture-derived channels or a legal conclusion.
"""
import json
import math


def actor_sample(actor):
    transform = actor.get_transform()
    point = transform.location
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(transform)
    position = [float(point.x), float(point.y)]
    motion = [float(velocity.x), float(velocity.y)]
    body = [[float(vertex.x), float(vertex.y)] for vertex in vertices]
    if (len(body) < 4 or any(not math.isfinite(value)
            for coordinates in [position, motion, *body] for value in coordinates)):
        raise ValueError('Incomplete Native actor body/velocity source')
    return {'actor_id': int(actor.id), 'position_xy_m': position,
            'velocity_xy_mps': motion, 'body_vertices_xy_m': body}


def record_sample(stream, *, snapshot, ego, oncoming, reciprocal, left_indicator_mask):
    frame = int(snapshot.frame)
    time_s = float(snapshot.timestamp.elapsed_seconds)
    if frame < 0 or not math.isfinite(time_s) or time_s < 0:
        raise ValueError('Invalid Native frame or time')
    if type(left_indicator_mask) is not int or left_indicator_mask <= 0:
        raise ValueError('Native left-indicator mask required')
    left_state = int(ego.get_light_state())
    heading = float(ego.get_transform().rotation.yaw)
    if not math.isfinite(heading):
        raise ValueError('Nonfinite Native ego heading')
    row = {'frame': frame, 'time_s': time_s,
           'ego': actor_sample(ego), 'oncoming': actor_sample(oncoming),
           'reciprocal': actor_sample(reciprocal), 'ego_heading_deg': heading,
           'ego_left_indicator': bool(left_state & left_indicator_mask)}
    if len({row[name]['actor_id'] for name in ('ego','oncoming','reciprocal')}) != 3:
        raise ValueError('Native participant identities repeat')
    stream.write(json.dumps(row, separators=(',', ':')) + '\n')
    return row
