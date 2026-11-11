"""Bounded Native control for posted-speed probes; observed motion decides outcome."""

import math


class PostedSpeedController:
    def __init__(self, target_mph, control_factory, gain=0.12):
        if isinstance(target_mph, bool) or not isinstance(target_mph, (float, int)) or not math.isfinite(target_mph) or target_mph <= 0:
            raise ValueError("Positive finite target mph required")
        if not callable(control_factory) or gain <= 0:
            raise ValueError("Control factory and positive gain required")
        self.target_mps = target_mph * 0.44704
        self.control_factory = control_factory
        self.gain = gain

    def step(self, vehicle, *, remaining_route_m, steering=0.0):
        velocity = vehicle.get_velocity()
        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        if not math.isfinite(speed) or not math.isfinite(remaining_route_m) or remaining_route_m < 0:
            raise ValueError("Finite speed and route clearance required")
        if not math.isfinite(steering) or abs(steering) > 1:
            raise ValueError("Invalid steering")
        stopping_allowance = speed * speed / 8.0 + 8.0
        if remaining_route_m <= stopping_allowance:
            throttle, brake = 0.0, 1.0
        else:
            error = self.target_mps - speed
            throttle = min(1.0, max(0.0, self.gain * error))
            brake = min(1.0, max(0.0, -self.gain * error))
        command = self.control_factory(throttle=throttle, brake=brake, steer=steering)
        vehicle.apply_control(command)
        return {"speed_mps": speed, "target_mps": self.target_mps,
                "route_remaining_m": remaining_route_m, "throttle": throttle,
                "brake": brake, "steer": steering}
