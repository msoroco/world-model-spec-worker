"""Source-bound bridge or viaduct approach measurement; no legal verdict."""

from measure_tunnel import CAMERAS, FRAMES, METRES_IN_100_FEET, RATE_HZ, finite, sha


KINDS = {"bridge", "viaduct"}


def measure(context, rows):
    kind = context.get("structure_kind")
    if kind not in KINDS or context.get("source_kind") != "original_native_structure_map_and_ray_readback":
        raise ValueError("Missing original Native bridge or viaduct source")
    for name in ("native_map_sha256", "structure_geometry_sha256",
                 "road_direction_survey_sha256", "centreline_geometry_sha256",
                 "vehicle_extent_sha256", "sight_ray_source_sha256"):
        sha(context.get(name), name)
    approach_x = finite(context.get("approach_structure_x_m"), "structure start")
    centre_y = finite(context.get("highway_centre_y_m"), "highway centre")
    if context.get("one_way_native_survey") is not False:
        raise ValueError("Opposed-lane Native survey required")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    previous_native = None
    in_zone = []
    left_of_centre = []
    occluded = []
    sight_brackets = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("video_frame") != index:
            raise ValueError("Video frame identity gap")
        native = row.get("native_frame")
        if type(native) is not int or (previous_native is not None and native <= previous_native):
            raise ValueError("Native frame identity gap")
        previous_native = native
        if abs(finite(row.get("time_s"), "Native time") - index / RATE_HZ) > 1e-6:
            raise ValueError("Native time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(
                cameras[name] != index for name in CAMERAS):
            raise ValueError("Four source camera frame join failed")
        body = row.get("body_xy_m")
        if not isinstance(body, list) or len(body) != 4 or any(
                not isinstance(point, list) or len(point) != 2 for point in body):
            raise ValueError("Full vehicle body source missing")
        points = [(finite(point[0], "body x"), finite(point[1], "body y")) for point in body]
        speed = finite(row.get("observed_speed_mps"), "observed speed")
        if speed < 0:
            raise ValueError("Negative observed speed")
        front = max(point[0] for point in points)
        rear = min(point[0] for point in points)
        distance = approach_x - front
        zone = speed > .10 and rear < approach_x and 0 <= distance <= METRES_IN_100_FEET
        in_zone.append(zone)
        left_of_centre.append(min(point[1] for point in points) > centre_y)
        ray = row.get("incoming_lane_sight_ray")
        if not isinstance(ray, dict) or ray.get("status") not in {"blocked", "clear_to_limit", "unknown"}:
            raise ValueError("Incoming-lane sight ray source missing")
        lower = finite(ray.get("clear_lower_bound_m"), "sight lower bound")
        upper = ray.get("blocker_upper_bound_m")
        if upper is not None:
            upper = finite(upper, "sight upper bound")
        if lower < 0 or (upper is not None and upper < lower):
            raise ValueError("Invalid sight bracket")
        if ray["status"] == "blocked" and upper is None:
            raise ValueError("Blocked ray lacks blocker bracket")
        if ray["status"] == "clear_to_limit" and upper is not None:
            raise ValueError("Clear ray cannot name blocker")
        occluded.append(ray["status"] == "blocked")
        if zone:
            sight_brackets.append({"frame": index, "status": ray["status"],
                                   "clear_lower_bound_m": lower,
                                   "blocker_upper_bound_m": upper})
    if not any(in_zone):
        raise ValueError("No approach inside 100-foot structure zone")
    return {"format": "worker-source-structure-approach-measurement",
            "structure_kind": kind, "frame_count": FRAMES, "rate_hz": RATE_HZ,
            "one_way_highway_surveyed": False,
            "within_100_ft_driving_frames": sum(in_zone),
            "left_of_centre_within_zone_frames": sum(z and left for z, left in zip(in_zone, left_of_centre)),
            "blocked_sight_within_zone_frames": sum(z and blocked for z, blocked in zip(in_zone, occluded)),
            "left_and_blocked_within_zone_frames": sum(z and left and blocked for z, left, blocked in zip(in_zone, left_of_centre, occluded)),
            "sight_brackets_in_zone": sight_brackets,
            "legal_view_obstructed": "independent_judgment_required",
            "legal_compliance": "unassessed",
            "limitations": ["Virtual incoming-lane rays are a proxy, not legal driver-eye obstruction",
                            "Original structure geometry and pixels require independent review",
                            "A whole-body left-of-centre sample is an engineering detector, not a legal cutoff"]}
