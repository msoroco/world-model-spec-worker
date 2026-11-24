"""Conservative bounded Native route control for fallback reversal attempts.

Routes are supplied by a SHA-bound site packet. This controller follows them
without encoding a desired legal outcome or visibility label.
"""
from __future__ import annotations

import math


def _clamp(value, low, high):
    return max(low, min(high, value))


def _wrapped_radians(value):
    return (value + math.pi) % (2 * math.pi) - math.pi


class RouteFollower:
    def __init__(self, world_map, route: dict, location_factory,
                 control_factory):
        points = route.get("waypoints")
        speed = route.get("target_speed_mps")
        if (not isinstance(points, list) or len(points) < 3 or
                type(speed) not in (int, float) or not math.isfinite(speed) or
                speed <= 0 or speed > 15):
            raise ValueError("reviewed route and bounded speed required")
        self.points = []
        for point in points:
            if (not isinstance(point, dict) or
                    any(type(point.get(axis)) not in (int, float) or
                        not math.isfinite(point[axis]) for axis in ("x", "y", "z")) or
                    type(point.get("road_id")) is not int or
                    type(point.get("lane_id")) is not int):
                raise ValueError("reviewed route waypoint incomplete")
            waypoint = world_map.get_waypoint(
                location_factory(point["x"], point["y"], point["z"]),
                project_to_road=False)
            if (waypoint is None or waypoint.road_id != point["road_id"] or
                    waypoint.lane_id != point["lane_id"]):
                raise ValueError("reviewed route leaves loaded road lane")
            self.points.append(point)
        if any(math.dist((a["x"], a["y"]), (b["x"], b["y"])) < 0.25
               for a, b in zip(self.points, self.points[1:])):
            raise ValueError("reviewed route has repeated or near-zero segment")
        self.target_speed = float(speed)
        self.control_factory = control_factory
        self.next_index = 1

    def apply(self, actor):
        transform = actor.get_transform()
        position = transform.location
        if self.next_index >= len(self.points):
            actor.apply_control(self.control_factory(throttle=0.0,
                                                     steer=0.0, brake=1.0))
            return "complete"
        target = self.points[self.next_index]
        distance = math.hypot(target["x"] - position.x,
                              target["y"] - position.y)
        if distance < 1.5:
            self.next_index += 1
            if self.next_index >= len(self.points):
                actor.apply_control(self.control_factory(throttle=0.0,
                                                         steer=0.0, brake=1.0))
                return "complete"
            target = self.points[self.next_index]
        heading = math.atan2(target["y"] - position.y,
                             target["x"] - position.x)
        yaw = math.radians(float(transform.rotation.yaw))
        speed = float(actor.get_velocity().length())
        if not all(math.isfinite(value) for value in (yaw, speed)) or speed < 0:
            raise ValueError("original actor motion is nonfinite")
        error = _wrapped_radians(heading - yaw)
        steer = _clamp(error / 1.1, -0.8, 0.8)
        throttle = _clamp((self.target_speed - speed) / 6.0, 0.0, 0.35)
        brake = _clamp((speed - self.target_speed) / 3.0, 0.0, 0.6)
        actor.apply_control(self.control_factory(throttle=throttle,
                                                 steer=steer, brake=brake))
        return "following"
