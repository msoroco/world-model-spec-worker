"""Native source row builders for a future selected C228133 capture runner.

These functions read a CARLA actor and synchronized camera bytes supplied by
the caller. They do not infer a turn-arrow shape or pedestrian-device permission
from a requested light state. Those observations require a separate pixel and
governance review before the saved measurement may use them.
"""

import hashlib
import math

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _identity(index, native_frame, time_s):
    if type(index) is not int or index < 0 or type(native_frame) is not int or \
            native_frame < 0 or type(time_s) not in (int, float) or \
            not math.isfinite(time_s):
        raise ValueError('Invalid Native frame identity')
    return {'frame': index, 'native_frame': native_frame, 'time_s': time_s}


def pedestrian_row(index, native_frame, time_s, actor, road_side):
    """Capture the roadward edge of the observed walker world footprint."""
    row = _identity(index, native_frame, time_s)
    if road_side not in ('at_or_above_y', 'at_or_below_y') or \
            not str(getattr(actor, 'type_id', '')).startswith('walker.pedestrian.'):
        raise ValueError('Expected a Native pedestrian and calibrated road side')
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = [[float(vertex.x), float(vertex.y)] for vertex in vertices]
    if len(points) < 4 or any(not all(math.isfinite(v) for v in point)
                              for point in points):
        raise ValueError('Incomplete Native walker footprint')
    y = (max(point[1] for point in points) if road_side == 'at_or_above_y'
         else min(point[1] for point in points))
    row.update(actor_id=actor.id, blueprint=actor.type_id,
               footprint_roadward_y_m=y, body_native_xy_m=points,
               source_kind='native_actor')
    return row


def frame_map_row(index, native_frame, time_s, rgb_bytes):
    """Bind every Native tick to four independently acquired RGB images."""
    row = _identity(index, native_frame, time_s)
    if not isinstance(rgb_bytes, dict) or set(rgb_bytes) != set(VIEWS) or \
            any(not isinstance(data, bytes) or not data for data in rgb_bytes.values()):
        raise ValueError('Missing four Native camera images')
    return {'video_frame': row['frame'], 'native_frame': row['native_frame'],
            'carla_frame': row['native_frame'], 'time_s': row['time_s'],
            'source_rgb_sha256': {view: hashlib.sha256(rgb_bytes[view]).hexdigest()
                                  for view in VIEWS}}


def signal_state_row(index, native_frame, time_s, red_actor, arrow_actor):
    """Retain light actor states without claiming a visible directional arrow."""
    row = _identity(index, native_frame, time_s)
    if red_actor.id == arrow_actor.id:
        raise ValueError('Red and arrow light actors must be distinct')
    row.update(red_actor_id=red_actor.id, arrow_actor_id=arrow_actor.id,
               observed_red_actor_state=str(red_actor.get_state()),
               observed_arrow_actor_state=str(arrow_actor.get_state()),
               red='other', green_turn_arrow=False, governs_pedestrian=False,
               directional_arrow_pixels_verified=False,
               facing_governance_verified=False, source_kind='native_signal')
    return row


def pedestrian_device_row(index, native_frame, time_s, device_actor=None):
    """Retain device identity; defer permission until source pixels are reviewed."""
    row = _identity(index, native_frame, time_s)
    row.update(device_actor_id=None if device_actor is None else device_actor.id,
               permits_proceed=False, permission_reviewed=False,
               source_kind='native_pedestrian_device')
    return row
