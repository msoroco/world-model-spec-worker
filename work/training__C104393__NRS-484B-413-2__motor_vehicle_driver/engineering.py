"""Exact authored request validation for C104393 hill-crest constructions."""
import hashlib

from controller import EngineeringKnobs
from geometry import open_drive, route, signal_start


def parameters(config):
    request = config["native_request"]
    identity = ("NRS-484B-413-2", "C104393", "motor_vehicle_driver")
    if (config["law_id"], config["cell_id"], config["actor"]) != identity:
        raise ValueError("Frozen assignment identity changed")
    if (request["case_id"], request["candidate_id"]) != (config["case_id"], config["candidate_id"]):
        raise ValueError("Exact request identity changed")
    if request["rate_hz"] != config["rate_hz"] or request["duration_s"] != config["duration_s"]:
        raise ValueError("Capture interval changed")
    if (request["rate_hz"], request["duration_s"]) != (20, 42):
        raise ValueError("Unplanned capture interval")
    candidate = config["candidate_id"]
    radius = 24.0 if candidate == "fallback1" else 20.0
    lookahead = 3.0 if candidate == "fallback2" else 4.0
    if request["turn_radius_m"] != radius or request["controller_lookahead_m"] != lookahead:
        raise ValueError("Candidate engineering knobs changed")
    if request["signal_start_ft"] not in (90, 100, 110, 290, 300, 310):
        raise ValueError("Unplanned signal distance")
    if request["area"] != "any_other_area" or request["weather"] not in ("clear_noon", "heavy_rain_noon"):
        raise ValueError("Unplanned area or weather context")
    if config["case_id"].split("__")[-1] != str(request["signal_start_ft"]):
        raise ValueError("Case suffix differs from signal request")
    if request["signal_start_station_m"] != signal_start(request["signal_start_ft"]):
        raise ValueError("Signal onset differs from authored station")
    if request["map_sha256"] != hashlib.sha256(open_drive(radius).encode()).hexdigest():
        raise ValueError("Owned OpenDRIVE differs from pinned request")
    points = route(radius)
    if request["route_sha256"] != hashlib.sha256(__import__("json").dumps(points, separators=(",", ":")).encode()).hexdigest():
        raise ValueError("Owned route differs from pinned request")
    knobs = EngineeringKnobs(lookahead_base_m=lookahead, target_speed_mps=5.0)
    knobs.validate()
    return {"radius_m": radius, "authored_route_xyz_m": points,
            "native_route_xy_m": [[x, -y] for x, y, z in points],
            "controller_knobs": knobs, "signal_start_x_m": request["signal_start_station_m"] - 130,
            "signal_start_ft": request["signal_start_ft"], "weather": request["weather"],
            "area": request["area"]}
