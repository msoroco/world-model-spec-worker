"""Source-selected single-vehicle route control for a reviewed rotary island."""
from __future__ import annotations

import math

from island_source import route


def spawn(world, packet, transform_factory):
    if world.get_map().name != packet["map_name"]:
        raise ValueError("live map differs from independently reviewed island source")
    blueprint = world.get_blueprint_library().find(packet["ego_blueprint"])
    actor = world.try_spawn_actor(blueprint, transform_factory(packet["ego_spawn"]))
    if actor is None or not actor.type_id.startswith("vehicle."):
        raise RuntimeError("source-selected motor vehicle did not spawn")
    return actor


class RouteControl:
    """Bounded engineering route follower; observed path remains authoritative."""

    def __init__(self, points, selected_lane_id, control_factory, *, throttle=.35):
        self.points = route(points, selected_lane_id)
        if not callable(control_factory) or type(throttle) not in (int, float) or not 0 < throttle <= .5:
            raise ValueError("bounded Native control required")
        self.factory = control_factory
        self.throttle = float(throttle)
        self.index = 1

    def __call__(self, actor, tick):
        if type(tick) is not int or tick < 0:
            raise ValueError("invalid original tick")
        if self.index >= len(self.points):
            actor.apply_control(self.factory(throttle=0, steer=0, brake=1))
            return
        pose = actor.get_transform()
        x, y = float(pose.location.x), float(pose.location.y)
        yaw = math.radians(float(pose.rotation.yaw))
        if not all(map(math.isfinite, (x, y, yaw))):
            raise ValueError("original vehicle transform nonfinite")
        target = self.points[self.index]
        distance = math.hypot(target["x"] - x, target["y"] - y)
        if distance < .8:
            self.index += 1
            if self.index >= len(self.points):
                actor.apply_control(self.factory(throttle=0, steer=0, brake=1))
                return
            target = self.points[self.index]
            distance = math.hypot(target["x"] - x, target["y"] - y)
        previous = self.points[self.index - 1]
        dx, dy = target["x"] - previous["x"], target["y"] - previous["y"]
        cross_track = abs((x - previous["x"]) * dy - (y - previous["y"]) * dx) / math.hypot(dx, dy)
        if cross_track > 4:
            raise ValueError("original island route tracking lost")
        target_heading = math.atan2(target["y"] - y, target["x"] - x)
        error = (target_heading - yaw + math.pi) % (2 * math.pi) - math.pi
        steer = max(-1., min(1., math.atan(2.7 * 2 * math.sin(error) / max(distance, .8)) / .65))
        actor.apply_control(self.factory(throttle=self.throttle, steer=steer, brake=0))
