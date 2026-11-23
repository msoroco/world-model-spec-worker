"""Source-bound reverse-crosswalk construction and saved-frame audit.

This module measures physical backing and body overlap. It makes no legal
boundary-contact or compliance decision and never imports CARLA on CPU.
"""

from math import hypot, isfinite


def _xy(point):
    if len(point) != 2:
        raise ValueError("original XY coordinate required")
    x, y = map(float, point)
    if not isfinite(x) or not isfinite(y):
        raise ValueError("nonfinite original coordinate")
    return x, y


def _axes(poly):
    for a, b in zip(poly, poly[1:] + poly[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        if hypot(dx, dy) < 0.01:
            raise ValueError("degenerate polygon edge")
        yield -dy, dx


def _extent(poly, axis):
    values = [p[0] * axis[0] + p[1] * axis[1] for p in poly]
    return min(values), max(values)


def polygon_relation(body, crossing):
    """Return disjoint/contact/overlap using convex source polygons."""
    body, crossing = list(map(_xy, body)), list(map(_xy, crossing))
    if len(body) < 3 or len(crossing) < 3:
        raise ValueError("original convex body and crosswalk polygons required")
    contact = False
    for axis in list(_axes(body)) + list(_axes(crossing)):
        a0, a1 = _extent(body, axis)
        b0, b1 = _extent(crossing, axis)
        gap = max(a0 - b1, b0 - a1)
        if gap > 1e-8:
            return "disjoint"
        if gap >= -1e-8:
            contact = True
    return "contact" if contact else "overlap"


def validate_source(packet):
    required = ("map_name", "map_sha256", "crosswalk_source", "crosswalk_polygon_xy",
                "vehicle_blueprint_id", "spawn_transform_source", "reverse_route_xy",
                "driver_source", "district_source")
    if any(not packet.get(k) for k in required):
        raise ValueError("source-hashed map, marked crossing, vehicle and driver required")
    if len(packet["map_sha256"]) != 64 or not packet["vehicle_blueprint_id"].startswith("vehicle."):
        raise ValueError("invalid original map hash or vehicle blueprint")
    route = list(map(_xy, packet["reverse_route_xy"]))
    if len(route) < 2 or any(hypot(b[0]-a[0], b[1]-a[1]) < .1 for a, b in zip(route, route[1:])):
        raise ValueError("connected nondegenerate reverse route required")
    crossing = list(map(_xy, packet["crosswalk_polygon_xy"]))
    if len(crossing) < 3:
        raise ValueError("original marked-crosswalk polygon required")
    list(_axes(crossing))
    return {"map_sha256": packet["map_sha256"], "map_name": packet["map_name"],
            "vehicle_blueprint_id": packet["vehicle_blueprint_id"],
            "crosswalk_source": packet["crosswalk_source"], "route": route}


def construct(world, packet, spawn_transform):
    """Spawn one checked ego from a source-bound Native map and transform."""
    source = validate_source(packet)
    if spawn_transform is None:
        raise ValueError("original spawn transform required")
    if world.get_map().name != source["map_name"]:
        raise ValueError("Native map readback differs from source")
    bp = world.get_blueprint_library().find(source["vehicle_blueprint_id"])
    actor = world.try_spawn_actor(bp, spawn_transform)
    if actor is None:
        raise ValueError("Native ego spawn failed")
    try:
        if actor.type_id != bp.id:
            raise ValueError("Native ego blueprint readback differs")
        return {"ego": actor, "source": source, "cleanup": actor.destroy}
    except Exception:
        actor.destroy()
        raise


def control_step(actor, *, reverse, hold, control_factory):
    if not isinstance(reverse, bool) or not isinstance(hold, bool):
        raise ValueError("explicit reverse and hold decisions required")
    command = {"reverse": reverse, "throttle": .16 if reverse and not hold else 0.0,
               "brake": 0.0 if reverse and not hold else 1.0, "hand_brake": False}
    actor.apply_control(control_factory(**command))
    return command


def measure(frames, *, source_id, map_sha256, crosswalk_source, vehicle_actor_id):
    if not source_id or len(map_sha256) != 64 or not crosswalk_source or vehicle_actor_id is None or not frames:
        raise ValueError("original source identities and frames required")
    rows = []
    previous_frame, previous_time = -1, -1.0
    for frame in frames:
        required = ("frame", "time_s", "vehicle_actor_id", "body_polygon_xy",
                    "crosswalk_polygon_xy", "velocity_xy", "forward_xy", "reverse_gear")
        if any(k not in frame for k in required):
            raise ValueError("missing original frame source")
        index, now = int(frame["frame"]), float(frame["time_s"])
        if index != previous_frame + 1 and previous_frame >= 0 or now <= previous_time:
            raise ValueError("noncontiguous or unordered original frames")
        if frame["vehicle_actor_id"] != vehicle_actor_id:
            raise ValueError("original actor identity changed")
        if previous_frame >= 0 and abs(now - previous_time - .05) > .001:
            raise ValueError("original source is not 20 Hz")
        velocity, forward = _xy(frame["velocity_xy"]), _xy(frame["forward_xy"])
        reverse_speed = -sum(a*b for a, b in zip(velocity, forward))
        rows.append({"frame": index, "time_s": now,
                     "relation": polygon_relation(frame["body_polygon_xy"], frame["crosswalk_polygon_xy"]),
                     "reverse_speed_mps": reverse_speed, "reverse_gear": bool(frame["reverse_gear"])})
        previous_frame, previous_time = index, now
    if not any(row["reverse_gear"] and row["reverse_speed_mps"] > .05 for row in rows):
        raise ValueError("backing not observed")
    return {"source_id": source_id, "map_sha256": map_sha256,
            "crosswalk_source": crosswalk_source, "vehicle_actor_id": vehicle_actor_id,
            "frames": rows, "legal_judgment": "unresolved"}


def audit(measured, *, expected_relation):
    if expected_relation not in ("disjoint", "contact", "overlap"):
        raise ValueError("unknown physical target")
    rows = measured["frames"]
    observed = [r for r in rows if r["reverse_gear"] and r["reverse_speed_mps"] > .05]
    if not observed or not any(r["relation"] == expected_relation for r in observed):
        raise ValueError("target relation not observed while backing")
    return {"source_id": measured["source_id"], "observed_relation": expected_relation,
            "frame_count": len(rows), "legal_judgment": "unresolved"}


def compare(left, right, *, changed_target):
    if left["source_id"] == right["source_id"] or left["map_sha256"] != right["map_sha256"]:
        raise ValueError("distinct sources and common map required")
    if left["crosswalk_source"] != right["crosswalk_source"]:
        raise ValueError("crosswalk source differs")
    a, b = left["frames"], right["frames"]
    if len(a) != len(b) or [x["frame"] for x in a] != [x["frame"] for x in b]:
        raise ValueError("comparison frame window differs")
    if not any(x["relation"] != y["relation"] for x, y in zip(a, b)):
        raise ValueError("physical relation did not differ")
    if not any(y["relation"] == changed_target and y["reverse_gear"] and y["reverse_speed_mps"] > .05 for y in b):
        raise ValueError("changed target not observed while backing")
    return {"sources": [left["source_id"], right["source_id"]],
            "fixed": ["map_sha256", "crosswalk_source", "frame_window"],
            "changed": "body-crosswalk relation during backing", "legal_judgment": "unresolved"}
