"""Controlled Native requests for the restricted-zone parking cell.

The requests encode construction differences, never observed purpose or legality.
"""

from __future__ import annotations

import math
import hashlib

from parking_controller import ParkingPlan
from geometry import check as geometry_check, open_drive

AID = "training__C135709__NRS-484B-510__motor_vehicle_driver"
CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
CASES = {
    "witness_1": {"requested_purpose": "zone_restricted_purpose",
                  "passenger_exchange_request": False, "waiting_vehicle_request": False,
                  "comparison_variable": "restricted_zone_purpose"},
    "witness_2": {"requested_purpose": "unrelated_purpose",
                  "passenger_exchange_request": False, "waiting_vehicle_request": False,
                  "comparison_variable": "restricted_zone_purpose"},
    "exception_1_1": {"requested_purpose": "passenger_loading",
                      "passenger_exchange_request": True, "waiting_vehicle_request": False,
                      "comparison_variable": "exception_1_applicability"},
    "exception_1_2": {"requested_purpose": "passenger_loading",
                      "passenger_exchange_request": True, "waiting_vehicle_request": True,
                      "comparison_variable": "exception_1_applicability"},
    "stop_only": {"requested_purpose": "unrelated_purpose",
                  "passenger_exchange_request": False, "waiting_vehicle_request": False,
                  "comparison_variable": "stationary_episode", "departure_frame": 300},
    "stand_only": {"requested_purpose": "unrelated_purpose",
                   "passenger_exchange_request": False, "waiting_vehicle_request": False,
                   "comparison_variable": "stationary_episode", "departure_frame": 500},
}


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def build(suffix: str, *, stop_center_x_m: float = 5.0,
          approach_speed_cap_mps: float = 4.0) -> dict:
    require(suffix in CASES, "unknown exact restricted-zone case")
    require(approach_speed_cap_mps in (3.0, 4.0),
            "only tested same-case approach caps are supported")
    require(isinstance(stop_center_x_m, (float, int)) and
            math.isfinite(stop_center_x_m), "finite parking target required")
    motion = ParkingPlan(target_center_x_m=float(stop_center_x_m),
                         max_speed_mps=float(approach_speed_cap_mps))
    motion.validate()
    case = CASES[suffix]
    geometry = geometry_check()
    return {"assignment_id": AID, "case_id": f"{AID}__{suffix}",
            "frozen_cell": {"layout": "narrow_road", "maneuver": "park",
                            "control": "parking_restriction_device"},
            "actor": "motor_vehicle_driver", "frames": 600, "fps": 20,
            "duration_s": 30, "camera_sizes": CAMERAS,
            "zone_x0_m": motion.zone_x0_m, "zone_x1_m": motion.zone_x1_m,
            "requested_zone_bounds_m": geometry["requested_zone_bounds_m"],
            "requested_sign_id": geometry["sign_id"],
            "requested_restricted_purpose": geometry["requested_restricted_purpose"],
            "requested_open_drive_sha256": hashlib.sha256(open_drive().encode()).hexdigest(),
            "parking_target_center_x_m": motion.target_center_x_m,
            "primary_max_speed_mps": motion.max_speed_mps,
            "passenger_vehicle_required": suffix.startswith("exception_"),
            "requested_purpose": case["requested_purpose"],
            "passenger_exchange_request": case["passenger_exchange_request"],
            "waiting_vehicle_request": case["waiting_vehicle_request"],
            "departure_frame": case.get("departure_frame"),
            "comparison_variable": case["comparison_variable"],
            "original_source_requirements": [
                "original OpenDRIVE bytes and restricted-zone survey",
                "posted sign pixels and authority review",
                "full ego body and speed every frame",
                "nearby passenger actor identities and requested door controls",
                "independent review of actual passenger loading",
                "other vehicle body and entry route",
                "four complete synchronized FFV1 camera videos"],
            "physical_risk": ["parking footprint may miss the narrow zone",
                              "a passenger exchange may not be visible or realized",
                              "waiting vehicle may block the target zone"],
            "fallback1": {"trigger": "primary ego footprint overshoots the surveyed zone",
                          "change": "reduce approach speed cap from 4 to 3 m/s with the same parking target",
                          "max_speed_mps": 3.0,
                          "same_case_and_observations": True},
            "source_kind": "prospective_native_request",
            "purpose_observed": False, "physical_acceptance_claimed": False,
            "legal_conclusion": None}


def validate_matrix() -> dict:
    plans = {suffix: build(suffix) for suffix in CASES}
    require(len({p["case_id"] for p in plans.values()}) == len(CASES),
            "distinct exact cases required")
    a, b = plans["witness_1"], plans["witness_2"]
    require(a["requested_purpose"] != b["requested_purpose"] and
            all(a[key] == b[key] for key in ("frames", "fps", "duration_s",
                                           "camera_sizes", "parking_target_center_x_m",
                                           "passenger_exchange_request", "waiting_vehicle_request")),
            "purpose pair must isolate the requested purpose")
    a, b = plans["exception_1_1"], plans["exception_1_2"]
    require(a["waiting_vehicle_request"] != b["waiting_vehicle_request"] and
            all(a[key] == b[key] for key in ("frames", "fps", "duration_s",
                                           "camera_sizes", "parking_target_center_x_m",
                                           "passenger_exchange_request", "requested_purpose")),
            "exception pair must isolate waiting vehicle request")
    a, b, c = plans["stop_only"], plans["stand_only"], plans["witness_2"]
    require((a["departure_frame"], b["departure_frame"], c["departure_frame"]) ==
            (300, 500, None) and
            all(a[key] == b[key] == c[key] for key in
                ("requested_purpose", "passenger_exchange_request",
                 "waiting_vehicle_request", "camera_sizes", "duration_s",
                 "parking_target_center_x_m")),
            "stationary episodes must isolate departure timing")
    return {"plans": plans, "comparison_count": 4,
            "original_native_observed": False, "ready": False}
