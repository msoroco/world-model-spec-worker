"""Portable route follower for the left-turn, center-lane and merge phases.

The path comes from a source-verified Native site. This controller commands
motion only; original measurements decide what the vehicle actually did.
"""

from math import atan2, hypot, pi


def _wrap(angle):
    return (angle + pi) % (2 * pi) - pi


class TurnMergeController:
    def __init__(self, route_xy_m, target_speed_mps=4.0, waypoint_radius_m=1.5):
        if not isinstance(route_xy_m, list) or len(route_xy_m) < 4:
            raise ValueError("route needs entry, center-lane and through-lane waypoints")
        self.route = [tuple(map(float, point)) for point in route_xy_m]
        if any(len(point) != 2 for point in self.route):
            raise ValueError("waypoints must be planar")
        if target_speed_mps <= 0 or waypoint_radius_m <= 0:
            raise ValueError("speed and waypoint radius must be positive")
        self.target_speed = float(target_speed_mps)
        self.radius = float(waypoint_radius_m)
        self.index = 0

    def command(self, x_m, y_m, yaw_rad, speed_mps):
        while self.index < len(self.route) - 1 and hypot(self.route[self.index][0] - x_m, self.route[self.index][1] - y_m) <= self.radius:
            self.index += 1
        goal_x, goal_y = self.route[self.index]
        heading_error = _wrap(atan2(goal_y - y_m, goal_x - x_m) - yaw_rad)
        steer = max(-1.0, min(1.0, heading_error / 0.65))
        speed_error = self.target_speed - speed_mps
        throttle = max(0.0, min(0.55, 0.22 * speed_error))
        brake = max(0.0, min(0.6, -0.3 * speed_error))
        arrived = self.index == len(self.route) - 1 and hypot(goal_x - x_m, goal_y - y_m) <= self.radius
        if arrived:
            throttle, brake = 0.0, 0.6
        return {"steer": steer, "throttle": throttle, "brake": brake,
                "waypoint_index": self.index, "route_complete": arrived}

    def apply(self, vehicle, x_m, y_m, yaw_rad, speed_mps, control_factory=None):
        command = self.command(x_m, y_m, yaw_rad, speed_mps)
        if control_factory is None:
            import carla  # Loaded only during an authorized local Native run.
            control_factory = carla.VehicleControl
        vehicle.apply_control(control_factory(throttle=command["throttle"],
                                              steer=command["steer"], brake=command["brake"]))
        return command
