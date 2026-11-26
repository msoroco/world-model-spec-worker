"""Plan bounded curb-entry sampling without asserting legal or physical outcomes.

The stations are authored controller targets in the 45-second, 20 Hz episode.
The original site and realized motion still need source-bound local review.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite

from curb_entry import CASES, validate_scene


@dataclass(frozen=True)
class Station:
    sweep: str
    name: str
    value_m_or_s: float
    observable: str
    unit: str


STATIONS = (
    Station("sudden_departure", "hold_4s", 4.0, "actual_departure_time_s", "s"),
    Station("sudden_departure", "hold_6s", 6.0, "actual_departure_time_s", "s"),
    Station("sudden_departure", "hold_8s", 8.0, "actual_departure_time_s", "s"),
    Station("yield_impossibility", "start_10m", 10.0,
            "vehicle_distance_at_road_entry_m", "m"),
    Station("yield_impossibility", "start_20m", 20.0,
            "vehicle_distance_at_road_entry_m", "m"),
    Station("yield_impossibility", "start_30m", 30.0,
            "vehicle_distance_at_road_entry_m", "m"),
)


def planned_scene(base: dict, station: Station) -> dict:
    """Return a distinct, source-labeled controller request from a reviewed base.

    This checks only bounded software geometry and timing. It never certifies
    that CARLA can realize the target or that either legal phrase applies.
    """
    if station not in STATIONS:
        raise ValueError("unlisted curb-entry sampling station")
    case = CASES[0]
    scene = deepcopy(base)
    if station.sweep == "sudden_departure":
        frames = station.value_m_or_s * 20
        if not isfinite(frames) or frames != int(frames) or not 40 <= frames <= 200:
            raise ValueError("departure controller target outside authored episode")
        scene["departure_frame"] = int(frames)
    else:
        route = scene.get("vehicle_route_xy")
        if not isinstance(route, list) or len(route) < 2:
            raise ValueError("vehicle route needed for sampling")
        if (not isfinite(station.value_m_or_s) or
                not 10 <= station.value_m_or_s <= 30):
            raise ValueError("vehicle station outside authored probe envelope")
        if route[-1][1] != 0 or scene.get("curb_start_xy") != [0, -3]:
            raise ValueError("diagnostic station requires reviewed path orientation")
        scene["vehicle_route_xy"][0] = [-station.value_m_or_s, 0]
    validate_scene(scene, case)
    return scene
