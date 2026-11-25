"""Original-frame measurements for NRS 484B.257(2) delivery review.

This module checks observable histories. It never assigns a legal hazard label.
"""
from __future__ import annotations

from math import hypot, isfinite

FPS = 20
FRAMES = 900


def build_case(adapter, spec):
    """Construct only after a native map/device readback supports the case.

    The adapter is injected, so importing this module never imports CARLA. The
    adapter must expose inspect_intersection, inspect_devices, spawn_vehicle,
    and set_target_speed. It must retain its source paths in the returned record.
    """
    if spec.get("cell_id") != "C158196" or spec.get("law_id") != "NRS-484B-257-2":
        raise ValueError("wrong frozen cell or law")
    if spec.get("control_context") not in {"stop_sign", "yield_sign", "signal_exception", "officer_exception"}:
        raise ValueError("invalid requested control")
    if spec.get("counterpart_start_m", 0) < 0 or spec.get("counterpart_start_m", 0) > 100:
        raise ValueError("counterpart start outside reviewed engineering range")
    road = adapter.inspect_intersection()
    if road.get("layout") != "one_way_to_two_way_intersection" or not road.get("through_highway") is False:
        raise ValueError("native road geometry does not support this branch")
    _rect(road.get("intersection_rectangle_xy"))
    if not road.get("source"):
        raise ValueError("native map source missing")
    devices = adapter.inspect_devices()
    if not devices.get("source") or devices.get("context") != spec["control_context"]:
        raise ValueError("native device context does not match requested case")
    if spec["control_context"] in {"stop_sign", "yield_sign"} and devices.get("signal_controlling") is not False:
        raise ValueError("controlling traffic light defeats sign branch")
    if spec["control_context"] in {"signal_exception", "officer_exception"} and devices.get("exception_active") is not True:
        raise ValueError("exception context not physically observed")
    ego = adapter.spawn_vehicle("ego", spec["ego_spawn"])
    other = adapter.spawn_vehicle("counterpart", spec["counterpart_spawn"])
    adapter.set_target_speed(ego, spec["ego_target_mps"])
    adapter.set_target_speed(other, spec["counterpart_target_mps"])
    return {"road_source": road["source"], "device_source": devices["source"],
            "ego_id": ego, "counterpart_id": other,
            "requested_targets_only": True}


def _point(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} requires two coordinates")
    if not all(isinstance(v, (int, float)) and isfinite(v) for v in value):
        raise ValueError(f"{name} has nonfinite coordinates")
    return tuple(float(v) for v in value)


def _inside(point, rectangle):
    x, y = _point(point, "body vertex")
    x0, y0, x1, y1 = rectangle
    return x0 <= x <= x1 and y0 <= y <= y1


def _body(sample, name):
    vertices = sample.get("body_vertices_xy")
    if not isinstance(vertices, list) or len(vertices) != 4:
        raise ValueError(f"{name} requires four original body vertices")
    return [_point(v, name) for v in vertices]


def _rect(value):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("intersection rectangle requires four bounds")
    if not all(isinstance(v, (int, float)) and isfinite(v) for v in value):
        raise ValueError("intersection rectangle has nonfinite bounds")
    x0, y0, x1, y1 = map(float, value)
    if not x0 < x1 or not y0 < y1:
        raise ValueError("intersection rectangle is empty")
    return x0, y0, x1, y1


def _overlap(vertices, rect):
    # The delivered rectangle must also intersect a body containing a corner.
    x0, y0, x1, y1 = rect
    bx0 = min(v[0] for v in vertices)
    by0 = min(v[1] for v in vertices)
    bx1 = max(v[0] for v in vertices)
    by1 = max(v[1] for v in vertices)
    return bx0 <= x1 and bx1 >= x0 and by0 <= y1 and by1 >= y0


