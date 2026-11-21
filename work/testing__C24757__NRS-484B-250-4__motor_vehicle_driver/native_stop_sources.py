"""Retain frame-aligned Native signal and complete-body stop-boundary sources.

The supplied boundary point and upstream normal come from a separately reviewed
map/video site packet. This recorder does not decide the statutory stop location.
"""

import math


def _finite(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Finite " + label + " required")
    return float(value)


def signed_front_distance(vertices, point, upstream_normal):
    """Positive means the complete body's foremost point is before the line."""
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("Complete Native body vertices required")
    px, py = (_finite(v, "boundary point") for v in point)
    nx, ny = (_finite(v, "upstream normal") for v in upstream_normal)
    norm = math.hypot(nx, ny)
    if abs(norm - 1) > 1e-5:
        raise ValueError("Unit upstream boundary normal required")
    distances = []
    for vertex in vertices:
        if not isinstance(vertex, (list, tuple)) or len(vertex) < 2:
            raise ValueError("Complete Native body vertex required")
        x, y = _finite(vertex[0], "body x"), _finite(vertex[1], "body y")
        distances.append((x - px) * nx + (y - py) * ny)
    return min(distances)


def actor_source(actor, intersection_id, point, upstream_normal, signed_field):
    transform = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(transform)
    xy = [[_finite(vertex.x, "body x"), _finite(vertex.y, "body y")] for vertex in vertices]
    velocity = actor.get_velocity()
    speed = math.sqrt(sum(_finite(getattr(velocity, axis), "velocity") ** 2 for axis in "xyz"))
    return {"intersection_id": intersection_id, "speed_mps": speed,
            signed_field: signed_front_distance(xy, point, upstream_normal),
            "body_vertices_xy_m": xy}


def source_row(frame, time_s, signal, ego, other, site, other_signal):
    if type(frame) is not int or frame < 0:
        raise ValueError("Nonnegative Native frame required")
    _finite(time_s, "Native time")
    boundary = site.get("stop_boundary")
    other_boundary = site.get("other_stop_boundary")
    fields = {"stop_line": "front_to_stop_line_signed_m",
              "crosswalk": "front_to_crosswalk_signed_m",
              "nearest_view": "front_to_nearest_view_signed_m"}
    for candidate in (boundary, other_boundary):
        if not isinstance(candidate, dict) or candidate.get("kind") not in fields or not candidate.get("source"):
            raise ValueError("Sourced statutory stop boundary required for each approach")
        point, normal = candidate.get("point_xy_m"), candidate.get("upstream_normal_xy")
        if not isinstance(point, list) or len(point) != 2 or not isinstance(normal, list) or len(normal) != 2:
            raise ValueError("Boundary geometry required")
    if not site.get("intersection_id") or not site.get("native_signal_id") or not site.get("other_native_signal_id"):
        raise ValueError("Sourced Native signal and intersection IDs required")
    if (signal.id != site["native_signal_id"] or
            other_signal.id != site["other_native_signal_id"] or signal.id == other_signal.id):
        raise ValueError("Observed different Native signal head")
    signal_state = str(signal.get_state()).split(".")[-1]
    other_signal_state = str(other_signal.get_state()).split(".")[-1]
    if signal_state != "Off" or other_signal_state != "Off":
        raise ValueError("Native Off readback failed in source row")
    return {"frame": frame, "time_s": time_s,
            "native_signal_id": signal.id, "signal_state": signal_state,
            "other_native_signal_id": other_signal.id, "other_signal_state": other_signal_state,
            "ego": actor_source(ego, site["intersection_id"], boundary["point_xy_m"],
                                boundary["upstream_normal_xy"], fields[boundary["kind"]]),
            "other": actor_source(other, site["intersection_id"], other_boundary["point_xy_m"],
                                  other_boundary["upstream_normal_xy"], fields[other_boundary["kind"]])}
