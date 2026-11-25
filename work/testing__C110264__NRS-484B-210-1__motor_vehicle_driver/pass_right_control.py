"""Source-bound Native vehicle placement and right-pass control requests.

This module does not infer observed motion from its commands. The session's
snapshot sampler and saved audit decide whether the maneuver actually occurred.
"""
from __future__ import annotations

import math

from pass_right_actor import _segments
from pass_right_capture import CAMERAS
from pass_right_media import PROFILE


def station_to_world(packet: dict, station_m: float, lateral_m: float) -> tuple[float, float, float]:
    """Interpolate an original map centerline in its right-positive frame."""
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (station_m, lateral_m)):
        raise ValueError('finite source station and lateral position required')
    segments = _segments(packet)
    if station_m < segments[0][0] or station_m > segments[-1][1]:
        raise ValueError('station outside source-reviewed corridor')
    for s0, s1, x0, y0, dx, dy, length, bounds0, bounds1 in segments:
        if s0 <= station_m <= s1:
            fraction = (station_m - s0) / (s1 - s0)
            left = bounds0[0] + fraction * (bounds1[0] - bounds0[0])
            right = bounds0[1] + fraction * (bounds1[1] - bounds0[1])
            half_width = packet['actor_half_width_m']
            if not left + half_width <= lateral_m <= right - half_width:
                raise ValueError('requested actor footprint leaves original pavement')
            x = x0 + fraction * dx + lateral_m * dy / length
            y = y0 + fraction * dy - lateral_m * dx / length
            return x, y, math.degrees(math.atan2(dy, dx))
    raise ValueError('source station interpolation failed')


def _route_xy(packet: dict, path: list) -> list[tuple[float, float]]:
    return [station_to_world(packet, row[0], row[1])[:2] for row in path]


class RouteFollower:
    """Issue bounded steering, throttle and brake toward source-bound waypoints."""

    def __init__(self, path_xy: list[tuple[float, float]], speed_mps: float,
                 waypoint_radius_m: float = 1.0):
        if len(path_xy) < 3 or speed_mps <= 0 or waypoint_radius_m <= 0:
            raise ValueError('source route, positive speed and radius required')
        if any(len(point) != 2 or not all(math.isfinite(v) for v in point) for point in path_xy):
            raise ValueError('finite source route XY required')
        self.path = path_xy
        self.speed_mps = speed_mps
        self.radius = waypoint_radius_m
        self.index = 0

    def command(self, x: float, y: float, yaw_deg: float, speed_mps: float) -> dict:
        if not all(math.isfinite(v) for v in (x, y, yaw_deg, speed_mps)):
            raise ValueError('finite original actor readback required')
        # Actors can spawn partway along a reviewed route. Select the next
        # waypoint ahead of the nearest route point, never a point behind spawn.
        nearest = min(range(len(self.path)), key=lambda i: math.dist((x, y), self.path[i]))
        self.index = max(self.index, min(nearest + 1, len(self.path) - 1))
        while self.index < len(self.path) - 1 and math.dist((x, y), self.path[self.index]) <= self.radius:
            self.index += 1
        goal = self.path[self.index]
        error = (math.degrees(math.atan2(goal[1] - y, goal[0] - x)) - yaw_deg + 180) % 360 - 180
        steer = max(-1.0, min(1.0, error / 35.0))
        delta = self.speed_mps - speed_mps
        throttle = max(0.0, min(0.55, 0.18 * delta))
        brake = max(0.0, min(0.65, -0.25 * delta))
        complete = self.index == len(self.path) - 1 and math.dist((x, y), goal) <= self.radius
        if complete:
            throttle, brake = 0.0, 0.65
        return {'steer': steer, 'throttle': throttle, 'brake': brake,
                'route_complete_request': complete}


