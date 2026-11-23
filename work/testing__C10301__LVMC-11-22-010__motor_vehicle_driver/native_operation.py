"""Lazy Native acquisition for the two alley-operation observation cases.

This constructs the requested ego motion only after a local operator supplies a
reviewed Native site. The geometry candidate is not evidence that a CARLA map
contains an alley, marked access aisle, or municipal jurisdiction.
"""
from __future__ import annotations

import math


ASSIGNMENT = "testing__C10301__LVMC-11-22-010__motor_vehicle_driver"
CASE_PROFILES = {
    ASSIGNMENT + "__steady_travel": "steady",
    ASSIGNMENT + "__steering_variation": "variation",
}
FPS = 20


def require_site(site: dict, case_id: str) -> None:
    if case_id not in CASE_PROFILES:
        raise ValueError("unknown exact case")
    for key in ("map_name", "alley_route_source", "access_aisle_source",
                "parking_designation_source", "municipal_jurisdiction_source",
                "ego_blueprint_id"):
        if not isinstance(site.get(key), str) or not site[key].strip():
            raise ValueError("missing reviewed Native source: " + key)
    if site.get("fps") != FPS:
        raise ValueError("original acquisition must run at 20 Hz")
    origin = site.get("ego_spawn_xyz_m")
    if not isinstance(origin, list) or len(origin) != 3 or not all(
        type(v) in (int, float) and math.isfinite(v) for v in origin
    ):
        raise ValueError("finite Native ego spawn required")
    if type(site.get("ego_yaw_deg")) not in (int, float) or not math.isfinite(site["ego_yaw_deg"]):
        raise ValueError("finite ego heading required")


def spawn_ego(world, carla, site: dict, case_id: str):
    """Spawn and read back the exact requested actor on the sourced map."""
    require_site(site, case_id)
    if world.get_map().name != site["map_name"]:
        raise ValueError("Native map does not match reviewed source")
    blueprint = world.get_blueprint_library().find(site["ego_blueprint_id"])
    x, y, z = site["ego_spawn_xyz_m"]
    transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                carla.Rotation(yaw=site["ego_yaw_deg"]))
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None or not actor.is_alive or actor.type_id != site["ego_blueprint_id"]:
        raise ValueError("Native ego spawn/readback failed")
    return actor


def request_control(actor, carla, case_id: str, elapsed_s: float):
    """Apply an observation contrast; no control request is a legal label."""
    if case_id not in CASE_PROFILES or not math.isfinite(elapsed_s) or elapsed_s < 0:
        raise ValueError("invalid exact case or time")
    if not actor.is_alive:
        raise ValueError("ego actor is not alive")
    # The same low-speed throttle policy is used for both cases. A bounded
    # preplanned steering perturbation is the sole deliberate control change.
    steer = 0.0 if CASE_PROFILES[case_id] == "steady" else 0.08 * math.sin(elapsed_s * math.pi)
    command = carla.VehicleControl(throttle=0.22, steer=steer, brake=0.0)
    actor.apply_control(command)
    return {"requested_throttle": 0.22, "requested_steer": steer,
            "requested_brake": 0.0, "elapsed_s": elapsed_s}


def sample_original(actor, snapshot, case_id: str, person_id: str) -> dict:
    """Read original Native actor state after a world tick.

    Device, aisle footprint and conflict observations require separate sourced
    acquisition. They are not guessed from this ego-only sample.
    """
    if case_id not in CASE_PROFILES or not person_id or not actor.is_alive:
        raise ValueError("exact case, operator identity and live ego required")
    position = actor.get_transform().location
    velocity = actor.get_velocity()
    acceleration = actor.get_acceleration()
    angular = actor.get_angular_velocity()
    values = (position.x, position.y, velocity.x, velocity.y,
              acceleration.x, acceleration.y, angular.z,
              snapshot.timestamp.elapsed_seconds)
    if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
        raise ValueError("nonfinite original Native state")
    speed = math.hypot(velocity.x, velocity.y)
    longitudinal = 0.0 if speed < 1e-6 else (
        acceleration.x * velocity.x + acceleration.y * velocity.y) / speed
    return {"source_kind": "original_native_ego_state", "case_id": case_id,
            "native_frame": int(snapshot.frame),
            "native_time_s": float(snapshot.timestamp.elapsed_seconds),
            "person_id": person_id, "vehicle_id": str(actor.id),
            "operating": True, "position_x_m": float(position.x),
            "position_y_m": float(position.y),
            "yaw_rate_rad_s": math.radians(float(angular.z)),
            "speed_m_s": speed,
            "accel_longitudinal_m_s2": longitudinal}


