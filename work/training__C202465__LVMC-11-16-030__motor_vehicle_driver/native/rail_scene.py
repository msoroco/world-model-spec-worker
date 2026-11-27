"""Source-shaped rail geometry and per-frame sight proxy for Native capture.

The geometry is a diagnostic proxy. Original actor and device readbacks, map
identity, and camera review remain necessary for physical acceptance.
"""

from __future__ import annotations

from math import hypot, isfinite

from rail_sight import FOUR_HUNDRED_FEET_M, FRAME_RATE


def _point(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(name + " requires a 2D source position")
    x, y = map(float, value)
    if not isfinite(x) or not isfinite(y):
        raise ValueError(name + " contains an invalid position")
    return x, y


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def segment_intersects(a, b, c, d):
    """Include contact with an opaque edge as occluded."""
    a, b, c, d = (_point(p, "ray endpoint") for p in (a, b, c, d))
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    q = (c[0] - a[0], c[1] - a[1])
    den = _cross(r, s)
    if abs(den) < 1e-12:
        if abs(_cross(q, r)) > 1e-9:
            return False
        rr = r[0] * r[0] + r[1] * r[1]
        if rr <= 0:
            return False
        t1 = (q[0]*r[0] + q[1]*r[1]) / rr
        t2 = ((d[0]-a[0])*r[0] + (d[1]-a[1])*r[1]) / rr
        return max(min(t1, t2), 0.0) <= min(max(t1, t2), 1.0)
    t, u = _cross(q, s) / den, _cross(q, r) / den
    return -1e-9 <= t <= 1+1e-9 and -1e-9 <= u <= 1+1e-9


def ray_clear(observer, target, blockers):
    observer, target = _point(observer, "observer"), _point(target, "target")
    if hypot(target[0]-observer[0], target[1]-observer[1]) < 1e-6:
        raise ValueError("zero length sight ray")
    for blocker in blockers:
        if not blocker.get("source_ref") or not blocker.get("opaque", False):
            raise ValueError("opaque blocker needs original source identity")
        edge = blocker.get("edge_xy_m")
        if not isinstance(edge, list) or len(edge) != 2:
            raise ValueError("blocker edge missing")
        if segment_intersects(observer, target, edge[0], edge[1]):
            return False
    return True


def _source_actor(actor, kind):
    if not actor.get("source_ref") or actor.get("kind") != kind:
        raise ValueError(kind + " original actor readback missing")
    return _point(actor.get("center_xy_m"), kind)


def sight_row(frame, ego, railway, rail_traffic, blockers, flagman, signal):
    """Measure each signed rail direction and both moving rail actors."""
    if not isinstance(frame, int) or frame < 0:
        raise ValueError("invalid Native frame")
    if not ego.get("source_ref") or not railway.get("source_ref"):
        raise ValueError("original ego and railway provenance required")
    observer = _point(ego.get("observer_xy_m"), "ego observer")
    crossing = _point(railway.get("crossing_xy_m"), "rail crossing")
    direction = _point(railway.get("unit_direction_xy"), "rail direction")
    if abs(hypot(*direction) - 1.0) > 1e-6:
        raise ValueError("rail direction must be unit length")
    if railway.get("grade_crossing") is not True:
        raise ValueError("source railway must be a grade crossing")
    if not rail_traffic or {a.get("side") for a in rail_traffic} != {"left", "right"}:
        raise ValueError("source railway traffic required in both directions")
    if not flagman.get("source_ref") or type(flagman.get("on_duty")) is not bool:
        raise ValueError("flagman duty readback required")
    if not signal.get("source_ref") or any(type(signal.get(k)) is not bool for k in
        ("installed", "visible", "indicates_approach")):
        raise ValueError("crossing signal readback required")
    extents = {}
    traffic_visible = {}
    for side, sign in (("left", -1), ("right", 1)):
        actor = next(a for a in rail_traffic if a["side"] == side)
        actor_xy = _source_actor(actor, "rail_vehicle")
        along = (actor_xy[0]-crossing[0])*direction[0] + (actor_xy[1]-crossing[1])*direction[1]
        if sign * along <= 0:
            raise ValueError("rail vehicle is on wrong signed side")
        clear = 0.0
        for distance_m in list(range(1, 122)) + [FOUR_HUNDRED_FEET_M]:
            target = (crossing[0] + sign * distance_m * direction[0],
                      crossing[1] + sign * distance_m * direction[1])
            if not ray_clear(observer, target, blockers):
                break
            clear = float(distance_m)
        extents[side] = clear
        traffic_visible[side] = ray_clear(observer, actor_xy, blockers)
    return {
        "frame": frame, "time_s": frame / FRAME_RATE,
        "distance_to_crossing_m": float(ego["distance_to_crossing_m"]),
        "speed_mps": float(ego["speed_mps"]),
        "traversing_grade_crossing": bool(ego["traversing_grade_crossing"]),
        "crossing_visible": ray_clear(observer, crossing, blockers),
        "rail_left_clear_distance_m": extents["left"],
        "rail_right_clear_distance_m": extents["right"],
        "left_traffic_visible": traffic_visible["left"],
        "right_traffic_visible": traffic_visible["right"],
        "flagman_on_duty": flagman["on_duty"],
        "crossing_signal_installed_visible": signal["installed"] and signal["visible"],
        "signal_indicates_train_approach": signal["indicates_approach"],
        "observer_pose_source": ego["source_ref"] + ":frame:" + str(frame),
        "observer_xy_m": list(observer),
        "rail_ray_source": railway["source_ref"] + ":frame:" + str(frame),
        "rail_vehicle_source_refs": [a["source_ref"] for a in rail_traffic],
        "blocker_source_refs": [b["source_ref"] for b in blockers],
        "flagman_source_ref": flagman["source_ref"],
        "signal_source_ref": signal["source_ref"],
        "sight_method": "2D dynamic virtual observer and opaque edge proxy; physical visibility unverified",
    }
