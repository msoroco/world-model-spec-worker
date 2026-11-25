"""Exact request-to-runner parameters for six signaling boundary probes."""
import hashlib
from cameras import camera_plan
from controller import EngineeringKnobs
from geometry import open_drive, route


def parameters(config):
    request = config["native_request"]
    case_id = config["case_id"]
    if request["case_id"] != case_id or request["candidate_id"] != config["candidate_id"]:
        raise ValueError("Materialized request identity differs from bundle")
    if (request["law_id"], request["cell_id"], request["actor"]) != (
        "NRS-484B-413-2", "C329610", "motor_vehicle_driver"):
        raise ValueError("Law, cell or actor changed")
    if request["rate_hz"] != 20 or request["duration_s"] != 40:
        raise ValueError("Capture interval changed")
    if hashlib.sha256(open_drive().encode()).hexdigest() != request["map_sha256"]:
        raise ValueError("Owned map differs from exact request")
    if request["signal_direction"] != "left" or request["turn_entry_x_m"] != -7:
        raise ValueError("Turn or signal direction changed")
    if abs((-7 - request["signal_onset_x_m"]) / .3048 - request["target_signal_distance_ft"]) > 1e-8:
        raise ValueError("Signaling target differs from requested station")
    authored_route = route(-1.75, start_x_m=request["start_x_m"])
    if request["route_xy_m"] != authored_route:
        raise ValueError("Request route differs from owned geometry")
    knobs = EngineeringKnobs(target_speed_mps=request["target_speed_mps"])
    knobs.validate()
    cameras = camera_plan(config["candidate_id"])
    if (config["candidate_id"] == "fallback3") != (request["camera_policy"] == "overview_shifted_left"):
        raise ValueError("Camera fallback identity differs")
    return {"authored_route_xy_m": authored_route,
            "native_route_xy_m": [[x,-y] for x,y in authored_route],
            "controller_knobs": knobs, "cameras": cameras,
            "signal_onset_x_m": request["signal_onset_x_m"],
            "start_x_m": request["start_x_m"],
            "target_signal_distance_ft": request["target_signal_distance_ft"],
            "area": request["area"], "weather": request["weather"]}
