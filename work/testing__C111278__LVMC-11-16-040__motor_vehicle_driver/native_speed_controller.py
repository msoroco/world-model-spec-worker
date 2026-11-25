"""Engineering speed target for the six intersection traversal constructions.

The requested speed is a control input. Original ego velocity in the sealed
capture, rather than this target, supplies the measurement.
"""
from __future__ import annotations

import math


class SpeedControlError(ValueError):
    pass


class NativeSpeedController:
    def __init__(self, target_mps: float, control_factory, gain: float = 1.0):
        if (type(target_mps) not in (int, float) or
                not math.isfinite(target_mps) or target_mps < 0):
            raise SpeedControlError("invalid engineering speed target")
        if not callable(control_factory):
            raise SpeedControlError("Native vehicle control factory required")
        if type(gain) not in (int, float) or not math.isfinite(gain) or not 0.5 <= gain <= 1.25:
            raise SpeedControlError("bounded controller gain required")
        self.target_mps = float(target_mps)
        self.control_factory = control_factory
        self.gain = float(gain)

    def apply(self, ego):
        velocity = ego.get_velocity()
        components = (velocity.x, velocity.y, velocity.z)
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in components):
            raise SpeedControlError("original velocity unavailable to controller")
        measured = math.sqrt(sum(v * v for v in components))
        error = self.target_mps - measured
        throttle = min(0.55, max(0.0, 0.22 + 0.18 * self.gain * error)) if error >= -0.1 else 0.0
        brake = min(0.65, max(0.0, -0.25 * error)) if error < -0.1 else 0.0
        control = self.control_factory(throttle=throttle, brake=brake, steer=0.0)
        ego.apply_control(control)
        return {"original_speed_mps": measured, "target_mps": self.target_mps,
                "throttle": throttle, "brake": brake, "controller_gain": self.gain}
