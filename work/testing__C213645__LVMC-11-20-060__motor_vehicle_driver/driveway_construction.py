"""Survey and reconstruct the selected residential driveway geometry.

All coordinates are original-map metres. A reviewed packet must accompany the
local CARLA run; a string naming a driveway never substitutes for the surveyed
sidewalk and connected roadway. This module has no CARLA import.
"""
from __future__ import annotations

import math


def _xy(value, name):
    if (not isinstance(value, (list, tuple)) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError("invalid original coordinate: " + name)
    return float(value[0]), float(value[1])


def _polygon(value, name):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("missing original polygon: " + name)
    poly = [_xy(v, name) for v in value]
    area = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] -
               poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2
    if abs(area) < 0.1:
        raise ValueError("degenerate original polygon: " + name)
    return poly


def _inside(point, polygon):
    x, y = point
    inside = False
    for i, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(i + 1) % len(polygon)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def survey(packet):
    """Demand an original ordered route and participant approaches.

    This validates geometric *possibility*. Actual wheel/body containment and
    clearance remain measured from the physical episode.
    """
    if packet.get("source_kind") != "original_native_geometry":
        raise ValueError("original native driveway geometry missing")
    required = ("map_sha256", "district_source", "frontage_source",
                "private_driveway_source", "sidewalk_source", "roadway_source",
                "connection_source", "ego_vehicle_id")
    for key in required:
        if not packet.get(key):
            raise ValueError("reviewed driveway source missing: " + key)
    if packet.get("district") != "residence" or packet.get("business_district") is not False:
        raise ValueError("selected residence district not source established")
    if packet.get("access") != "private_driveway" or packet.get("road_connection") is not True:
        raise ValueError("private driveway to roadway connection unverified")
    if packet.get("crosswalk_assumed") or packet.get("controlled_access_assumed"):
        raise ValueError("unsupported crosswalk or controlled-access premise")
    regions = {name: _polygon(packet.get(name + "_polygon_m"), name)
               for name in ("driveway", "sidewalk", "roadway")}
    route = [_xy(point, "ego_route") for point in packet.get("ego_route_xy_m", [])]
    if len(route) < 5:
        raise ValueError("ego route needs sampled private approach and roadway entry")
    states = []
    for point in route:
        membership = tuple(name for name, poly in regions.items() if _inside(point, poly))
        states.append(membership)
    first_driveway = next((i for i, state in enumerate(states) if "driveway" in state), None)
    first_sidewalk = next((i for i, state in enumerate(states) if "sidewalk" in state), None)
    first_roadway = next((i for i, state in enumerate(states) if "roadway" in state), None)
    if not all(i is not None for i in (first_driveway, first_sidewalk, first_roadway)):
        raise ValueError("route omits driveway, sidewalk or roadway")
    if not (first_driveway < first_sidewalk < first_roadway):
        raise ValueError("driveway-sidewalk-roadway route order invalid")
    if first_sidewalk < 1 or "sidewalk" in states[first_sidewalk - 1]:
        raise ValueError("no original pre-sidewalk stop location")
    if first_roadway < first_sidewalk + 1:
        raise ValueError("no sidewalk crossing before roadway entry")
    approaches = packet.get("roadway_approaches", {})
    if not isinstance(approaches, dict) or set(approaches) != {"left", "right"}:
        raise ValueError("both roadway approach directions required")
    for direction in ("left", "right"):
        row = approaches[direction]
        if not row.get("lane_source") or len(row.get("route_xy_m", [])) < 2:
            raise ValueError("sourced roadway route missing: " + direction)
        a, b = (_xy(v, direction) for v in row["route_xy_m"][:2])
        if math.dist(a, b) < 1:
            raise ValueError("roadway approach route degenerate: " + direction)
        if not any(_inside(_xy(v, direction), regions["roadway"])
                   for v in row["route_xy_m"]):
            raise ValueError("roadway participant not on roadway: " + direction)
    pedestrian = packet.get("pedestrian_route_xy_m", [])
    if len(pedestrian) < 2 or not any(_inside(_xy(v, "pedestrian"), regions["sidewalk"])
                                          for v in pedestrian):
        raise ValueError("pedestrian route does not cross sidewalk area")
    return {
        "ego_route_xy_m": [list(v) for v in route],
        "stop_point_xy_m": list(route[first_sidewalk - 1]),
        "sidewalk_entry_index": first_sidewalk,
        "roadway_entry_index": first_roadway,
        "roadway_approaches": approaches,
        "pedestrian_route_xy_m": pedestrian,
        "survey_states": [list(v) for v in states],
        "source_kind": "original_native_geometry",
    }


def construct(packet, case):
    plan = survey(packet)
    world = case["world_setup"]
    if world["district"] != "residence" or world["access"] != "private_driveway":
        raise ValueError("selected world facts differ")
    if world["roadway_vehicle"].startswith("left_"):
        direction = "left"
    elif world["roadway_vehicle"].startswith("right_"):
        direction = "right"
    else:
        direction = None
    plan.update({
        "case_id": case["case_id"],
        "ego_entry_behavior": case["controller"]["entry_behavior"],
        "pedestrian_mode": world["pedestrian"],
        "roadway_vehicle_mode": world["roadway_vehicle"],
        "active_roadway_direction": direction,
        "termination_rule": "after recorded road entry or end of 900 synchronized frames",
        "legal_judgment": "unresolved",
    })
    return plan
