"""CPU geometry and source checks for the NRS 484B.153(2) door interaction.

All coordinates are world XY metres. The calculations describe a physical
candidate interaction; they do not decide what legally "interfere" means.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable


@dataclass(frozen=True)
class Point:
    x: float
    y: float


def _cross(a: Point, b: Point) -> float:
    return a.x * b.y - a.y * b.x


def _sub(a: Point, b: Point) -> Point:
    return Point(a.x - b.x, a.y - b.y)


def _unit(vector: Point) -> Point:
    length = hypot(vector.x, vector.y)
    if length <= 1e-9:
        raise ValueError("direction has zero length")
    return Point(vector.x / length, vector.y / length)


def traffic_side(parked_heading: Point, parked_center: Point,
                 passing_path: Iterable[Point]) -> str:
    """Classify the side of a parked car occupied by a passing trajectory.

    The path must remain on one side. A crossing or centerline trajectory is
    ambiguous and must be reviewed from original geometry.
    """
    heading = _unit(parked_heading)
    signed = [_cross(heading, _sub(point, parked_center))
              for point in passing_path]
    if len(signed) < 2 or any(abs(value) < 0.05 for value in signed):
        raise ValueError("insufficient or centerline passing path")
    if min(signed) < 0 < max(signed):
        raise ValueError("passing path crosses parked centerline")
    return "left" if signed[0] > 0 else "right"


def segment_distance(a: Point, b: Point, c: Point, d: Point) -> float:
    """Minimum XY distance between two closed line segments."""
    ab, cd, ca = _sub(b, a), _sub(d, c), _sub(c, a)
    denominator = _cross(ab, cd)
    if abs(denominator) > 1e-12:
        t = _cross(ca, cd) / denominator
        u = _cross(ca, ab) / denominator
        if 0 <= t <= 1 and 0 <= u <= 1:
            return 0.0

    def point_segment_distance(p: Point, start: Point, end: Point) -> float:
        edge = _sub(end, start)
        squared = edge.x * edge.x + edge.y * edge.y
        if squared <= 1e-12:
            return hypot(p.x - start.x, p.y - start.y)
        t = max(0.0, min(1.0, ((p.x - start.x) * edge.x +
                              (p.y - start.y) * edge.y) / squared))
        return hypot(p.x - start.x - t * edge.x,
                     p.y - start.y - t * edge.y)

    return min(point_segment_distance(p, s, e)
               for p, s, e in ((a, c, d), (b, c, d),
                               (c, a, b), (d, a, b)))


def door_sweep(parked_center: Point, parked_heading: Point, side: str,
               *, longitudinal_offset_m: float = 0.75,
               half_width_m: float = 0.9,
               door_reach_m: float = 0.85) -> tuple[Point, Point]:
    """Conservative hinge-to-outer-edge proxy, pending Native door vertices.

    This proxy is only a planning check. Delivery auditing must use recorded
    door transforms and bounding vertices for each original frame.
    """
    if side not in ("left", "right"):
        raise ValueError("door side must be left or right")
    if min(longitudinal_offset_m, half_width_m, door_reach_m) <= 0:
        raise ValueError("door dimensions must be positive")
    direction = _unit(parked_heading)
    normal = Point(-direction.y, direction.x)
    sign = 1 if side == "left" else -1
    hinge = Point(parked_center.x + longitudinal_offset_m * direction.x +
                  sign * half_width_m * normal.x,
                  parked_center.y + longitudinal_offset_m * direction.y +
                  sign * half_width_m * normal.y)
    tip = Point(hinge.x + sign * door_reach_m * normal.x,
                hinge.y + sign * door_reach_m * normal.y)
    return hinge, tip


def interaction_measurement(*, parked_center: Point,
                            parked_heading: Point, door_side: str,
                            passing_path: list[Point],
                            passing_speed_samples_mps: list[float],
                            door_open_samples: list[bool],
                            synchronized_frame_ids: list[int],
                            vehicle_half_width_m: float) -> dict:
    """Retain prerequisites and engineering proximity without a legal verdict."""
    count = len(synchronized_frame_ids)
    if count < 2 or not (len(passing_path) ==
                         len(passing_speed_samples_mps) ==
                         len(door_open_samples) == count):
        raise ValueError("source streams must join at every original frame")
    if len(set(synchronized_frame_ids)) != count or any(
            b <= a for a, b in zip(synchronized_frame_ids,
                                    synchronized_frame_ids[1:])):
        raise ValueError("original frame IDs must strictly increase")
    if vehicle_half_width_m <= 0:
        raise ValueError("passing vehicle width must be positive")
    side = traffic_side(parked_heading, parked_center, passing_path)
    hinge, tip = door_sweep(parked_center, parked_heading, door_side)
    proximities = []
    for index in range(count - 1):
        if not (door_open_samples[index] or door_open_samples[index + 1]):
            continue
        if max(passing_speed_samples_mps[index:index + 2]) <= 0.1:
            continue
        clearance = segment_distance(hinge, tip,
                                     passing_path[index], passing_path[index + 1])
        proximities.append({"first_frame": synchronized_frame_ids[index],
                            "last_frame": synchronized_frame_ids[index + 1],
                            "centerline_to_door_m": clearance,
                            "proxy_body_overlap": clearance <= vehicle_half_width_m})
    return {"passing_traffic_side": side,
            "opening_on_passing_side": side == door_side,
            "moving_open_intervals": proximities,
            "proxy_overlap_present": any(x["proxy_body_overlap"]
                                         for x in proximities),
            "legal_interference": "unresolved_judgment",
            "geometry_kind": "planning_proxy_requires_original_door_vertices"}


def request_door_open(vehicle, carla_module, side: str) -> None:
    """Issue the Native CARLA door command on the selected front door."""
    if side not in ("left", "right"):
        raise ValueError("door side must be left or right")
    vehicle.open_door(carla_module.VehicleDoor.FL if side == "left"
                      else carla_module.VehicleDoor.FR)


def inspect_loading_crest(route_samples: list[tuple[float, float]],
                          loading_station_m: float,
                          loading_position: Point,
                          road_edge: tuple[Point, Point]) -> dict:
    """Verify an authored loading site is near a measured grade reversal.

    Route samples are (station metres, elevation metres). This deliberately
    returns a measured offset rather than a legal definition of "near".
    """
    if len(route_samples) < 3 or any(b[0] <= a[0] for a, b in zip(
            route_samples, route_samples[1:])):
        raise ValueError("route grade samples must be ordered and complete")
    grades = [(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(
        route_samples, route_samples[1:])]
    candidates = [index for index in range(1, len(route_samples) - 1)
                  if grades[index - 1] > 0.01 and grades[index] < -0.01]
    if len(candidates) != 1:
        raise ValueError("unique measured hill crest is absent")
    if not route_samples[0][0] <= loading_station_m <= route_samples[-1][0]:
        raise ValueError("loading site is outside surveyed route")
    edge_clearance_m = segment_distance(loading_position, loading_position,
                                        *road_edge)
    return {"crest_station_m": route_samples[candidates[0]][0],
            "loading_station_m": loading_station_m,
            "loading_to_crest_m": abs(loading_station_m -
                                      route_samples[candidates[0]][0]),
            "loading_to_road_edge_m": edge_clearance_m,
            "legal_hill_crest_proximity": "unresolved_judgment"}