def measure(packet, expected_control, expected_relation="within"):
    """Require synchronized, source-backed Native records and return event brackets.

    `stop_sign` and `yield_sign` are measured device states, not case-name facts.
    A yielding maneuver is retained as speed and geometry; sufficiency remains a
    human legal judgment. A signal/officer case is an explicit exception context.
    """
    if expected_control not in {"stop_sign", "yield_sign", "signal_exception", "officer_exception"}:
        raise ValueError("unsupported control context")
    if expected_relation not in {"within", "approaching"}:
        raise ValueError("unsupported counterpart relation")
    sources = packet.get("sources")
    required = {"native_world", "native_devices", "native_ego", "native_counterpart", "camera_sync"}
    if not isinstance(sources, dict) or not required <= set(sources):
        raise ValueError("missing original source inventory")
    if any(not isinstance(sources[k], str) or not sources[k] for k in required):
        raise ValueError("empty original source reference")
    rect = _rect(packet.get("intersection_rectangle_xy"))
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) != FRAMES:
        raise ValueError("expected full 900-frame original history")
    first_native_frame = frames[0].get("native_frame")
    if type(first_native_frame) is not int or first_native_frame < 0:
        raise ValueError("original Native first frame missing")
    first_time_s = frames[0].get("time_s")
    if type(first_time_s) not in (int, float) or not isfinite(first_time_s):
        raise ValueError("original Native first time missing")
    ego_overlap = []
    other_inside = []
    other_center = []
    speeds = []
    distances = []
    for index, frame in enumerate(frames):
        if frame.get("native_frame") != first_native_frame + index:
            raise ValueError("missing or reordered original frame")
        time_s = frame.get("time_s")
        if not isinstance(time_s, (int, float)) or abs(time_s - first_time_s - index / FPS) > 0.001:
            raise ValueError("non-20Hz original elapsed time")
        if frame.get("camera_frame") != index:
            raise ValueError("camera and Native frame maps differ")
        if frame.get("control_context") != expected_control:
            raise ValueError("device/officer context changed within attempt")
        authority = frame.get("authority")
        if (not isinstance(authority, dict) or
                authority.get("native_frame") != first_native_frame + index or
                authority.get("control_context") != expected_control or
                type(authority.get("ego_control_actor_id")) is not int):
            raise ValueError("original same-frame controlling authority missing")
        if expected_control in {"stop_sign", "yield_sign"}:
            if authority.get("signal_controlling") is not False or authority.get("officer_controlling") is not False:
                raise ValueError("sign lost independent control")
        if expected_control == "signal_exception" and authority.get("signal_state") is None:
            raise ValueError("original controlling signal state missing")
        if expected_control == "officer_exception" and authority.get("officer_actor_visible") is not True:
            raise ValueError("original officer control observation missing")
        ego = frame.get("ego")
        other = frame.get("counterpart")
        if not isinstance(ego, dict) or not isinstance(other, dict):
            raise ValueError("missing vehicle state")
        ebody = _body(ego, "ego")
        obody = _body(other, "counterpart")
        speed = ego.get("speed_mps")
        if not isinstance(speed, (int, float)) or not isfinite(speed) or speed < 0:
            raise ValueError("missing measured ego speed")
        if not isinstance(ego.get("applied_controls"), dict):
            raise ValueError("missing applied ego controls")
        if other.get("obligated_to_stop_or_yield") is not False:
            raise ValueError("counterpart priority is unverified")
        ec = tuple(sum(v[j] for v in ebody) / 4 for j in (0, 1))
        oc = tuple(sum(v[j] for v in obody) / 4 for j in (0, 1))
        ego_overlap.append(_overlap(ebody, rect))
        other_inside.append(all(_inside(v, rect) for v in obody))
        other_center.append(oc)
        speeds.append(float(speed))
        distances.append(hypot(ec[0] - oc[0], ec[1] - oc[1]))
    occupied = [i for i, value in enumerate(ego_overlap) if value]
    if not occupied:
        raise ValueError("ego never reaches intersection")
    if occupied[0] == 0 or occupied[-1] == FRAMES - 1:
        raise ValueError("intersection entry/clearance brackets missing")
    if expected_relation == "within":
        if not any(other_inside[:occupied[-1] + 1]):
            raise ValueError("no counterpart fully within intersection during approach or crossing")
    else:
        entry = occupied[0]
        if entry < 2:
            raise ValueError("no counterpart approach history")
        x0, y0, x1, y1 = rect
        center = ((x0 + x1) / 2, (y0 + y1) / 2)
        station = [hypot(p[0] - center[0], p[1] - center[1]) for p in other_center]
        if other_inside[entry] or not station[entry] < station[entry - 2]:
            raise ValueError("counterpart approach not observed before ego entry")
    if expected_control == "stop_sign" and min(speeds[:occupied[0]]) > 0.05:
        raise ValueError("no observed stop before intersection")
    return {
        "entry_frame": occupied[0],
        "clearance_frame": occupied[-1] + 1,
        "counterpart_within_frames": [i for i in occupied if other_inside[i]],
        "counterpart_pre_entry_within_frames": [i for i in range(occupied[0])
                                                if other_inside[i]],
        "counterpart_relation_observed": expected_relation,
        "counterpart_center_station_at_entry_m": hypot(
            other_center[occupied[0]][0] - (rect[0] + rect[2]) / 2,
            other_center[occupied[0]][1] - (rect[1] + rect[3]) / 2),
        "crossing_mean_speed_mps": sum(speeds[i] for i in occupied) / len(occupied),
        "minimum_center_distance_m": min(distances[i] for i in occupied),
        "legal_hazard_judgment": "unresolved",
    }


def compare(left, right, fields):
    """Check exact fixed context and at least one declared physical difference."""
    if not fields:
        raise ValueError("comparison needs declared difference")
    for key in ("map_sha256", "intersection_rectangle_xy", "ego_blueprint", "counterpart_blueprint", "weather", "fps", "camera_policy"):
        if left.get(key) != right.get(key):
            raise ValueError(f"fixed condition changed: {key}")
    if left.get("fps") != FPS:
        raise ValueError("wrong frame rate")
    if not any(left.get(key) != right.get(key) for key in fields):
        raise ValueError("declared difference not realized")
    return True
