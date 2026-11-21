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
            saved.append((light, light.get_state()))
            light.freeze(True)
            light.set_state(traffic_light_state.Off)
        world.tick()
        if any(light.get_state() != traffic_light_state.Off for light in lights):
            raise ValueError("Native Off readback failed")
        yield lights
    finally:
        for light, state in reversed(saved):
            light.set_state(state)
            light.freeze(False)
        if saved:
            world.tick()
            if any(light.get_state() != state for light, state in saved):
                raise ValueError("Native signal restoration readback failed")


class StopController:
    """Hold at a sourced boundary until a measured halt and release condition."""

    def __init__(self, release_frame, target_speed_mps, stop_tolerance_m=0.5):
        if type(release_frame) is not int or release_frame < 0:
            raise ValueError("Nonnegative release frame required")
        if not math.isfinite(target_speed_mps) or not 0 < target_speed_mps <= 20:
            raise ValueError("Finite positive target speed required")
        if not math.isfinite(stop_tolerance_m) or not 0 <= stop_tolerance_m <= 2:
            raise ValueError("Finite stop tolerance required")
        self.release_frame = release_frame
        self.target_speed_mps = target_speed_mps
        self.stop_tolerance_m = stop_tolerance_m
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
        if at_boundary and speed <= 0.01 and self.full_halt_frame is None:
            self.full_halt_frame = frame
        if front_to_boundary_signed_m < 0 and self.full_halt_frame is None:
            raise ValueError("Vehicle crossed stop boundary without measured full halt")
        held = (at_boundary and (self.full_halt_frame is None or
                frame <= self.release_frame or not release_condition))
        command = carla.VehicleControl()
        command.steer = steer
        command.throttle = 0.0 if held else max(0.0, min(0.65, 0.18 + 0.16 * (self.target_speed_mps - speed)))
        command.brake = 1.0 if held else (min(0.4, 0.3 * (speed - self.target_speed_mps)) if speed > self.target_speed_mps else 0.0)
        actor.apply_control(command)
        return {"frame": frame, "speed_mps": speed, "front_to_boundary_signed_m": front_to_boundary_signed_m,
                "full_halt_frame": self.full_halt_frame, "held": held,
                "release_condition": bool(release_condition), "throttle": command.throttle,
                "brake": command.brake}
