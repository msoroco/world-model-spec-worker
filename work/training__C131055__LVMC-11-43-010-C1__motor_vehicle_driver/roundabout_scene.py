"""Authored two-lane roundabout and matched left-turn lane policy requests."""

import math

CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}
LANES = {"left_lane": 12.0, "right_lane": 16.0,
         "u_turn_left_lane": 12.0, "u_turn_right_lane": 16.0}


def intent(case):
    return "u_turn" if case.startswith("u_turn_") else "left_turn"


def request(case):
    if case not in LANES:
        raise ValueError("Unknown lane policy")
    radius = LANES[case]
    turn = intent(case)
    sweep = 2 * math.pi if turn == "u_turn" else 3 * math.pi / 2
    points = []
    for i in range(49):
        theta = -math.pi / 2 + i * sweep / 48
        points.append({"x_m": radius * math.cos(theta), "y_m": radius * math.sin(theta),
                       "heading_deg": (math.degrees(theta) + 90) % 360})
    return {"format": "worker-authored-roundabout-request", "case": case,
            "cell_id": "C131055", "intent": turn + "_exit", "entry_arm": "south",
            "exit_arm": "south" if turn == "u_turn" else "west",
            "geometry": {"center_xy_m": [0, 0], "island_radius_m": 8,
                         "left_lane_center_radius_m": 12, "right_lane_center_radius_m": 16,
                         "lane_half_width_m": 1.5, "entry_arm_south_y_m": -40,
                         "exit_arm_west_x_m": -40},
            "ego": {"blueprint": "vehicle.tesla.model3", "initial_xy_m": [0, -40],
                    "heading_deg": 90, "requested_circulatory_lane": case,
                    "requested_speed_mps": 4},
            "controller": {"policy": "follow_waypoints_at_requested_lane_radius",
                           "circulatory_waypoints": points,
                           "exit_heading_deg": 270 if turn == "u_turn" else 180,
                           "lane_change_requested": False},
            "cameras": [{"name": "overview", "xyz": [0, 0, 45], "pitch": -90, "size": [1920, 1080]},
                        {"name": "approach", "xyz": [0, -30, 15], "pitch": -35,
                         "size": [1280, 720]},
                        {"name": "reference_corner", "xyz": [-24, -12, 18], "pitch": -35,
                         "size": [1280, 720]},
                        {"name": "driver_reference", "xyz": [0, -18, 9], "pitch": -18,
                         "size": [1280, 720]}],
            "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
            "native_topology_verified": False, "physical_success_claimed": False}


def validate(value):
    geometry = value["geometry"]
    if not 0 < geometry["island_radius_m"] < geometry["left_lane_center_radius_m"] < geometry["right_lane_center_radius_m"]:
        raise ValueError("Roundabout lane ordering invalid")
    points = value["controller"]["circulatory_waypoints"]
    turn = intent(value["case"])
    end = points[-1]
    if len(points) != 49 or abs(points[0]["x_m"]) > 1e-6:
        raise ValueError("Roundabout arc missing")
    if turn == "left_turn" and (abs(end["x_m"] + LANES[value["case"]]) > 1e-6 or
                                abs(end["y_m"]) > 1e-6 or value["exit_arm"] != "west"):
        raise ValueError("Left-turn arc missing")
    if turn == "u_turn" and (abs(end["x_m"]) > 1e-6 or
                              abs(end["y_m"] + LANES[value["case"]]) > 1e-6 or
                              value["exit_arm"] != "south"):
        raise ValueError("U-turn arc missing")
    if {c["name"] for c in value["cameras"]} != CAMERAS:
        raise ValueError("Four camera requests missing")
    if value["rate_hz"] != 20 or value["planned_frames"] != 600 or value["native_topology_verified"]:
        raise ValueError("Capture duration or source assertion invalid")
    return {"case": value["case"], "intent": turn, "waypoint_count": len(points),
            "camera_count": 4, "planned_frames": 600, "native_topology_verified": False}
