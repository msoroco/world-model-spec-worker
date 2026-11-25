"""One synchronous Native officer-case tick with original-source joins.

The arm-pose readback proves a command reached the walker API. It cannot prove
that a police officer controlled this approach or that a driver saw a gesture.
Those findings require separate review of the original camera sources.
"""

import math

from officer_direction import REFERENCE_SUFFIXES, apply_direction, behavior_suffix
from stopping_reference import ApproachState, control_step


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _body(actor):
    if type(getattr(actor, "id", None)) is not int:
        raise ValueError("Native actor identity missing")
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError("Complete Native actor body missing")
    points = [[float(v.x), float(v.y)] for v in vertices]
    if any(not math.isfinite(x) for point in points for x in point):
        raise ValueError("Nonfinite Native actor body")
    return points


def _speed(actor):
    velocity = actor.get_velocity()
    values = (velocity.x, velocity.y, velocity.z)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError("Native actor speed readback missing")
    return math.sqrt(sum(v * v for v in values))


def _control(carla, ego, command):
    if type(getattr(ego, "id", None)) is not int:
        raise ValueError("Native ego identity missing")
    for key in ("throttle", "brake"):
        value = command.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Invalid Native ego command")
    ego.apply_control(carla.VehicleControl(throttle=command["throttle"],
                                           brake=command["brake"]))
    return {"actor_id": ego.id, "command": command,
            "native_control_applied": True}


def step(carla, world, ego, other, officer, bone_adapter, case_id, frame_index,
         frame_count, reference, approach_state, camera_readback, source_intake,
         *, hold_ticks=20, go_frame=None):
    """Command and tick once, then join all four raw cameras and actor bodies.

    The inactive case follows the sourced stopping reference. Active officer
    cases hold for a stop direction and use bounded throttle for a go direction.
    This is a physical test program, not a legal compliance decision.
    """
    suffix = behavior_suffix(case_id)
    if (not isinstance(source_intake, dict) or
            source_intake.get("format") != "worker-subsection-2-officer-source-intake" or
            not isinstance(source_intake.get("site_id"), str) or
            not source_intake["site_id"] or
            (suffix not in REFERENCE_SUFFIXES and
             (not isinstance(source_intake.get("officer_source"), str) or
              not source_intake["officer_source"]))):
        raise ValueError("Officer site and actor source intake required")
    if not isinstance(approach_state, ApproachState):
        raise ValueError("Stopping-reference approach state required")
    if (not isinstance(reference, dict) or
            type(reference.get('x_m')) not in (int, float) or
            not math.isfinite(reference['x_m']) or
            not isinstance(reference.get('source'), str) or not reference['source']):
        raise ValueError('Sourced finite stopping reference required')
    if not callable(camera_readback):
        raise ValueError("Four-camera readback adapter required")
    ego_before = _body(ego)
    _body(other)
    pose = apply_direction(officer, bone_adapter, case_id, frame_index,
                           frame_count, go_frame)
    if suffix == "officer_present_inactive" or suffix in REFERENCE_SUFFIXES:
        command = control_step(approach_state,
                               front_x_m=max(point[0] for point in ego_before),
                               speed_mps=_speed(ego), reference=reference,
                               hold_ticks=hold_ticks)
    elif pose["programmed_direction"] == "stop":
        command = {"throttle": 0.0, "brake": 1.0, "phase": "officer_stop_program"}
    elif pose["programmed_direction"] == "go":
        command = {"throttle": 0.35, "brake": 0.0, "phase": "officer_go_program"}
    else:
        raise ValueError("Active officer direction missing")
    applied = _control(carla, ego, command)
    native_frame = world.tick()
    if type(native_frame) is not int or native_frame < 0:
        raise ValueError("Native world tick frame missing")
    cameras = camera_readback(native_frame)
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError("Four original camera frames required")
    for name in CAMERAS:
        camera = cameras[name]
        if (not isinstance(camera, dict) or camera.get("carla_frame") != native_frame or
                not isinstance(camera.get("raw_source"), str) or
                not camera["raw_source"]):
            raise ValueError("Original camera frame mismatch: " + name)
    ego_body = _body(ego)
    other_body = _body(other)
    ego_speed = _speed(ego)
    return {"case_id": case_id, "frame_index": frame_index,
            "carla_frame": native_frame, "site_id": source_intake["site_id"],
            "officer_source": source_intake["officer_source"],
            "officer_program": pose, "ego_control": applied,
            "ego_actor_id": ego.id, "other_actor_id": other.id,
            "ego_body_vertices_xy_m": ego_body,
            "other_body_vertices_xy_m": other_body,
            "ego_speed_mps": ego_speed, "other_speed_mps": _speed(other),
            "stopping_reference": reference,
            "ego_front_x_m": max(point[0] for point in ego_body),
            "ego_engineering_stop_before_reference_sample":
            ego_speed <= 0.05 and max(point[0] for point in ego_body) <= reference["x_m"],
            "camera_raw_sources": cameras,
            "officer_direction_observed": "unreviewed",
            "actual_police_control_observed": "unreviewed"}
