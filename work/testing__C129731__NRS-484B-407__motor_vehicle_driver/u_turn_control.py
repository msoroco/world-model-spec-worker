"""Measured-feedback route request for a C129731 U-turn attempt.

Completion is an observed geometric/motion event, not a statutory decision.
"""
import math


def _wrap(angle):
    return (angle + 180) % 360 - 180


class UTurnController:
    def __init__(self, route_xyz_m, target_speed_mps=3.0, lookahead_m=3.0,
                 max_frame=1100):
        if not isinstance(route_xyz_m, list) or len(route_xyz_m) < 4 or any(
                not isinstance(p, list) or len(p) != 3 or any(
                    type(v) not in (int, float) or not math.isfinite(v) for v in p)
                for p in route_xyz_m):
            raise ValueError("Finite source-bound U-turn route required")
        if (type(target_speed_mps) not in (int, float) or not 0 < target_speed_mps <= 8
                or type(lookahead_m) not in (int, float) or not 0 < lookahead_m <= 10
                or type(max_frame) is not int or max_frame < 1):
            raise ValueError("Finite engineering speed, lookahead and timeout required")
        self.route = route_xyz_m
        self.target_speed = target_speed_mps
        self.lookahead = lookahead_m
        self.max_frame = max_frame
        self.progress = 1
        self.entry_heading_deg = math.degrees(math.atan2(
            route_xyz_m[1][1]-route_xyz_m[0][1],
            route_xyz_m[1][0]-route_xyz_m[0][0]))
        self.completed = False

    def step(self, carla, actor, frame):
        if type(frame) is not int or frame < 0:
            raise ValueError("Original Native frame required")
        pose = actor.get_transform()
        location = pose.location
        yaw = float(pose.rotation.yaw)
        velocity = actor.get_velocity()
        x, y = float(location.x), float(location.y)
        speed = math.sqrt(sum(float(getattr(velocity, axis))**2 for axis in "xyz"))
        if any(not math.isfinite(v) for v in (x, y, yaw, speed)):
            raise ValueError("Finite Native pose and velocity required")
        if frame > self.max_frame and not self.completed:
            raise ValueError("U-turn attempt exceeded planned capture")
        while self.progress < len(self.route)-1 and math.dist(
                (x, y), self.route[self.progress][:2]) < self.lookahead:
            self.progress += 1
        target = self.route[self.progress]
        distance = math.dist((x, y), target[:2])
        heading = math.atan2(target[1]-y, target[0]-x)
        error = (heading-math.radians(yaw)+math.pi) % (2*math.pi)-math.pi
        curvature = 2*math.sin(error)/max(distance, self.lookahead)
        steer = max(-1.0, min(1.0, -math.atan(2.8*curvature)/math.radians(35)))
        exit_distance = math.dist((x, y), self.route[-1][:2])
        observed_reversal = abs(_wrap(yaw-self.entry_heading_deg))
        # Brake at the reviewed route exit. Actual steering and stop are measured.
        braking = self.progress == len(self.route)-1 and exit_distance <= max(3.0, speed*speed/8)
        self.completed = self.completed or (exit_distance <= 2 and observed_reversal >= 150
                                            and speed <= 0.5)
        control = carla.VehicleControl()
        control.steer = steer
        control.throttle = 0 if braking or self.completed else max(
            0.0, min(0.5, 0.18+0.16*(self.target_speed-speed)))
        control.brake = 1.0 if braking or self.completed else min(0.35, max(
            0.0, 0.25*(speed-self.target_speed)))
        actor.apply_control(control)
        return {"original_frame": frame, "target_index": self.progress,
                "measured_speed_mps": speed, "exit_distance_m": exit_distance,
                "observed_reversal_deg": observed_reversal,
                "requested_reversal": True, "geometric_completion_observed": self.completed,
                "steer": steer, "throttle": control.throttle, "brake": control.brake}
