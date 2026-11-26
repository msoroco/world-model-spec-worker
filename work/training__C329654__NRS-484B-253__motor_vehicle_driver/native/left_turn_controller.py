"""Observed-state Native control requests for the two left-turn conditions.

This policy requests motion. Saved original actor histories, rather than these
requests, determine whether yielding, passage and turn completion occurred.
"""
import math


POLICIES = {"yield_then_turn": 15.0, "turn_before_pass": 9.0}


def _number(value, label):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError("Missing finite observed " + label)
    return float(value)


def steering_to_waypoint(position_xy, yaw_deg, target_xy):
    x, y = (_number(value, "subject position") for value in position_xy)
    tx, ty = (_number(value, "route waypoint") for value in target_xy)
    heading = math.degrees(math.atan2(ty - y, tx - x))
    error = (heading - _number(yaw_deg, "subject heading") + 180) % 360 - 180
    return max(-1.0, min(1.0, error / 35.0))


def command(config, observation):
    policy = config.get("yield_policy")
    if policy not in POLICIES or config.get("turn_release_s") != POLICIES[policy]:
        raise ValueError("Selected exact turn policy differs")
    time_s = _number(observation.get("time_s"), "time")
    ego = observation.get("ego", {})
    opponents = observation.get("oncoming")
    if not isinstance(opponents, list) or len(opponents) < 2:
        raise ValueError("Initial and subsequent observed opponents required")
    initial = opponents[0]
    subsequent = opponents[1]
    if initial.get("actor_id") == subsequent.get("actor_id"):
        raise ValueError("Distinct opposing actor readbacks required")
    first_distance = _number(initial.get("distance_to_conflict_m"), "initial distance")
    second_distance = _number(subsequent.get("distance_to_conflict_m"), "subsequent distance")
    progress = _number(ego.get("left_turn_progress"), "turn progress")
    speed = _number(ego.get("speed_mps"), "subject speed")
    inside = ego.get("inside_intersection")
    if inside not in (True, False) or not 0 <= progress <= 1 or speed < 0:
        raise ValueError("Invalid observed subject state")
    target_xy = observation.get("route_target_xy_m")
    steer = steering_to_waypoint(ego.get("center_xy_m", []), ego.get("heading_deg"), target_xy)
    if not inside:
        ego_phase, ego_drive = "approach", True
    elif policy == "yield_then_turn":
        ego_phase = "turn" if time_s >= POLICIES[policy] and first_distance <= 0 else "yield_wait"
        ego_drive = ego_phase == "turn"
    else:
        ego_phase = "turn" if time_s >= POLICIES[policy] else "yield_wait"
        ego_drive = ego_phase == "turn"
    # This request is conditional on the measured subject's commitment and on
    # a still-approaching second vehicle. It is not a statutory priority verdict.
    subsequent_yield_request = progress >= 0.2 and second_distance > 0
    return {
        "ego": {"phase": ego_phase, "throttle": 0.35 if ego_drive and speed < 5 else 0.0,
                "brake": 0.0 if ego_drive else 1.0, "steer": steer,
                "left_indicator_requested": True},
        "initial_opponent": {"throttle": 0.35, "brake": 0.0},
        "subsequent_opponent": {"throttle": 0.0 if subsequent_yield_request else 0.35,
                                "brake": 0.7 if subsequent_yield_request else 0.0},
        "subsequent_yield_requested": subsequent_yield_request,
        "physical_effect_observed": False,
        "legal_priority_verdict": None,
    }


def apply_vehicle_control(actor, request):
    """Lazy CARLA adapter; only called by a local Native owner."""
    import carla
    actor.apply_control(carla.VehicleControl(
        throttle=request["throttle"], brake=request["brake"],
        steer=request.get("steer", 0.0)))
