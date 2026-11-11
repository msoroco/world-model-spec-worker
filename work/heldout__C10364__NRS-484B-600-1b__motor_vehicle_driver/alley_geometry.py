"""Pure geometry for the C10364 alley construction; CARLA is imported by the runner.

All distances are metres.  These are engineering placement checks, not legal
thresholds for endangerment under NRS 484B.600(1)(b).
"""

from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Placement:
    vehicle_start: Point
    vehicle_end: Point
    pedestrian: Point
    property_center: Point
    pedestrian_route_gap: float
    property_route_gap: float
    usable_width: float


def _unit(start: Point, end: Point):
    dx, dy = end.x - start.x, end.y - start.y
    length = hypot(dx, dy)
    if length <= 0:
        raise ValueError("Alley route needs distinct start and end points")
    return dx / length, dy / length, length


def _position(start: Point, forward, left, station: float, lateral: float):
    fx, fy = forward
    lx, ly = left
    return Point(start.x + station * fx + lateral * lx,
                 start.y + station * fy + lateral * ly)


def plan_alley(start: Point, end: Point, *, alley_width: float,
               vehicle_width: float, pedestrian_station: float,
               pedestrian_offset: float, property_station: float,
               property_offset: float, pedestrian_radius: float = 0.3,
               property_radius: float = 0.4, margin: float = 0.2) -> Placement:
    """Place stationary pedestrian and property beside a straight alley path.

    Offset signs are relative to travel.  The construction keeps the complete
    objects outside the vehicle's nominal swept width, but inside the alley.
    The measured gaps remain available for a physical exposure sweep.
    """
    fx, fy, length = _unit(start, end)
    if min(alley_width, vehicle_width, pedestrian_radius, property_radius, margin) <= 0:
        raise ValueError("Widths, radii and margin must be positive")
    usable = alley_width - vehicle_width
    if usable <= 2 * margin:
        raise ValueError("Alley is too narrow for the vehicle and margins")
    for name, station, offset, radius in (
        ("pedestrian", pedestrian_station, pedestrian_offset, pedestrian_radius),
        ("property", property_station, property_offset, property_radius),
    ):
        if not margin < station < length - margin:
            raise ValueError(f"{name} station lies outside the usable route")
        if abs(offset) - radius < vehicle_width / 2 + margin:
            raise ValueError(f"{name} overlaps the vehicle swept corridor")
        if abs(offset) + radius > alley_width / 2 - margin:
            raise ValueError(f"{name} lies outside the alley boundary")
    left = (-fy, fx)
    return Placement(
        vehicle_start=start, vehicle_end=end,
        pedestrian=_position(start, (fx, fy), left, pedestrian_station, pedestrian_offset),
        property_center=_position(start, (fx, fy), left, property_station, property_offset),
        pedestrian_route_gap=abs(pedestrian_offset) - pedestrian_radius - vehicle_width / 2,
        property_route_gap=abs(property_offset) - property_radius - vehicle_width / 2,
        usable_width=usable,
    )
