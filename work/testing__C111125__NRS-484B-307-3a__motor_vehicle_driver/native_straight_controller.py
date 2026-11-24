"""Measured-pose straight controller for the surveyed C111125 route.

Control commands are engineering inputs. Original positions, lamp aspects and
lawful-use evidence remain separate observations in native_attempt.py.
"""
from __future__ import annotations

import math

from dual_green import check_site, inside, require


class StraightController:
    def __init__(self, site, source_root, carla, ego, other=None, target_speed_mps=4.0):
        check_site(site, source_root)
        require(0 < float(target_speed_mps) <= 15, "invalid engineering target speed")
        self.site = site
        self.carla = carla
        self.ego = ego
        self.other = other
        self.speed = float(target_speed_mps)
        self.route = [(float(x), float(y)) for x, y in site["ego_route_xy"]]
        self.last_index = -1
        self.completed = False

    def __call__(self, ego, index):
        require(ego is self.ego, "controller ego identity changed")
        require(index == self.last_index + 1, "controller tick order changed")
        self.last_index = index
        pose = ego.get_location()
        velocity = ego.get_velocity()
        x, y = float(pose.x), float(pose.y)
        speed = math.hypot(float(velocity.x), float(velocity.y))
        require(all(math.isfinite(value) for value in (x, y, speed)),
                "nonfinite original ego motion")
        start, end = self.route[0], self.route[-1]
        dx, dy = end[0] - start[0], end[1] - start[1]
        distance = math.hypot(dx, dy)
        along = ((x - start[0]) * dx + (y - start[1]) * dy) / distance
        lateral = abs((x - start[0]) * dy - (y - start[1]) * dx) / distance
        require(lateral <= max(2.5, float(self.site["straight_tolerance_m"]) + 2),
                "ego departed surveyed straight corridor")
        require(-5 <= along <= distance + 5, "ego departed surveyed route extent")
        if along >= distance - 1.5:
            self.completed = True
        conflict = False
        if self.other is not None:
            location = self.other.get_location()
            point = [float(location.x), float(location.y)]
            require(all(math.isfinite(value) for value in point),
                    "nonfinite other-user pose")
            conflict = (inside(point, self.site["intersection_polygon_xy"]) or
                        inside(point, self.site["adjacent_crosswalk_polygon_xy"]))
        # A precautionary stop request is not a finding of lawful use or yield.
        demand = 0.0 if self.completed or conflict else self.speed
        heading = ego.get_transform().get_forward_vector()
        actual_heading = math.atan2(float(heading.y), float(heading.x))
        desired_heading = math.atan2(dy, dx)
        error = math.atan2(math.sin(desired_heading - actual_heading),
                           math.cos(desired_heading - actual_heading))
        steer = max(-0.6, min(0.6, error / 0.7))
        throttle = max(0.0, min(0.6, 0.2 * (demand - speed)))
        brake = max(0.0, min(1.0, 0.5 * (speed - demand)))
        if demand == 0:
            brake = max(brake, 0.7)
        command = self.carla.VehicleControl(throttle=throttle, brake=brake,
                                             steer=steer, hand_brake=False)
        ego.apply_control(command)
        return {"engineering_stop_requested": demand == 0,
                "conflict_region_occupied": conflict,
                "route_completed_request": self.completed,
                "legal_yield_verdict": None}
