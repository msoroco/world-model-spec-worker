"""Join original Native body, ray, and exception readbacks by exact frame."""

from __future__ import annotations

from math import sqrt

from rail_sight import FRAME_RATE


def joined_row(frame, body, rays, reviews, flagman, signal):
    if not isinstance(frame, int) or frame < 0 or body.get("frame") != frame or rays.get("frame") != frame:
        raise ValueError("original body and rail ray Native frame join failed")
    for name, source in (("flagman", flagman), ("signal", signal)):
        if source.get("frame") != frame or not source.get("source_ref"):
            raise ValueError("original " + name + " frame and source join failed")
    railway = reviews["railway"]
    approach = reviews["approach"]
    if rays.get("review_source_sha256") != railway["source_sha256"]:
        raise ValueError("rail ray source review hash differs")
    if body.get("actor_id") != rays.get("ego_actor_id") or not body.get("actor_type_id", "").startswith("vehicle."):
        raise ValueError("original motor vehicle body identity differs")
    crossing = railway["crossing_xyz_m"]
    ux, uy = approach["approach_direction_xy"]
    if abs((ux*ux+uy*uy)**.5-1) > 1e-6:
        raise ValueError("approach axis is not unit length")
    vertices = body.get("body_vertices_m")
    if not isinstance(vertices, list) or len(vertices) != 8:
        raise ValueError("original motor vehicle body vertices required")
    progress = [(float(v[0])-crossing[0])*ux + (float(v[1])-crossing[1])*uy for v in vertices]
    velocities = body.get("velocity_mps")
    if not isinstance(velocities, list) or len(velocities) != 3:
        raise ValueError("original vehicle velocity readback required")
    speed = sqrt(sum(float(v)**2 for v in velocities))
    if any(type(flagman.get(key)) is not bool for key in ("on_duty",)):
        raise ValueError("original flagman duty readback required")
    if any(type(signal.get(key)) is not bool for key in ("installed", "visible", "indicates_approach")):
        raise ValueError("original crossing signal state readback required")
    directions = rays.get("directions", {})
    if set(directions) != {"left", "right"}:
        raise ValueError("both original railway sight directions required")
    for side in ("left", "right"):
        if not directions[side].get("actor_id") or not directions[side].get("rail_rays") or not directions[side].get("body_rays"):
            raise ValueError("original railway traffic and ray records required")
        position = directions[side].get("actor_position_m")
        if not isinstance(position, list) or len(position) != 3:
            raise ValueError("original railway traffic position required")
    crossing_ray = rays.get("crossing", {})
    if type(crossing_ray.get("clear")) is not bool or not crossing_ray.get("method"):
        raise ValueError("original crossing sight ray required")
    eye = rays.get("observer_m")
    if not isinstance(eye, list) or len(eye) != 3:
        raise ValueError("original moving observer position required")
    return {
        "frame": frame, "time_s": frame / FRAME_RATE,
        "distance_to_crossing_m": -max(progress),
        "traversing_grade_crossing": min(progress) <= 0 <= max(progress),
        "speed_mps": speed,
        "rail_left_clear_distance_m": float(directions["left"]["clear_distance_m"]),
        "rail_right_clear_distance_m": float(directions["right"]["clear_distance_m"]),
        "crossing_visible": crossing_ray["clear"],
        "left_traffic_visible": bool(directions["left"]["rail_vehicle_visible_proxy"]),
        "right_traffic_visible": bool(directions["right"]["rail_vehicle_visible_proxy"]),
        "flagman_on_duty": flagman["on_duty"],
        "crossing_signal_installed_visible": signal["installed"] and signal["visible"],
        "signal_indicates_train_approach": signal["indicates_approach"],
        "observer_pose_source": "original-ego-body:" + str(body["actor_id"]) + ":" + str(frame),
        "observer_xy_m": eye[:2],
        "rail_ray_source": "original-world-cast-ray:" + str(frame),
        "rail_vehicle_source_refs": ["original-actor:" + str(directions[s]["actor_id"]) for s in ("left", "right")],
        "rail_vehicle_positions_m": {s: directions[s]["actor_position_m"][:2]
                                     for s in ("left", "right")},
        "flagman_source_ref": flagman["source_ref"],
        "signal_source_ref": signal["source_ref"],
        "railway_review_sha256": railway["source_sha256"],
        "sight_method": "same-tick original world.cast_ray virtual observer proxy; physical review pending",
    }
