"""Source-gated road-side geometry for NRS 484B.297(2).

Coordinates are only a construction convention. Original map and actor transforms
must be read back before a captured attempt can establish the statutory facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True)
class Route:
    start: tuple[float, float]
    end: tuple[float, float]

    @property
    def unit(self) -> tuple[float, float]:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        length = hypot(dx, dy)
        if length <= 0:
            raise ValueError("route has no longitudinal motion")
        return dx / length, dy / length


def side_of_highway(vehicle_route: Route, pedestrian_xy: tuple[float, float]) -> str:
    """Classify the pedestrian relative to approaching traffic's forward vector.

    An engineering zero band is intentionally absent: source review must resolve
    road boundaries and a pedestrian on the center line has unknown side.
    """
    ux, uy = vehicle_route.unit
    cross = ux * (pedestrian_xy[1] - vehicle_route.start[1]) - uy * (pedestrian_xy[0] - vehicle_route.start[0])
    if cross > 0:
        return "traffic_left"
    if cross < 0:
        return "traffic_right"
    return "unknown"


def pedestrian_faces_approach(vehicle_route: Route, pedestrian_route: Route) -> bool:
    vx, vy = vehicle_route.unit
    px, py = pedestrian_route.unit
    return vx * px + vy * py < 0


def construction_routes(approach: str, side: str, heading: str = "facing") -> tuple[Route, Route]:
    """Return distinct vehicle/pedestrian paths on a two-directional road.

    The side is defined in the pedestrian's direction of travel: a pedestrian
    facing the oncoming vehicle at the left highway edge is left-facing.
    """
    if approach not in {"east", "west"} or side not in {"left", "right"} or heading not in {"facing", "with_traffic"}:
        raise ValueError("unsupported route request")
    vehicle = Route((-30.0, 0.0), (30.0, 0.0)) if approach == "east" else Route((30.0, 0.0), (-30.0, 0.0))
    # A facing pedestrian walks opposite the approaching vehicle. To isolate
    # highway side, keep both variants facing and change only the lateral edge.
    y = -4.5 if (approach == "east") == (side == "left") else 4.5
    if (approach == "east") == (heading == "facing"):
        pedestrian = Route((20.0, y), (-20.0, y))
    else:
        pedestrian = Route((-20.0, y), (20.0, y))
    return vehicle, pedestrian
