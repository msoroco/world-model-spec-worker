"""Draft scalar through-vehicle speed control and source-body readback.

This is a CPU construction probe. Its target is an engineering command, not
an immediate-hazard threshold. Native feasibility and pixels require capture.
"""

import math

from yield_controller import speed_control


TARGETS_MPS = (3.0, 7.0, 11.0)


def command_through(actor, target_mps, control_factory):
    if target_mps not in TARGETS_MPS:
        raise ValueError('Through target is outside the declared scalar sweep')
    velocity = actor.get_velocity()
    observed = math.sqrt(sum(float(getattr(velocity, axis)) ** 2
                             for axis in ('x', 'y', 'z')))
    if not math.isfinite(observed):
        raise ValueError('Nonfinite original through-actor velocity')
    command = speed_control(target_mps, observed)
    actor.apply_control(control_factory(**command))
    return {'through_target_mps': target_mps, 'through_observed_mps': observed,
            'through_command': command}


def body_speed_samples(rows):
    """Measure speed from same-actor body centers and original frame times."""
    previous = None
    actor_id = None
    result = []
    for row in rows:
        frame, time_s = row['frame'], float(row['time_s'])
        body = row.get('through')
        if body is None:
            raise ValueError('Through actor absent from a speed-sweep source')
        if actor_id is None:
            actor_id = body['actor_id']
        if body['actor_id'] != actor_id:
            raise ValueError('Through actor identity changed')
        vertices = body['body_vertices_m']
        if len(vertices) < 4:
            raise ValueError('Incomplete original through-actor body')
        center = tuple(sum(float(point[axis]) for point in vertices) / len(vertices)
                       for axis in (0, 1))
        if not all(math.isfinite(value) for value in (*center, time_s)):
            raise ValueError('Nonfinite original through-actor source')
        if previous is not None:
            old_frame, old_time, old_center = previous
            if type(frame) is not int or frame <= old_frame or time_s <= old_time:
                raise ValueError('Nonmonotone original frame or time')
            speed = math.dist(center, old_center) / (time_s - old_time)
            result.append({'frame': frame, 'time_s': time_s, 'actor_id': actor_id,
                           'through_vehicle_speed_mps': speed})
        previous = (frame, time_s, center)
    if not result:
        raise ValueError('At least two through-body frames required')
    return result
