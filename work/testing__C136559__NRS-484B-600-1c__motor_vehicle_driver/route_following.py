"""Measured waypoint tracking for the source-reviewed Native corridor.

The route itself comes from route_construction.select_corridor. This helper
produces a bounded steering request and measured remaining centerline distance.
It does not imply that the alley can physically support the requested speed.
"""

import math


class RouteFollower:
    def __init__(self, waypoints, *, lookahead_m=12.0, max_deviation_m=3.0):
        if len(waypoints) < 2 or lookahead_m <= 0 or max_deviation_m <= 0:
            raise ValueError("Continuous waypoint corridor and positive limits required")
        points = [(float(wp.transform.location.x), float(wp.transform.location.y)) for wp in waypoints]
        if not all(math.isfinite(v) for point in points for v in point):
            raise ValueError("Finite Native waypoints required")
        lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
        if any(length <= 0 for length in lengths):
            raise ValueError("Repeated Native waypoint")
        self.points = points
        self.lengths = lengths
        self.lookahead_m = lookahead_m
        self.max_deviation_m = max_deviation_m
        self.last_segment = 0

    def step(self, vehicle):
        transform = vehicle.get_transform()
        loc = transform.location
        x, y, yaw = float(loc.x), float(loc.y), float(transform.rotation.yaw)
        if not all(math.isfinite(v) for v in (x, y, yaw)):
            raise ValueError("Finite Native vehicle pose required")
        best = None
        for i in range(self.last_segment, len(self.lengths)):
            ax, ay = self.points[i]
            bx, by = self.points[i + 1]
            dx, dy = bx - ax, by - ay
            fraction = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
            px, py = ax + fraction * dx, ay + fraction * dy
            distance = math.hypot(x - px, y - py)
            candidate = (distance, i, fraction)
            if best is None or candidate < best:
                best = candidate
        deviation, segment, fraction = best
        if deviation > self.max_deviation_m:
            raise ValueError("Vehicle departed source-reviewed corridor")
        self.last_segment = segment
        remaining = (1 - fraction) * self.lengths[segment] + sum(self.lengths[segment + 1:])
        target_distance = min(self.lookahead_m, remaining)
        target_segment, target_fraction = segment, fraction
        while target_distance and target_segment < len(self.lengths):
            available = (1 - target_fraction) * self.lengths[target_segment]
            if target_distance <= available:
                target_fraction += target_distance / self.lengths[target_segment]
                break
            target_distance -= available
            target_segment += 1
            target_fraction = 0.0
        if target_segment >= len(self.lengths):
            tx, ty = self.points[-1]
        else:
            ax, ay = self.points[target_segment]
            bx, by = self.points[target_segment + 1]
            tx, ty = ax + target_fraction * (bx - ax), ay + target_fraction * (by - ay)
        desired_yaw = math.degrees(math.atan2(ty - y, tx - x))
        error = (desired_yaw - yaw + 180) % 360 - 180
        steering = max(-1.0, min(1.0, error / 35.0))
        return {"steering": steering, "distance_to_route_end_m": remaining,
                "lateral_deviation_m": deviation, "segment_index": segment}
