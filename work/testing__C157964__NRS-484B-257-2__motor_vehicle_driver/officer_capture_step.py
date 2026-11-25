"""One synchronous Native step for the three exact officer comparison cases.

The programmed arm pose and controller command are construction facts. Raw
camera frame references are kept separately for later original-frame review.
"""

import math

from officer_direction import apply_direction
from officer_ego_controller import apply_native, command


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _speed(actor):
    velocity = actor.get_velocity()
    values = (velocity.x, velocity.y, velocity.z)
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise ValueError("Native ego speed readback missing")
    return math.sqrt(sum(value * value for value in values))


def step(carla, world, ego, officer, bone_adapter, case_id, frame_index,
         frame_count, traffic_sample, camera_readback, source_intake,
         target_speed_mps=5.0, officer_go_frame=None, ego_hold_until_frame=None):
    """Command one tick and bind all four raw camera sources to its frame.

    ``traffic_sample`` is supplied by a source adapter for actor-body
    occupancy and reviewed approaching-hazard judgment. This function refuses
    absent source references. It never derives legal hazard from distance.
    """
    if (not isinstance(source_intake, dict) or
            source_intake.get("format") != "worker-officer-subsection-2-source-intake" or
            not source_intake.get("site_id")):
        raise ValueError("Reviewed officer site intake required")
    if not isinstance(traffic_sample, dict) or not traffic_sample.get("source"):
        raise ValueError("Original other-traffic source required")
    if type(traffic_sample.get("other_inside")) is not bool or type(traffic_sample.get("approaching_hazard")) is not bool:
        raise ValueError("Sourced other-body and approaching-hazard inputs required")
    if (traffic_sample.get("site_id") != source_intake["site_id"] or
            type(traffic_sample.get("other_actor_id")) is not int or
            not isinstance(traffic_sample.get("other_body_vertices_xy_m"), list) or
            len(traffic_sample["other_body_vertices_xy_m"]) < 4 or
            not isinstance(traffic_sample.get("hazard_source"), str) or
            not traffic_sample["hazard_source"]):
        raise ValueError("Native other body and hazard source binding required")
    if not callable(camera_readback):
        raise ValueError("Four-camera readback adapter required")
    pose = apply_direction(officer, bone_adapter, case_id, frame_index, frame_count,
                           officer_go_frame)
    selected = command(case_id, pose["programmed_direction"],
                       other_inside=traffic_sample["other_inside"],
                       approaching_hazard=traffic_sample["approaching_hazard"],
                       current_speed_mps=_speed(ego), target_speed_mps=target_speed_mps)
    if ego_hold_until_frame is not None:
        if type(ego_hold_until_frame) is not int or not 0 <= ego_hold_until_frame < frame_count:
            raise ValueError("Ego hold release frame outside capture")
        if frame_index < ego_hold_until_frame:
            selected = {"throttle": 0.0, "brake": 1.0, "proceed": False,
                        "basis": "bounded physical ego hold command"}
    control = apply_native(carla, ego, selected)
    native_frame = world.tick()
    if type(native_frame) is not int:
        raise ValueError("Native world tick frame missing")
    cameras = camera_readback(native_frame)
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError("Four original camera frames required")
    for name in CAMERAS:
        frame = cameras[name]
        if (not isinstance(frame, dict) or frame.get("carla_frame") != native_frame or
                not isinstance(frame.get("raw_source"), str) or not frame["raw_source"]):
            raise ValueError("Original camera frame mismatch: " + name)
    return {"case_id": case_id, "frame_index": frame_index, "carla_frame": native_frame,
            "reviewed_site_id": source_intake["site_id"],
            "officer_program": pose, "ego_control": control,
            "traffic_source": traffic_sample, "camera_raw_sources": cameras,
            "officer_direction_observed": "unreviewed",
            "actual_police_control_observed": "unreviewed"}
