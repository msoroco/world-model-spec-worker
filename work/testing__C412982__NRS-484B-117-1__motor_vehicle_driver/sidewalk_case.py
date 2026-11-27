"""Exact NRS 484B.117(1) construction and source-context requirements."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    suffix: str
    travel_region: str
    entrance_kind: str | None
    vehicle_power: str
    designed_wheels: int
    operator_role: str


CASES = (
    Case("ordinary_road_travel", "road", None, "combustion", 4, "ordinary"),
    Case("ordinary_sidewalk_travel", "sidewalk", None, "combustion", 4, "ordinary"),
    Case("permanent_driveway_crossing", "sidewalk", "permanent_driveway", "combustion", 4, "ordinary"),
    Case("temporary_driveway_crossing", "sidewalk", "temporary_driveway", "combustion", 4, "ordinary"),
    Case("alley_entrance_crossing", "sidewalk", "alley_entrance", "combustion", 4, "ordinary"),
    Case("electric_three_wheel_no_duty", "sidewalk", None, "solely_electric", 3, "ordinary"),
    Case("electric_three_wheel_emergency", "sidewalk", None, "solely_electric", 3, "emergency"),
    Case("electric_three_wheel_law_officer", "sidewalk", None, "solely_electric", 3, "law_officer"),
    Case("electric_three_wheel_security_guard", "sidewalk", None, "solely_electric", 3, "security_guard"),
)
BY_SUFFIX = {case.suffix: case for case in CASES}


def validate_case_site(case, site):
    if case.suffix not in BY_SUFFIX or BY_SUFFIX[case.suffix] != case:
        raise ValueError("unknown frozen exact sidewalk case")
    if site.get("requested_travel_region") != case.travel_region:
        raise ValueError("reviewed requested travel region differs")
    if site.get("requested_entrance_kind") != case.entrance_kind:
        raise ValueError("reviewed requested entrance branch differs")
    design = site["vehicle_design"]
    if (design.get("power") != case.vehicle_power or
            design.get("designed_for_wheel_count") != case.designed_wheels or
            design.get("wheel_count") != case.designed_wheels):
        raise ValueError("reviewed vehicle design differs from selected case")
    operator = site["operator_context"]
    if operator.get("role") != case.operator_role:
        raise ValueError("reviewed operator branch differs from selected case")
    if case.operator_role != "ordinary" and operator.get("authorized") is not True:
        raise ValueError("original operator authorization missing")
    if case.operator_role in ("law_officer", "security_guard") and operator.get("on_official_duty") is not True:
        raise ValueError("original official duty missing")
    if case.operator_role == "emergency" and operator.get("operated_as_authorized_emergency_vehicle") is not True:
        raise ValueError("original emergency operation missing")
    return True


def construct(adapter, site, case):
    """Exercise actual spawn, route and control configuration calls."""
    validate_case_site(case, site)
    route = site["approach_route_xy"]
    ego = adapter.spawn_vehicle(route[0], site["vehicle_blueprint_id"])
    adapter.set_route(ego, route)
    adapter.set_target_region(ego, site["sidewalk_area_polygon_xy"],
                              site["entrance_polygons_xy"],
                              case.travel_region, case.entrance_kind)
    adapter.enable_controller(ego, "route_follow_20hz")
    return {"ego": ego, "route": route, "case": case.suffix}
