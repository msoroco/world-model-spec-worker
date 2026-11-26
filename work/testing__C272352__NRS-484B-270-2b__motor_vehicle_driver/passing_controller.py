"""Per-frame physical pass intent; no legal safety or due-care conclusion."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class Sample:
    original_frame: int
    ego_rear_m: float
    ego_front_m: float
    bicycle_rear_m: float
    bicycle_front_m: float
    ego_lateral_m: float
    bicycle_left_m: float
    target_clearance_m: float
    opposing_path_clear: bool
    centerline_source: str
    zone_source: str
    traffic_source: str
    body_source: str


def command(case, sample):
    if case.get("case_id", "").split("__")[0] != "testing" or \
            case.get("control_kind") not in {"bicycle", "electric_bicycle", "electric_scooter"}:
        raise ValueError("exact qualifying case required")
    if sample.original_frame < 0 or not all(isfinite(x) for x in (
            sample.ego_rear_m, sample.ego_front_m, sample.bicycle_rear_m,
            sample.bicycle_front_m, sample.ego_lateral_m,
            sample.bicycle_left_m, sample.target_clearance_m)):
        raise ValueError("original finite motion required")
    if sample.ego_rear_m > sample.ego_front_m or sample.bicycle_rear_m > sample.bicycle_front_m:
        raise ValueError("invalid measured body envelopes")
    if sample.target_clearance_m < 0:
        raise ValueError("negative requested clearance")
    if sample.target_clearance_m != case.get("target_clearance_m"):
        raise ValueError("sampled clearance target differs from exact case")
    route = case.get("route_request")
    if route not in {"within_right_half", "centerline", "no_passing_zone"}:
        raise ValueError("exact route request required")
    if not all((sample.centerline_source, sample.zone_source,
                sample.traffic_source, sample.body_source)):
        raise ValueError("missing original source readback")
    if not sample.opposing_path_clear:
        return {"frame": sample.original_frame, "mode": "hold_back",
                "reason": "sampled opposing path occupied", "route_request": route,
                "target_clearance_m": sample.target_clearance_m, "legal_safety": None}
    clear = sample.ego_rear_m > sample.bicycle_front_m
    if clear:
        mode = "return_right"
    elif sample.ego_lateral_m < sample.bicycle_left_m + sample.target_clearance_m:
        mode = "establish_left_clearance"
    else:
        mode = "continue_left_pass"
    if case.get("return_request") == "early" and not clear:
        # This exact experimental variant requests and records the early return.
        # It is an observed statutory contrast, never a safe/legal assertion.
        mode = "return_right_early_requested"
    return {"frame": sample.original_frame, "mode": mode,
            "reason": "measured body ordering and source-checked traffic",
            "route_request": route, "target_clearance_m": sample.target_clearance_m,
            "legal_safety": None}
