"""Low-level route follower with separately recorded stop and precedence requests.

The controller's requested phases are never used as proof of actual stopping,
pedestrian necessity or roadway right-of-way. Original kinematics determine those.
"""
from __future__ import annotations

import math


class DrivewayController:
    def __init__(self, plan, *, max_speed_mps=3.0):
        self.plan = plan
        self.route = [tuple(v) for v in plan["ego_route_xy_m"]]
        self.stop = tuple(plan["stop_point_xy_m"])
        self.max_speed = max_speed_mps
        self.phase = "approach"
        self.hold_ticks = 0
        self.next_waypoint = 1

    def step(self, xy_m, yaw_rad, speed_mps, pedestrian_clear, roadway_clear):
        x, y = xy_m
        if any(not math.isfinite(v) for v in (x, y, yaw_rad, speed_mps)):
            raise ValueError("original controller state invalid")
        if self.next_waypoint >= len(self.route):
            self.phase = "complete"
            return {"throttle": 0.0, "brake": 1.0, "steer": 0.0, "phase": self.phase}
        while self.next_waypoint < len(self.route) - 1 and math.dist(
                (x, y), self.route[self.next_waypoint]) < 1.0:
            self.next_waypoint += 1
        target = self.route[self.next_waypoint]
        heading = math.atan2(target[1] - y, target[0] - x)
        heading_error = (heading - yaw_rad + math.pi) % (2 * math.pi) - math.pi
        steer = max(-1.0, min(1.0, 1.2 * heading_error))
        stop_distance = math.dist((x, y), self.stop)
        stop_requested = self.plan["ego_entry_behavior"] != "roll_across_sidewalk"
        if self.phase == "approach" and stop_requested and stop_distance < 2.0:
            self.phase = "pre_sidewalk_stop"
        if self.phase == "pre_sidewalk_stop":
            if speed_mps < 0.08:
                self.hold_ticks += 1
            if self.hold_ticks >= 4:
                self.phase = "sidewalk_wait"
            else:
                return {"throttle": 0.0, "brake": 1.0, "steer": steer, "phase": self.phase}
        pedestrian_mode = self.plan["pedestrian_mode"]
        if (self.phase == "sidewalk_wait" and
                pedestrian_mode == "pedestrian_crossing_yield" and not pedestrian_clear):
            return {"throttle": 0.0, "brake": 1.0, "steer": steer, "phase": self.phase}
        if self.phase in ("sidewalk_wait", "pre_sidewalk_stop"):
            self.phase = "sidewalk_crossing"
        road_index = self.plan["roadway_entry_index"]
        if self.next_waypoint >= road_index - 1:
            mode = self.plan["roadway_vehicle_mode"]
            if mode.endswith("_yield") and not roadway_clear:
                self.phase = "roadway_wait"
                return {"throttle": 0.0, "brake": 1.0, "steer": steer, "phase": self.phase}
            self.phase = "roadway_entry"
        target_speed = min(self.max_speed, 1.8 if self.phase == "sidewalk_crossing" else 2.5)
        error = target_speed - speed_mps
        throttle = max(0.0, min(0.45, 0.22 * error))
        brake = max(0.0, min(0.8, -0.35 * error))
        return {"throttle": throttle, "brake": brake, "steer": steer, "phase": self.phase}
