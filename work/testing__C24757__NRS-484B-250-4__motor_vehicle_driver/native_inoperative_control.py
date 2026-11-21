"""Reversible Off-signal and stop-order controls for a planned Native capture.

This module imports no CARLA package. Native state and physical/legal results
must be checked from the original capture, not inferred from this controller.
"""

import math
from contextlib import contextmanager


def governing_lights(world, entrance_road_lanes):
    """Resolve one distinct Native head for each inventoried approach lane."""
    if not isinstance(entrance_road_lanes, list) or len(entrance_road_lanes) < 2:
        raise ValueError("All governed entrance lanes required")
    lanes = [tuple(row) for row in entrance_road_lanes]
    if len(set(lanes)) != len(lanes):
        raise ValueError("Duplicate entrance lane")
    lights = list(world.get_actors().filter("traffic.traffic_light*"))
    selected = []
    for road_id, lane_id in lanes:
        matching = [light for light in lights if any(
            point.road_id == road_id and point.lane_id == lane_id
            for point in light.get_affected_lane_waypoints())]
        if len(matching) != 1:
            raise ValueError("Expected one governing Native light per entrance")
        selected.append(matching[0])
    if len({light.id for light in selected}) != len(selected):
        raise ValueError("Distinct governed entrance heads required")
    return selected


@contextmanager
def all_heads_off(world, lights, traffic_light_state):
    """Request and read back Off, restoring each prior state on every exit."""
    if len(lights) < 2 or len({light.id for light in lights}) != len(lights):
        raise ValueError("Distinct governed entrance heads required")
    saved = []
    try:
        for light in lights:
            frozen = light.is_frozen() if callable(getattr(light, "is_frozen", None)) else False
            saved.append((light, light.get_state(), frozen))
            light.freeze(True)
            light.set_state(traffic_light_state.Off)
        world.tick()
        if any(light.get_state() != traffic_light_state.Off for light in lights):
            raise ValueError("Native Off readback failed")
        yield lights
    finally:
        for light, state, frozen in reversed(saved):
            light.set_state(state)
            light.freeze(frozen)
        if saved:
            world.tick()
            if any(light.get_state() != state or
                   (callable(getattr(light, "is_frozen", None)) and light.is_frozen() != frozen)
                   for light, state, frozen in saved):
                raise ValueError("Native signal restoration readback failed")


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