def make_controller(ego, target, packet: dict, case: dict, *, control_factory,
                    left_signal_mask: int, ego_speed_mps: float, target_speed_mps: float):
    """Return the session before-tick callback for both original Native actors."""
    if not isinstance(left_signal_mask, int) or left_signal_mask <= 0:
        raise ValueError('CARLA left signal mask required')
    if not all(hasattr(actor, 'get_transform') and hasattr(actor, 'get_velocity') and
               hasattr(actor, 'apply_control') for actor in (ego, target)):
        raise ValueError('live controllable Native actors required')
    followers = ((ego, RouteFollower(_route_xy(packet, case['ego_path_s_lateral_m']), ego_speed_mps)),
                 (target, RouteFollower(_route_xy(packet, case['target_path_s_lateral_m']), target_speed_mps)))

    def before_tick(index: int):
        if not isinstance(index, int) or index < 0:
            raise ValueError('nonnegative Native tick index required')
        for actor, follower in followers:
            transform = actor.get_transform()
            velocity = actor.get_velocity()
            cmd = follower.command(transform.location.x, transform.location.y,
                                   transform.rotation.yaw, math.hypot(velocity.x, velocity.y))
            actor.apply_control(control_factory(throttle=cmd['throttle'], steer=cmd['steer'],
                                                brake=cmd['brake']))
        requested = bool(case['target_left_signal_request'])
        state = int(target.get_light_state())
        target.set_light_state((state | left_signal_mask) if requested else (state & ~left_signal_mask))

    return before_tick


def spawn_source_actors(world, packet: dict, case: dict, *, blueprint_library,
                        transform_factory, location_factory, rotation_factory,
                        ego_blueprint_id: str, target_blueprint_id: str,
                        ego_start_s_m: float, target_start_s_m: float):
    """Spawn two distinct vehicles at reviewed source stations, cleaning partial creation."""
    if target_start_s_m <= ego_start_s_m + 2 * packet['actor_half_width_m']:
        raise ValueError('source target must start ahead of ego with clearance')
    built = []
    try:
        for blueprint_id, station, path in ((ego_blueprint_id, ego_start_s_m, case['ego_path_s_lateral_m']),
                                            (target_blueprint_id, target_start_s_m, case['target_path_s_lateral_m'])):
            if not isinstance(blueprint_id, str) or not blueprint_id.startswith('vehicle.'):
                raise ValueError('specific Native vehicle blueprint required')
            x, y, yaw = station_to_world(packet, station, path[0][1])
            blueprint = blueprint_library.find(blueprint_id)
            transform = transform_factory(location_factory(x=x, y=y, z=0.5),
                                          rotation_factory(yaw=yaw))
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None or not getattr(actor, 'is_alive', False):
                raise ValueError('Native vehicle spawn failed at source station')
            built.append(actor)
        if built[0].id == built[1].id:
            raise ValueError('Native actor IDs are not distinct')
        return tuple(built)
    except Exception:
        for actor in reversed(built):
            actor.destroy()
        raise


def spawn_four_cameras(world, ego, *, blueprint_library, transform_factory,
                       location_factory, rotation_factory, mounts: dict):
    """Attach exactly four original RGB cameras; clean up on partial failure.

    Mount poses are operator supplied and must be physically reviewed later.
    They are not derived from a diagnostic recording or assumed visibility.
    """
    if not isinstance(mounts, dict) or set(mounts) != set(CAMERAS):
        raise ValueError('four reviewed camera mounts required')
    sensors = {}
    try:
        for name in CAMERAS:
            pose = mounts[name]
            if (not isinstance(pose, dict) or set(pose) != {'x', 'y', 'z', 'yaw', 'pitch'} or
                    not all(isinstance(v, (int, float)) and math.isfinite(v) for v in pose.values())):
                raise ValueError(name + ' finite camera mount pose required')
            width, height = PROFILE[name]
            blueprint = blueprint_library.find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('sensor_tick', '0.05')
            transform = transform_factory(location_factory(x=pose['x'], y=pose['y'], z=pose['z']),
                                          rotation_factory(yaw=pose['yaw'], pitch=pose['pitch']))
            sensor = world.spawn_actor(blueprint, transform, attach_to=ego)
            if sensor is None or not getattr(sensor, 'is_alive', False):
                raise ValueError(name + ' Native camera spawn failed')
            sensors[name] = sensor
        return sensors
    except Exception:
        for sensor in reversed(tuple(sensors.values())):
            sensor.destroy()
        raise
