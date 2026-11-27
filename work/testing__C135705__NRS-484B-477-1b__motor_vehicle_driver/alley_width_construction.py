"""Construct source-surveyed width targets for C135705 park encounters.

Requested geometry is an engineering target. Original Native body vertices and
cross-sections, not this request, determine the observed statutory measurement.
"""
from __future__ import annotations

import math
from width_measurement import ASSIGNMENT, FEET_PER_M, _point, continuous_free_width_m

TARGETS_FT = {"width_9_9ft": 9.9, "width_10_0ft": 10.0,
              "width_10_1ft": 10.1, "ordinance_otherwise": 9.9}
VARIANTS = set(TARGETS_FT) | {"other_vehicle_close", "other_vehicle_far"}


def body_polygon(center, axis, length, width):
    normal = (-axis[1], axis[0])
    return [[center[0] + along * axis[0] * length / 2 + across * normal[0] * width / 2,
             center[1] + along * axis[1] * length / 2 + across * normal[1] * width / 2]
            for along, across in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def build_plan(site, case_id, *, direction=1):
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("wrong C135705 assignment")
    variant = case_id.removeprefix(ASSIGNMENT + "__")
    if variant not in VARIANTS or direction not in (-1, 1):
        raise ValueError("unknown width case or approach direction")
    if site.get("alley_kind") != "other_alley" or site.get("cul_de_sac") is not False or not site.get("start_connected") or not site.get("end_connected"):
        raise ValueError("qualifying connected other alley unproven")
    start = _point(site.get("centerline_start_m"), "centerline start")
    end = _point(site.get("centerline_end_m"), "centerline end")
    vector = (end[0] - start[0], end[1] - start[1])
    route_length = math.hypot(*vector)
    if route_length < 80:
        raise ValueError("surveyed connected approach too short")
    axis = (vector[0] / route_length, vector[1] / route_length)
    target_s = site.get("parking_station_m")
    if type(target_s) not in (int, float) or not 35 <= target_s <= route_length - 25:
        raise ValueError("surveyed parking station outside connected route")
    section = min(site.get("cross_sections", []),
                  key=lambda x: abs(x.get("station_m", -1000) - target_s), default=None)
    if section is None or abs(section.get("station_m", -1000) - target_s) > 0.25:
        raise ValueError("parking cross-section absent from survey")
    left = _point(section.get("left_xy_m"), "left alley boundary")
    right = _point(section.get("right_xy_m"), "right alley boundary")
    cross = (right[0] - left[0], right[1] - left[1])
    alley_width = math.hypot(*cross)
    across = (cross[0] / alley_width, cross[1] / alley_width)
    if abs(axis[0] * across[0] + axis[1] * across[1]) > 0.1:
        raise ValueError("surveyed cross-section not transverse to route")
    ego_length, ego_width = site.get("ego_length_m"), site.get("ego_width_m")
    if any(type(v) not in (int, float) for v in (ego_length, ego_width)) or not 3 <= ego_length <= 8 or not 1 <= ego_width <= 3:
        raise ValueError("actual ego blueprint dimensions missing")
    target_width_m = TARGETS_FT.get(variant, 10.0) / FEET_PER_M
    center_offset = alley_width - target_width_m - ego_width / 2
    if not ego_width / 2 <= center_offset <= alley_width - ego_width / 2:
        raise ValueError("target width cannot fit actual ego body inside alley")
    center = (left[0] + across[0] * center_offset,
              left[1] + across[1] * center_offset)
    ego_body = body_polygon(center, axis, ego_length, ego_width)
    expected = continuous_free_width_m(left, right, [ego_body]) * FEET_PER_M
    if abs(expected - TARGETS_FT.get(variant, 10.0)) > 0.02:
        raise ValueError("planned geometry does not produce requested width")
    if variant.startswith("other_vehicle"):
        if not site.get("other_vehicle_blueprint_source") or not site.get("other_vehicle_dimensions_source"):
            raise ValueError("other vehicle source and dimensions absent")
        other_length, other_width = site.get("other_vehicle_length_m"), site.get("other_vehicle_width_m")
        if any(type(v) not in (int, float) for v in (other_length, other_width)) or not 3 <= other_length <= 8 or not 1 <= other_width <= 3:
            raise ValueError("actual other-vehicle dimensions missing")
    if variant == "ordinance_otherwise" and site.get("ordinance_status") != "otherwise_provides":
        raise ValueError("reviewed otherwise-providing ordinance absent")
    route_point = lambda s: [start[0] + axis[0] * s, start[1] + axis[1] * s]
    other_target = None
    if variant.startswith("other_vehicle"):
        other_station = target_s if variant == "other_vehicle_close" else target_s + 18
        other_target = [left[0] + across[0] * (alley_width - other_width / 2) +
                        axis[0] * (other_station - target_s),
                        left[1] + across[1] * (alley_width - other_width / 2) +
                        axis[1] * (other_station - target_s)]
    return {"case_id":case_id, "variant":variant, "direction":direction,
            "start_xy_m":route_point(target_s-direction*30),
            "target_xy_m":list(center), "depart_xy_m":route_point(target_s+direction*15),
            "route_axis_xy":list(axis), "planned_ego_body_polygon_m":ego_body,
            "planned_available_width_ft":round(expected,6),
            "other_vehicle_target_xy_m":other_target,
            "other_vehicle_requested_polygon_m":body_polygon(other_target, axis, other_length, other_width) if other_target else None,
            "controller":{"kind":"route_tracking_then_brake_and_hold","hold_min_s":20.0},
            "capture":{"rate_hz":20,"duration_s":45,"cameras":["overview","approach","reference_corner","driver_reference"]},
            "physical_free_movement_judgment":"unresolved"}
