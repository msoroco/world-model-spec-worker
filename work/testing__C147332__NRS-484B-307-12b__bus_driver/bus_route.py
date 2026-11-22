"""Deterministic center routes for the four exact red-X bus probes.

The returned waypoints are construction targets, not claims of CARLA motion.
"""
from __future__ import annotations

from lane_signal_measurement import _number


ADJACENT_LANE_Y = -1.8
GOVERNED_LANE_Y = 1.8
BUS_HALF_WIDTH_M = 1.25
ROUTES = ("adjacent_travel", "lateral_entry", "red_lane_stand", "red_lane_drive")


def route(kind, *, road_length_m=90.0):
    if kind not in ROUTES:
        raise ValueError("unknown exact red-X bus route")
    length = _number(road_length_m, "road length")
    if length < 40:
        raise ValueError("road too short for original approach and camera coverage")
    x0, x1, x2 = 8.0, length / 2, length - 8.0
    if kind == "adjacent_travel":
        centers = [(x0, ADJACENT_LANE_Y), (x1, ADJACENT_LANE_Y),
                   (x2, ADJACENT_LANE_Y)]
    elif kind == "lateral_entry":
        centers = [(x0, ADJACENT_LANE_Y), (x1 - 8, ADJACENT_LANE_Y),
                   (x1 + 8, GOVERNED_LANE_Y), (x2, GOVERNED_LANE_Y)]
    elif kind == "red_lane_stand":
        centers = [(x0, GOVERNED_LANE_Y), (x0, GOVERNED_LANE_Y),
                   (x0, GOVERNED_LANE_Y)]
    else:
        centers = [(x0, GOVERNED_LANE_Y), (x1, GOVERNED_LANE_Y),
                   (x2, GOVERNED_LANE_Y)]
    return {"route_kind": kind, "waypoint_centers_m": [list(p) for p in centers],
            "governed_lane_bounds_m": [0.0, 3.6],
            "adjacent_lane_bounds_m": [-3.6, 0.0],
            "bus_half_width_m": BUS_HALF_WIDTH_M,
            "signal_symbol": "red_x", "official_provenance": "requires_source_review",
            "realized_motion_claimed": False}