def validate_history(rows: list[dict], case_id: str) -> dict:
    """Require complete, contiguous 20 Hz original observations."""
    if case_id not in CASE_PROFILES or len(rows) < 2:
        raise ValueError("two original frames required")
    first = rows[0]
    if first.get("case_id") != case_id or first.get("source_kind") != "original_native_ego_state":
        raise ValueError("first original source or case mismatch")
    ids = (first.get("person_id"), first.get("vehicle_id"))
    if not all(ids):
        raise ValueError("original identities missing")
    for previous, row in zip(rows, rows[1:]):
        if row.get("case_id") != case_id or row.get("source_kind") != "original_native_ego_state":
            raise ValueError("source or case mismatch")
        if (row.get("person_id"), row.get("vehicle_id")) != ids:
            raise ValueError("participant identity changed")
        if row["native_frame"] != previous["native_frame"] + 1:
            raise ValueError("native frame gap")
        if abs(row["native_time_s"] - previous["native_time_s"] - 1 / FPS) > 0.001:
            raise ValueError("original 20 Hz time gap")
    return {"case_id": case_id, "original_frames": len(rows),
            "first_native_frame": first["native_frame"],
            "last_native_frame": rows[-1]["native_frame"],
            "interior_attention_observed": False}


def assemble_measurement_rows(ego_rows: list[dict], context_rows: list[dict],
                              case_id: str) -> list[dict]:
    """Join independently acquired context by original Native frame identity.

    Context acquisition must measure the aisle footprint, conflict path, and
    device state from Native sources. A missing source is rejected rather than
    filled with a favorable observation.
    """
    validate_history(ego_rows, case_id)
    if len(context_rows) != len(ego_rows):
        raise ValueError("missing original context frames")
    joined = []
    for index, (ego, context) in enumerate(zip(ego_rows, context_rows)):
        if context.get("source_kind") != "original_native_context_state":
            raise ValueError("context must come from original Native acquisition")
        if context.get("case_id") != case_id or context.get("native_frame") != ego["native_frame"]:
            raise ValueError("context frame or exact case mismatch")
        if not isinstance(context.get("source_sha256"), str) or len(context["source_sha256"]) != 64:
            raise ValueError("context source hash required")
        for key in ("straddles_marking", "time_to_conflict_s", "traffic_signal"):
            if key not in context:
                raise ValueError("missing original context: " + key)
        joined.append({
            "case_id": case_id, "frame": index,
            "time_s": index / FPS, "person_id": ego["person_id"],
            "vehicle_id": ego["vehicle_id"], "operating": ego["operating"],
            "position_x_m": ego["position_x_m"],
            "position_y_m": ego["position_y_m"],
            "yaw_rate_rad_s": ego["yaw_rate_rad_s"],
            "speed_m_s": ego["speed_m_s"],
            "accel_longitudinal_m_s2": ego["accel_longitudinal_m_s2"],
            # Engineering deceleration bin only; no legal threshold is implied.
            "hard_deceleration": ego["accel_longitudinal_m_s2"] <= -3.0,
            "straddles_marking": context["straddles_marking"],
            "time_to_conflict_s": context["time_to_conflict_s"],
            "traffic_signal": context["traffic_signal"],
            "native_frame": ego["native_frame"],
            "native_time_s": ego["native_time_s"],
            "context_source_sha256": context["source_sha256"],
        })
    return joined
