"""Native stop and rolling controllers adapted from same-law C24757.

The commanded motion is an engineering attempt; original frames decide the case.
"""

import math

class StopController:
    """Hold at a sourced boundary until a measured halt and release condition."""

    def __init__(self, release_frame, target_speed_mps, stop_tolerance_m=0.5,
                 approach_deceleration_mps2=3.0):
        if type(release_frame) is not int or release_frame < 0:
            raise ValueError("Nonnegative release frame required")
        if not math.isfinite(target_speed_mps) or not 0 < target_speed_mps <= 20:
            raise ValueError("Finite positive target speed required")
        if not math.isfinite(stop_tolerance_m) or not 0 <= stop_tolerance_m <= 2:
            raise ValueError("Finite stop tolerance required")
        if (type(approach_deceleration_mps2) not in (int, float) or
                not math.isfinite(approach_deceleration_mps2) or
                not 1 <= approach_deceleration_mps2 <= 8):
            raise ValueError("Bounded approach deceleration required")
        self.release_frame = release_frame
        self.target_speed_mps = target_speed_mps
        self.stop_tolerance_m = stop_tolerance_m
        self.approach_deceleration_mps2 = approach_deceleration_mps2
        self.full_halt_frame = None

    def step(self, carla, actor, frame, front_to_boundary_signed_m,
             steer=0.0, release_condition=True):
        if type(frame) is not int or frame < 0:
            raise ValueError("Nonnegative Native frame required")
        if not math.isfinite(front_to_boundary_signed_m):
            raise ValueError("Finite sourced boundary distance required")
        if not math.isfinite(steer) or abs(steer) > 1:
            raise ValueError("Finite steering command required")
        velocity = actor.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        if not math.isfinite(speed):
            raise ValueError("Finite Native speed feedback required")
        at_boundary = 0 <= front_to_boundary_signed_m <= self.stop_tolerance_m
        # Saved measurement recognizes an observed zero-speed sample. Do not
        # release on a merely slow nonzero sample that it would reject.
        if at_boundary and speed == 0.0 and self.full_halt_frame is None:
            self.full_halt_frame = frame
        if front_to_boundary_signed_m < 0 and self.full_halt_frame is None:
            raise ValueError("Vehicle crossed stop boundary without measured full halt")
        waiting = (self.full_halt_frame is None or frame <= self.release_frame or
                   not release_condition)
        held = at_boundary and waiting
        # This speed envelope starts braking before the complete body reaches
        # the sourced boundary. It is an engineering controller, not a legal
        # stopping-distance threshold; original motion still decides success.
        approach_target = min(self.target_speed_mps,
            math.sqrt(2 * self.approach_deceleration_mps2 *
                      max(0.0, front_to_boundary_signed_m - self.stop_tolerance_m)))
        command = carla.VehicleControl()
        command.steer = steer
        desired = self.target_speed_mps if not waiting else approach_target
        command.throttle = 0.0 if held or speed > desired else max(0.0, min(0.65, 0.18 + 0.16 * (desired - speed)))
        command.brake = 1.0 if held else (min(1.0, 0.35 * (speed - desired)) if speed > desired else 0.0)
        actor.apply_control(command)
        return {"frame": frame, "speed_mps": speed, "front_to_boundary_signed_m": front_to_boundary_signed_m,
                "full_halt_frame": self.full_halt_frame, "held": held,
                "approach_target_speed_mps": approach_target,
                "release_condition": bool(release_condition), "throttle": command.throttle,
                "brake": command.brake}


class RollingController:
    """Bounded no-halt comparison; saved observations decide what occurred."""

    def __init__(self, target_speed_mps, minimum_speed_mps=1.0):
        if (type(target_speed_mps) not in (int, float) or
                type(minimum_speed_mps) not in (int, float) or
                not math.isfinite(target_speed_mps) or
                not math.isfinite(minimum_speed_mps) or
                not 0 < minimum_speed_mps <= target_speed_mps <= 20):
            raise ValueError("Bounded rolling comparison speeds required")
        self.target_speed_mps = target_speed_mps
        self.minimum_speed_mps = minimum_speed_mps

    def step(self, carla, actor, frame, front_to_boundary_signed_m,
             steer=0.0, release_condition=True):
        if (type(frame) is not int or frame < 0 or
                not math.isfinite(front_to_boundary_signed_m) or
                not math.isfinite(steer) or abs(steer) > 1):
            raise ValueError("Finite rolling comparison input required")
        velocity = actor.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        if not math.isfinite(speed):
            raise ValueError("Finite Native speed feedback required")
        command = carla.VehicleControl()
        command.steer = steer
        command.throttle = max(0.0, min(0.65, 0.18 + 0.16 *
                              (self.target_speed_mps - speed))) if speed < self.target_speed_mps else 0.0
        command.brake = min(1.0, 0.35 * (speed - self.target_speed_mps)) if speed > self.target_speed_mps else 0.0
        actor.apply_control(command)
        return {"frame": frame, "speed_mps": speed,
                "front_to_boundary_signed_m": front_to_boundary_signed_m,
                "rolling_comparison": True, "minimum_speed_mps": self.minimum_speed_mps,
                "throttle": command.throttle, "brake": command.brake}
