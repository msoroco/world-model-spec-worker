"""CPU route geometry and CARLA-lazy controller for the unselected backing alternatives.

The route is a sequence of vehicle-center points in original Native coordinates.
It is an engineering construction: saved body history determines the outcome.
"""

import math

from shapely.affinity import rotate, translate
from shapely.geometry import MultiPoint, Polygon


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("Route point must have two coordinates")
    if any(type(item) not in (int, float) or not math.isfinite(item) for item in value):
        raise ValueError("Route point must be finite")
    return tuple(map(float, value))


def _angle(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def _delta(a, b):
    return (b - a + 180.0) % 360.0 - 180.0


def review_route(route_xy, start_body_xy, region_xy, *, alternative):
    """Check the planned complete-body sweep and the reverse turn geometry."""
    if alternative not in ("intersection", "street_corner"):
        raise ValueError("Unknown backing alternative")
    if not isinstance(route_xy, list) or len(route_xy) < 3:
        raise ValueError("Reverse route needs three or more points")
    route = [_point(row) for row in route_xy]
    if any(math.dist(a, b) < 0.15 for a, b in zip(route, route[1:])):
        raise ValueError("Reverse route has a degenerate segment")
    body = MultiPoint([_point(row) for row in start_body_xy]).convex_hull
    region = Polygon([_point(row) for row in region_xy])
    if body.area <= 0 or not region.is_valid or region.area <= 0:
        raise ValueError("Invalid vehicle body or sourced region")
    if body.intersects(region):
        raise ValueError("Reverse start body already occupies selected region")
    headings = [(_angle(a, b) + 180.0) % 360.0 for a, b in zip(route, route[1:])]
    cumulative_turn = sum(abs(_delta(a, b)) for a, b in zip(headings, headings[1:]))
    if any(abs(_delta(a, b)) > 15 for a, b in zip(headings, headings[1:])):
        raise ValueError("Reverse route has an abrupt steering corner")
    if alternative == "intersection" and cumulative_turn > 10:
        raise ValueError("Intersection construction must use a straight backing route")
    if alternative == "street_corner" and cumulative_turn < 30:
        raise ValueError("Street-corner construction lacks a planned turn")
    first_heading = headings[0]
    overlaps = []
    for index, center in enumerate(route):
        heading = headings[min(index, len(headings) - 1)]
        footprint = translate(rotate(body, _delta(first_heading, heading),
                                     origin=route[0], use_radians=False),
                              xoff=center[0] - route[0][0],
                              yoff=center[1] - route[0][1])
        overlaps.append(footprint.intersection(region).area)
    if not any(value > 0 for value in overlaps[1:]):
        raise ValueError("Planned reverse body never enters selected region")
    return {"alternative": alternative, "route_xy_m": [list(row) for row in route],
            "planned_body_region_overlap_area_m2": overlaps,
            "planned_heading_change_deg": _delta(headings[0], headings[-1]),
            "actual_motion_confirmed": False}


class ReverseRouteController:
    """Follow a reviewed centerline while reversing; observed motion is audited later."""

    def __init__(self, route_xy, *, lookahead_m=2.0, wheelbase_m=2.7):
        if not isinstance(route_xy, list) or len(route_xy) < 3:
            raise ValueError("Reverse route needs three or more points")
        self.route = [_point(row) for row in route_xy]
        if lookahead_m <= 0 or wheelbase_m <= 0:
            raise ValueError("Positive lookahead and wheelbase required")
        self.lookahead = float(lookahead_m)
        self.wheelbase = float(wheelbase_m)

    def step(self, center_xy, heading_deg, speed_mps):
        center = _point(center_xy)
        if any(type(v) not in (int, float) or not math.isfinite(v)
               for v in (heading_deg, speed_mps)) or speed_mps < 0:
            raise ValueError("Finite heading and nonnegative speed required")
        nearest = min(range(len(self.route)),
                      key=lambda i: math.dist(center, self.route[i]))
        target = nearest
        while target < len(self.route) - 1 and math.dist(self.route[nearest], self.route[target]) < self.lookahead:
            target += 1
        aim = self.route[target]
        remaining = sum(math.dist(a, b) for a, b in zip(self.route[nearest:], self.route[nearest + 1:]))
        desired_heading = (_angle(center, aim) + 180.0) % 360.0
        error_rad = math.radians(_delta(float(heading_deg), desired_heading))
        # Negative longitudinal speed reverses the yaw response of steering.
        steer = max(-0.65, min(0.65, -math.atan2(2 * self.wheelbase *
                                                 math.sin(error_rad),
                                                 max(self.lookahead, math.dist(center, aim))) / 0.6))
        brake = remaining < 0.4 + speed_mps * speed_mps / 3.0
        return {"reverse": True, "throttle": 0.0 if brake else 0.16,
                "brake": 1.0 if brake else 0.0, "steer": steer,
                "route_index": nearest, "remaining_m": remaining,
                "target_reached": remaining < 0.4}
