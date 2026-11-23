"""Build frame-aligned Native source rows for three distinct complete bodies.

This recorder reads Native feedback. It does not infer legal priority, physical
signal inoperability, or camera visibility from an authored configuration.
"""

import math


ROLES = ("ego", "earlier", "occupant")


def _finite(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Finite " + label + " required")
    return float(value)


def signed_front_distance(vertices, point, upstream_normal):
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("Complete Native body vertices required")
    px, py = (_finite(value, "stop-line point") for value in point)
    nx, ny = (_finite(value, "upstream normal") for value in upstream_normal)
    if abs(math.hypot(nx, ny)-1) > 1e-5:
        raise ValueError("Unit upstream normal required")
    return min(((_finite(vertex[0], "body x")-px)*nx +
                (_finite(vertex[1], "body y")-py)*ny) for vertex in vertices)


def actor_row(actor, route, junction_id):
    transform = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(transform)
    if len(vertices) < 4:
        raise ValueError("Complete Native body required")
    xy = [[_finite(v.x, "body x"), _finite(v.y, "body y")] for v in vertices]
    velocity = actor.get_velocity()
    speed = math.sqrt(sum(_finite(getattr(velocity, axis), "velocity")**2 for axis in "xyz"))
    return {"intersection_id": junction_id, "speed_mps": speed,
            "front_to_stop_line_signed_m": signed_front_distance(
                xy, route["stop_line_point_xy_m"], route["upstream_normal_xy"]),
            "body_vertices_xy_m": xy}


def source_row(frame, time_s, junction_id, lights, actors, routes):
    if type(frame) is not int or frame < 0:
        raise ValueError("Nonnegative Native frame required")
    _finite(time_s, "Native time")
    if type(junction_id) is not int or junction_id <= 0:
        raise ValueError("Authored junction ID required")
    if set(actors) != set(ROLES) or set(routes) != set(ROLES):
        raise ValueError("Three distinct Native actors and routes required")
    if len({actors[role].id for role in ROLES}) != 3:
        raise ValueError("Distinct observed Native vehicle IDs required")
    if len(lights) != 2 or len({light.id for light in lights}) != 2:
        raise ValueError("Two distinct observed Native heads required")
    states = {str(light.id): str(light.get_state()).split(".")[-1] for light in lights}
    if any(state not in ("Off", "Green", "Yellow", "Red") for state in states.values()):
        raise ValueError("Unsupported observed Native head state")
    row = {"frame": frame, "time_s": float(time_s), "signal_states": states,
           "actor_ids": {role: actors[role].id for role in ROLES}}
    for role in ROLES:
        row[role] = actor_row(actors[role], routes[role], junction_id)
    return row
