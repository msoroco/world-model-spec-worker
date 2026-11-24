"""Source-bound construction and measurement rules for NRS 484B.270(5)(a).

The caller supplies a packet read from a selected Native map and blueprints.
This module never treats requested actors or a scripted brake as observed facts.
"""

from math import hypot, isfinite


RIDER_KINDS = ("bicycle", "electric_bicycle", "electric_scooter")


def _point(entry):
    if not entry.get("source_ref") or not entry.get("road_id") or not entry.get("lane_id"):
        raise ValueError("route waypoint needs original Native provenance")
    result = float(entry["x_m"]), float(entry["y_m"])
    if not all(isfinite(value) for value in result):
        raise ValueError("nonfinite waypoint")
    return result


def _segments_cross(a, b, c, d):
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    x, y, z, w = side(a, b, c), side(a, b, d), side(c, d, a), side(c, d, b)
    # OpenDRIVE waypoint sampling commonly places the conflict at a shared
    # segment endpoint. Accept that intersection while rejecting collinear
    # routes, which do not establish an across-path conflict by themselves.
    direction_a = (b[0] - a[0], b[1] - a[1])
    direction_b = (d[0] - c[0], d[1] - c[1])
    cross = direction_a[0] * direction_b[1] - direction_a[1] * direction_b[0]
    return abs(cross) > 1e-6 and x * y <= 0 and z * w <= 0


def validate_site(packet, rider_kind):
    """Reject a tag-only intersection or unsupported rider classification."""
    if rider_kind not in RIDER_KINDS:
        raise ValueError("unsupported rider kind")
    if len(packet.get("map_sha256", "")) != 64 or not packet.get("map_source_ref"):
        raise ValueError("original map hash/source required")
    if packet.get("junction_id") is None:
        raise ValueError("original junction required")
    routes = []
    for name in ("ego_route", "rider_route"):
        entries = packet.get(name, [])
        if len(entries) < 3:
            raise ValueError("approach, conflict and exit waypoints required")
        coordinates = [_point(item) for item in entries]
        if entries[1].get("junction_id") != packet["junction_id"]:
            raise ValueError("route conflict waypoint is outside junction")
        if hypot(coordinates[0][0] - coordinates[1][0], coordinates[0][1] - coordinates[1][1]) < 2:
            raise ValueError("approach too short to establish encounter")
        routes.append(coordinates)
    ego, rider = routes
    if not any(_segments_cross(ego[i], ego[i + 1], rider[j], rider[j + 1])
               for i in range(len(ego) - 1) for j in range(len(rider) - 1)):
        raise ValueError("original routes have no crossing conflict")
    motor = packet.get("motor_vehicle", {})
    if not motor.get("source_ref") or not motor.get("blueprint_id") or motor.get("rail_bound"):
        raise ValueError("source-backed nonrail motor vehicle required")
    rider_actor = packet.get("rider", {})
    if not rider_actor.get("source_ref") or not rider_actor.get("blueprint_id") or not rider_actor.get("person_actor_id"):
        raise ValueError("rider person and blueprint must be source-backed")
    if rider_actor.get("kind") != rider_kind or rider_actor.get("moped"):
        raise ValueError("rider classification conflicts with case")
    if rider_kind == "bicycle":
        wheels = rider_actor.get("wheel_diameters_in", [])
        if len(wheels) != 2 or not any(float(x) > 14 for x in wheels) or rider_actor.get("motorized"):
            raise ValueError("human-powered tandem-wheel bicycle not established")
    elif rider_kind == "electric_bicycle" and not rider_actor.get("electric_assist"):
        raise ValueError("electric bicycle propulsion not established")
    elif rider_kind == "electric_scooter" and not rider_actor.get("standing_platform"):
        raise ValueError("electric scooter platform not established")
    return {"map_sha256": packet["map_sha256"], "junction_id": packet["junction_id"],
            "rider_kind": rider_kind, "crossing_conflict": True}


