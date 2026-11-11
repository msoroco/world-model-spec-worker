"""Native vehicle speed request with bounded throttle/brake and measured feedback.

The controller targets speed cases; the saved trace, not its target, establishes
the measured rate. At 80 mph an alley may be physically infeasible or unsafe;
the route finder must verify an actual long, unobstructed candidate before use.
"""

import math


MPH_TO_MPS = 0.44704


class SpeedController:
    def __init__(self, target_mph, control_factory, *, gain=0.12):
        if not isinstance(target_mph, (int, float)) or isinstance(target_mph, bool) or not math.isfinite(target_mph) or target_mph <= 0:
            raise ValueError("Positive finite target mph required")
        if not callable(control_factory) or gain <= 0:
            raise ValueError("Control factory and positive gain required")
        self.target_mps = target_mph * MPH_TO_MPS
        self.control_factory = control_factory
        self.gain = gain

    def step(self, vehicle, *, distance_to_route_end_m, steering=0.0):
        velocity = vehicle.get_velocity()
        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        if not math.isfinite(speed) or not math.isfinite(distance_to_route_end_m) or distance_to_route_end_m < 0:
            raise ValueError("Finite measured speed and route clearance required")
        if not math.isfinite(steering) or abs(steering) > 1:
            raise ValueError("Invalid steering request")
        # This is engineering braking, not a legal stopping-distance claim.
        stopping_allowance = speed * speed / (2 * 4.0) + 8.0
        if distance_to_route_end_m <= stopping_allowance:
            throttle, brake = 0.0, 1.0
        else:
            error = self.target_mps - speed
            throttle = min(1.0, max(0.0, self.gain * error))
            brake = min(1.0, max(0.0, -self.gain * error))
        command = self.control_factory(throttle=throttle, brake=brake, steer=steering)
        vehicle.apply_control(command)
        return {"measured_speed_mps": speed, "target_speed_mps": self.target_mps,
                "distance_to_route_end_m": distance_to_route_end_m,
                "throttle": throttle, "brake": brake, "steer": steering}
