"""Tick-driven motor-vehicle approach/stop/departure requests for a rail crossing.

Commands are intentions. The saved original-frame audit decides what happened.
"""
from __future__ import annotations

import math

FEET_PER_METRE = 3.280839895013123


class RailApproachController:
    def __init__(self, ego, rail_xy, approach_unit_normal_xy, body_half_extent_m,
                 stop_gap_ft, control_factory, *, rolling=False, depart_on_conflict=False):
        if stop_gap_ft <= 0 or body_half_extent_m <= 0:
            raise ValueError("positive stop gap and body half extent required")
        if abs(math.hypot(*approach_unit_normal_xy) - 1.0) > 1e-6:
            raise ValueError("approach normal must be unit length")
        self.ego = ego
        self.rail = rail_xy
        self.normal = approach_unit_normal_xy
        self.extent = body_half_extent_m
        self.target_gap_m = stop_gap_ft / FEET_PER_METRE
        self.control_factory = control_factory
        self.rolling = rolling
        self.depart_on_conflict = depart_on_conflict
        self.stopped_frames = 0
        self.departed = False

    def _signed_body_gap(self):
        location = self.ego.get_location()
        cx = float(location.x) - self.rail[0]
        cy = float(location.y) - self.rail[1]
        return -(cx * self.normal[0] + cy * self.normal[1]) - self.extent

    def step(self, crossing_clear: bool):
        """Apply one Native command; clear signal is a scene input, not due care."""
        gap_error = self._signed_body_gap() - self.target_gap_m
        velocity = self.ego.get_velocity()
        forward_speed = velocity.x * self.normal[0] + velocity.y * self.normal[1]
        if not math.isfinite(gap_error) or not math.isfinite(forward_speed):
            raise ValueError("nonfinite Native position or velocity")
        if self.departed:
            control = self.control_factory(throttle=0.25, brake=0.0)
            phase = "departure_requested"
        elif gap_error <= 0.3 and abs(forward_speed) <= 0.05 and not self.rolling:
            self.stopped_frames += 1
            if (crossing_clear or self.depart_on_conflict) and self.stopped_frames >= 1:
                self.departed = True
                control = self.control_factory(throttle=0.25, brake=0.0)
                phase = "departure_requested"
            else:
                control = self.control_factory(throttle=0.0, brake=1.0)
                phase = "stop_hold_requested"
        elif self.rolling and gap_error <= 0.3:
            control = self.control_factory(throttle=0.12, brake=0.0)
            phase = "rolling_requested"
        else:
            # Kinematic stopping distance is an engineering command heuristic.
            braking_distance = max(0.0, forward_speed) ** 2 / (2 * 2.5)
            brake = 0.75 if gap_error <= max(1.0, braking_distance + 0.5) else 0.0
            control = self.control_factory(throttle=0.0 if brake else 0.18, brake=brake)
            phase = "braking_requested" if brake else "approach_requested"
        self.ego.apply_control(control)
        return {"phase": phase, "commanded_gap_error_m": gap_error,
                "native_forward_speed_mps": forward_speed,
                "stopped_frames_command_state": self.stopped_frames}