def spawn_encounter(world, packet, rider_kind, transform_factory):
    """Use source-selected Native blueprints and route approach transforms.

    world is an injected CARLA-shaped object; no CARLA import occurs here.
    Spawn failures clean up both owned actors before returning control.
    """
    validate_site(packet, rider_kind)
    library = world.get_blueprint_library()
    created = []
    try:
        for actor_key, route_key in (("motor_vehicle", "ego_route"), ("rider", "rider_route")):
            blueprint_id = packet[actor_key]["blueprint_id"]
            blueprint = library.find(blueprint_id)
            if blueprint is None or getattr(blueprint, "id", None) != blueprint_id:
                raise ValueError("declared Native blueprint unavailable")
            position = packet[route_key][0]
            actor = world.try_spawn_actor(blueprint, transform_factory(position))
            if actor is None:
                raise ValueError("Native actor spawn failed")
            if getattr(actor, "type_id", None) != blueprint_id:
                raise ValueError("spawned Native actor identity differs")
            created.append(actor)
        return {"ego": created[0], "rider": created[1],
                "blueprint_ids": (created[0].type_id, created[1].type_id)}
    except Exception:
        for actor in reversed(created):
            actor.destroy()
        raise


def control_step(ego_speed_mps, distance_to_conflict_m, rider_time_to_conflict_s, response):
    """Engineering trigger only; no due-care or legal cutoff is inferred."""
    if response not in ("brake", "maintain"):
        raise ValueError("unknown paired response")
    values = (ego_speed_mps, distance_to_conflict_m, rider_time_to_conflict_s)
    if not all(isfinite(float(x)) and float(x) >= 0 for x in values):
        raise ValueError("invalid source samples")
    ego_ttc = float(distance_to_conflict_m) / max(float(ego_speed_mps), 0.01)
    conflict_window = abs(ego_ttc - float(rider_time_to_conflict_s)) <= 2.0
    return {"throttle": 0.0 if response == "brake" and conflict_window else 0.25,
            "brake": 0.65 if response == "brake" and conflict_window else 0.0,
            "conflict_window": conflict_window, "ego_ttc_s": ego_ttc}


def audit_original_history(rows, *, expected_rider_kind, expected_response, map_sha256,
                           expected_person_actor_id=None):
    """Require original samples, role IDs and observed response, never request flags."""
    if expected_rider_kind not in RIDER_KINDS or expected_response not in ("brake", "maintain"):
        raise ValueError("invalid audit target")
    if not rows or len(rows) < 3:
        raise ValueError("insufficient original history")
    first = rows[0]
    expected_ids = (first.get("ego_actor_id"), first.get("rider_actor_id"))
    if not all(expected_ids) or expected_ids[0] == expected_ids[1]:
        raise ValueError("distinct observed actor IDs required")
    if expected_person_actor_id is not None and (
            not first.get("rider_person_actor_id") or
            str(first["rider_person_actor_id"]) != str(expected_person_actor_id) or
            str(first["rider_person_actor_id"]) == str(expected_ids[0])):
        raise ValueError("source-bound rider person identity missing or changed")
    previous = None
    conflict_rows = []
    for row in rows:
        if row.get("source") != "original_native" or row.get("map_sha256") != map_sha256:
            raise ValueError("original map-bound samples required")
        if (row.get("ego_actor_id"), row.get("rider_actor_id")) != expected_ids:
            raise ValueError("actor identity changed")
        if expected_person_actor_id is not None and (
                str(row.get("rider_person_actor_id")) != str(expected_person_actor_id)):
            raise ValueError("source-bound rider person identity missing or changed")
        if row.get("rider_kind_observed") != expected_rider_kind or not row.get("rider_mounted_observed"):
            raise ValueError("rider type or mounted state unobserved")
        frame = int(row["frame"])
        time_s = float(row["time_s"])
        if previous and (frame != previous[0] + 1 or abs(time_s - previous[1] - 0.05) > 0.005):
            raise ValueError("20 Hz original continuity lost")
        previous = frame, time_s
        for key in ("surface_gap_m", "ego_speed_mps", "rider_speed_mps", "ego_brake_observed"):
            if not isfinite(float(row[key])):
                raise ValueError("nonfinite original measurement")
        if row.get("conflict_window_observed"):
            conflict_rows.append(row)
    if not conflict_rows:
        raise ValueError("no observed encounter window")
    brakes = [float(row["ego_brake_observed"]) for row in conflict_rows]
    if expected_response == "brake" and max(brakes) < 0.5:
        raise ValueError("braking response not observed")
    if expected_response == "maintain" and max(brakes) > 0.1:
        raise ValueError("maintained response not observed")
    return {"rider_kind": expected_rider_kind, "response": expected_response,
            "min_surface_gap_m": min(float(row["surface_gap_m"]) for row in conflict_rows),
            "contact_observed": any(bool(row.get("contact_observed")) for row in rows),
            "frames": len(rows), "physical_outcome": "unreviewed"}
