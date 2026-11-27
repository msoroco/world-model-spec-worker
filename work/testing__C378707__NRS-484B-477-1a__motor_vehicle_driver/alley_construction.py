"""Source-gated construction targets for the exact business-district alley cases.

These are commands for a Native operator. The operator must read back actual
vehicle, passenger, goods and camera state; a request is never an observation.
"""
from __future__ import annotations

import math

ASSIGNMENT = "testing__C378707__NRS-484B-477-1a__motor_vehicle_driver"
VARIANTS = frozenset(("passenger_active_stop", "passenger_wait_stand",
                      "passenger_driver_exit_park", "goods_active_load",
                      "goods_wait_interrupted", "ordinance_passenger_authorized"))


def _point(value, label):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError("surveyed " + label + " missing")
    return [float(v) for v in value]


def _source(value, label):
    if (not isinstance(value, dict) or not isinstance(value.get("path"), str) or
            not value["path"] or not isinstance(value.get("sha256"), str) or
            len(value["sha256"]) != 64 or
            any(c not in "0123456789abcdef" for c in value["sha256"])):
        raise ValueError("reviewed " + label + " source missing")


def build_plan(site: dict, case_id: str, *, direction: int = 1) -> dict:
    """Return an executable target from reviewed site and actor source references."""
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("wrong business-alley assignment")
    variant = case_id.removeprefix(ASSIGNMENT + "__")
    if variant not in VARIANTS or type(direction) is not int or direction not in (-1, 1):
        raise ValueError("unknown exact case or approach direction")
    if (site.get("alley_kind") != "business_district_alley" or
            site.get("public_highway_status") is not True or
            site.get("business_district_reviewed") is not True or
            site.get("jurisdiction_reviewed") is not True):
        raise ValueError("qualifying business-district alley review missing")
    sources = site.get("reviewed_sources")
    if not isinstance(sources, dict):
        raise ValueError("reviewed site sources missing")
    for label in ("map", "alley", "business_frontage", "jurisdiction",
                  "vehicle_blueprint", "passenger_actor", "goods_actor"):
        _source(sources.get(label), label)
    if variant == "ordinance_passenger_authorized":
        _source(sources.get("ordinance"), "applicable local ordinance")
        if site.get("ordinance_status") != "reviewed_authorizes_passenger_loading":
            raise ValueError("applicable passenger-loading ordinance review missing")
    elif site.get("ordinance_status") != "reviewed_no_applicable_override":
        raise ValueError("local ordinance absence is not reviewed")
    start = _point(site.get("centerline_start_m"), "alley centerline start")
    end = _point(site.get("centerline_end_m"), "alley centerline end")
    span = [end[i] - start[i] for i in range(2)]
    length = math.hypot(*span)
    if length < 75:
        raise ValueError("surveyed approach cannot support enter, halt and depart")
    axis = [span[i] / length for i in range(2)]
    station = site.get("loading_station_m")
    if type(station) not in (int, float) or not math.isfinite(station) or not 30 <= station <= length - 20:
        raise ValueError("surveyed loading station outside alley approach")
    if site.get("loading_bay_reviewed") is not True:
        raise ValueError("loading destination and actor zone review missing")
    passenger = _point(site.get("passenger_zone_xy_m"), "passenger zone")
    goods = _point(site.get("goods_zone_xy_m"), "goods zone")
    target = [start[i] + axis[i] * station for i in range(2)]
    if any(math.dist(target, point) > 8 for point in (passenger, goods)):
        raise ValueError("loading actor zone is not adjacent to surveyed halt")
    def at(delta):
        return [target[i] + axis[i] * delta for i in range(2)]
    schedule = {
        "passenger_active_stop": {"passenger_board_s": [13, 20], "hold_s": [10, 28]},
        "passenger_wait_stand": {"passenger_board_s": [25, 30], "hold_s": [10, 35]},
        "passenger_driver_exit_park": {"passenger_board_s": [20, 26],
                                       "driver_exit_s": [14, 24], "hold_s": [10, 36]},
        "goods_active_load": {"goods_contact_s": [12, 25], "hold_s": [10, 30]},
        "goods_wait_interrupted": {"goods_contact_s": [[12, 16], [22, 26]],
                                   "hold_s": [10, 32]},
        "ordinance_passenger_authorized": {"passenger_board_s": [13, 20],
                                            "hold_s": [10, 28]},
    }[variant]
    return {
        "assignment_id": ASSIGNMENT, "case_id": case_id, "variant": variant,
        "approach_direction": direction, "reviewed_sources": sources,
        "start_xy_m": at(-direction * 28), "target_xy_m": target,
        "depart_xy_m": at(direction * 17), "route_axis_xy": axis,
        "passenger_zone_xy_m": passenger, "goods_zone_xy_m": goods,
        "schedule_request_s": schedule,
        "operator_actions": ["spawn source-bound motor vehicle and actors",
                             "drive to original surveyed alley halt",
                             "apply brake and hold while controlling real actor contact",
                             "depart and read back actual actor and vehicle histories"],
        "capture": {"rate_hz": 20, "frames": 900, "duration_s": 45,
                    "cameras": ["overview", "approach", "reference_corner", "driver_reference"]},
        "physical_outcome": "pending_original_native_readback",
        "legal_conclusion": "unreviewed",
    }
