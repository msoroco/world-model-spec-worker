"""Authored two-lane roundabout and matched left-turn lane policy requests."""

import math

CAMERAS = {"overview", "ego_front", "entry_lane", "exit_lane"}
LANES = {"left_lane": 12.0, "right_lane": 16.0}


def request(case):
    if case not in LANES:
        raise ValueError("Unknown lane policy")
    radius = LANES[case]
    points = []
    for i in range(49):
        theta = -math.pi / 2 + i * (3 * math.pi / 2) / 48
        points.append({"x_m": radius * math.cos(theta), "y_m": radius * math.sin(theta),
                       "heading_deg": (math.degrees(theta) + 90) % 360})
    return {"format": "worker-authored-roundabout-request", "case": case,
            "cell_id": "C131055", "intent": "left_turn_exit", "entry_arm": "south", "exit_arm": "west",
            "geometry": {"center_xy_m": [0, 0], "island_radius_m": 8,
                         "left_lane_center_radius_m": 12, "right_lane_center_radius_m": 16,
                         "lane_half_width_m": 1.5, "entry_arm_south_y_m": -40,
                         "exit_arm_west_x_m": -40},
            "ego": {"blueprint": "vehicle.tesla.model3", "initial_xy_m": [0, -40],
                    "heading_deg": 90, "requested_circulatory_lane": case,
                    "requested_speed_mps": 4},
            "controller": {"policy": "follow_waypoints_at_requested_lane_radius",
                           "circulatory_waypoints": points, "exit_heading_deg": 180,
                           "lane_change_requested": False},
            "cameras": [{"name": "overview", "xyz": [0, 0, 35], "pitch": -90, "size": [1920, 1080]},
                        {"name": "ego_front", "xyz": [1, 0, 2], "pitch": -8,
                         "attach_to_ego": True, "size": [1280, 720]},
                        {"name": "entry_lane", "xyz": [12, -26, 9], "pitch": -25, "size": [1280, 720]},
                        {"name": "exit_lane", "xyz": [-25, 12, 9], "pitch": -25, "size": [1280, 720]}],
            "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
            "native_topology_verified": False, "physical_success_claimed": False}


def validate(value):
    geometry = value["geometry"]
    if not 0 < geometry["island_radius_m"] < geometry["left_lane_center_radius_m"] < geometry["right_lane_center_radius_m"]:
        raise ValueError("Roundabout lane ordering invalid")
    points = value["controller"]["circulatory_waypoints"]
    if len(points) != 49 or abs(points[0]["x_m"]) > 1e-6 or abs(points[-1]["x_m"] + LANES[value["case"]]) > 1e-6:
        raise ValueError("Left-turn arc missing")
    if {c["name"] for c in value["cameras"]} != CAMERAS:
        raise ValueError("Four camera requests missing")
    if value["rate_hz"] != 20 or value["planned_frames"] != 600 or value["native_topology_verified"]:
        raise ValueError("Capture duration or source assertion invalid")
    return {"case": value["case"], "waypoint_count": len(points),
            "camera_count": 4, "planned_frames": 600, "native_topology_verified": False}
