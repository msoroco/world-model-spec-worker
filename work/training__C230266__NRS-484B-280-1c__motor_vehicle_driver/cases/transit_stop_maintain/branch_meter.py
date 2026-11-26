"""Source-bound, nonlegal measurements for all NRS 484B.280(1)(c) positions."""

import hashlib
import json
import math


BRANCH_SOURCES = {
    "road": ("road_boundary_source", "pedestrian_position_source"),
    "bus_stop": ("bus_stop_designation_source", "bus_stop_geometry_source", "pedestrian_position_source"),
    "bench": ("bench_geometry_source", "bench_public_mass_transport_use_source", "pedestrian_position_source"),
    "shelter": ("shelter_geometry_source", "shelter_public_mass_transport_use_source", "pedestrian_position_source"),
    "transit_stop": ("stop_designation_source", "stop_furniture_geometry_source", "pedestrian_position_source"),
    "boarding": ("transit_vehicle_class_source", "door_side_source", "boarding_motion_source"),
    "other_transport": ("other_public_transport_class_source", "door_side_source", "boarding_motion_source"),
    "school_zone": ("school_zone_sign_source", "governed_zone_extent_source", "pedestrian_position_source"),
    "school_crossing": ("school_crossing_sign_source", "governed_zone_extent_source", "pedestrian_position_source"),
    "marked_crosswalk": ("marked_crosswalk_source", "pedestrian_position_source"),
    "unmarked_crosswalk": ("intersection_and_sidewalk_source", "unmarked_crossing_limits_source", "pedestrian_position_source"),
}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _require(value, message):
    if not value:
        raise ValueError(message)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(packet):
    _require(packet.get("format") == "worker-pedestrian-caution-branch-source-v1", "Wrong source format")
    _require(packet.get("law_id") == "NRS-484B-280-1c" and packet.get("cell_id") == "C230266"
             and packet.get("actor") == "motor_vehicle_driver", "Wrong assignment scope")
    branch = packet.get("branch")
    _require(branch in BRANCH_SOURCES, "Unknown statutory alternative")
    _require(packet.get("pedestrian_id") and packet.get("ego_id") and
             packet["pedestrian_id"] != packet["ego_id"] and
             packet.get("pedestrian_classification_source"), "Distinct sourced actor identity required")
    survey = packet.get("survey")
    _require(isinstance(survey, dict), "Original context survey missing")
    for key in BRANCH_SOURCES[branch]:
        _require(isinstance(survey.get(key), str) and survey[key].strip(), f"Missing original {key}")
    trace = packet.get("trace")
    _require(isinstance(trace, list) and len(trace) == 600, "Full 600-frame trace required")
    _require(_digest(trace) == packet.get("trace_sha256"), "Stale trace hash")
    first_observed = None
    visible = 0
    context_frames = 0
    speed = []
    distances = []
    for frame, row in enumerate(trace):
        _require(row.get("frame") == frame and row.get("video_frame") == frame and
                 row.get("native_frame") is not None and
                 _finite(row.get("time_s")) and abs(row["time_s"] - frame / 20) < 1e-8,
                 "Frame/video/Native time join failed")
        for key in ("ego_x_m", "ego_y_m", "ped_x_m", "ped_y_m", "ego_speed_mps"):
            _require(_finite(row.get(key)), f"Missing measured {key}")
        _require(row["ego_speed_mps"] >= 0, "Negative source speed")
        _require(type(row.get("line_of_sight_clear")) is bool, "Original visibility sample missing")
        observed = row.get("driver_observed_pedestrian")
        _require(observed is None or type(observed) is bool, "Invalid driver observation sample")
        _require(not observed or row.get("driver_observation_source"), "Actual observation provenance missing")
        _require(type(row.get("branch_position_evidenced")) is bool,
                 "Original statutory-position sample missing")
        if observed and first_observed is None:
            first_observed = frame
        visible += row["line_of_sight_clear"]
        context_frames += row["branch_position_evidenced"]
        speed.append(row["ego_speed_mps"])
        distances.append(math.hypot(row["ego_x_m"] - row["ped_x_m"],
                                    row["ego_y_m"] - row["ped_y_m"]))
    _require(context_frames > 0, "Statutory position never evidenced")
    _require(visible > 0, "No sourced line of sight")
    return {
        "format": "worker-pedestrian-caution-branch-measurement-v1", "branch": branch,
        "trace_sha256": packet["trace_sha256"], "frames": 600, "rate_hz": 20,
        "position_evidenced_frames": context_frames,
        "line_of_sight_frames": visible,
        "first_actual_observation_frame": first_observed,
        "speed_at_first_observation_mps": speed[first_observed] if first_observed is not None else None,
        "speed_two_seconds_later_mps": speed[min(first_observed + 40, 599)] if first_observed is not None else None,
        "minimum_centre_distance_m": min(distances),
        "actual_driver_observation_unverified": first_observed is None,
        "proper_caution_legal_verdict": None,
        "physical_execution_proven": False,
    }
