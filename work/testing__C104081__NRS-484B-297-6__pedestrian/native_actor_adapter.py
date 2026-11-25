"""Bind surveyed sidewalk assets and original traffic actors to live CARLA calls.

The caller supplies a hash-verified original site survey. This module imports no
simulator at import time and never treats authored geometry as a site survey.
"""
from __future__ import annotations

import math

from native_readback import CarlaFrameReader
from native_walking import world_route


def _world_xy(x, y, transform):
    yaw = math.radians(transform["yaw_degrees"])
    return (transform["x"] + x * math.cos(yaw) - y * math.sin(yaw),
            transform["y"] + x * math.sin(yaw) + y * math.cos(yaw))


def _covers_surveyed_rectangle(actor, shape, transform):
    box = getattr(actor, "bounding_box", None)
    if box is None:
        return False
    vertices = box.get_world_vertices(actor.get_transform())
    yaw = math.radians(transform["yaw_degrees"])
    cosine, sine = math.cos(yaw), math.sin(yaw)
    local = [((float(point.x) - transform["x"]) * cosine +
              (float(point.y) - transform["y"]) * sine,
              -(float(point.x) - transform["x"]) * sine +
              (float(point.y) - transform["y"]) * cosine) for point in vertices]
    if len(local) < 4 or any(not math.isfinite(value) for point in local for value in point):
        return False
    xs, ys = zip(*local)
    return (min(xs) <= shape.x0 + .1 and max(xs) >= shape.x1 - .1 and
            min(ys) <= shape.y0 + .1 and max(ys) >= shape.y1 - .1)


class CarlaActorAdapter:
    """Own the walker and exact surveyed obstruction assets for one attempt."""

    def __init__(self, world, carla, survey):
        if world.get_map().name != survey.get("map_id"):
            raise ValueError("original Native map differs from surveyed map")
        self.world, self.carla, self.survey = world, carla, survey
        self.transform = survey["local_to_world"]
        self.obstacles = {}
        self.walker = None
        self.gap = None

    def spawn_obstacle(self, shape, transform):
        if transform != self.transform:
            raise ValueError("obstacle transform differs from source survey")
        asset = self.survey.get("obstacle_assets", {}).get(shape.name)
        expected = [shape.x0, shape.x1, shape.y0, shape.y1]
        if not isinstance(asset, dict) or asset.get("local_rectangle_m") != expected:
            raise ValueError("surveyed obstruction asset does not match exact case")
        blueprint_id = asset.get("blueprint_id")
        z = asset.get("z_m")
        if not isinstance(blueprint_id, str) or not blueprint_id.startswith("static.prop.") or \
                type(z) not in (int, float) or not math.isfinite(z):
            raise ValueError("surveyed obstruction blueprint or elevation missing")
        x, y = _world_xy((shape.x0 + shape.x1) / 2, (shape.y0 + shape.y1) / 2, transform)
        pose = self.carla.Transform(self.carla.Location(x=x, y=y, z=z),
                                    self.carla.Rotation(yaw=transform["yaw_degrees"]))
        actor = self.world.spawn_actor(self.world.get_blueprint_library().find(blueprint_id), pose)
        if actor is None or not getattr(actor, "is_alive", False):
            raise ValueError("Native obstruction spawn failed")
        try:
            covers = _covers_surveyed_rectangle(actor, shape, transform)
        except (AttributeError, TypeError, ValueError):
            covers = False
        if not covers:
            actor.destroy()
            raise ValueError("Native obstruction body does not cover surveyed impassable section")
        self.obstacles[shape.name] = actor
        return actor

    def verify_existing_gap(self, shape, transform):
        if transform != self.transform:
            raise ValueError("sidewalk gap transform differs from source survey")
        gap = self.survey.get("missing_sidewalk_gap")
        if not isinstance(gap, dict) or gap.get("local_rectangle_m") != \
                [shape.x0, shape.x1, shape.y0, shape.y1]:
            raise ValueError("original missing sidewalk polygon does not match exact case")
        vertices = gap.get("vertices_world_m")
        if not isinstance(vertices, list) or len(vertices) < 4 or any(
                not isinstance(point, list) or len(point) < 2 or
                any(type(value) not in (int, float) or not math.isfinite(value)
                    for value in point[:2]) for point in vertices):
            raise ValueError("original missing sidewalk polygon is incomplete")
        self.gap = vertices

    def spawn_pedestrian(self, point, transform):
        if transform != self.transform:
            raise ValueError("walker transform differs from source survey")
        blueprint_id = self.survey.get("pedestrian_blueprint")
        z = self.survey.get("pedestrian_spawn_z_m")
        if not isinstance(blueprint_id, str) or not blueprint_id.startswith("walker.pedestrian.") or \
                type(z) not in (int, float) or not math.isfinite(z):
            raise ValueError("original pedestrian blueprint or elevation missing")
        x, y = _world_xy(*point, transform)
        pose = self.carla.Transform(self.carla.Location(x=x, y=y, z=z),
                                    self.carla.Rotation(yaw=transform["yaw_degrees"]))
        actor = self.world.spawn_actor(self.world.get_blueprint_library().find(blueprint_id), pose)
        if actor is None or not getattr(actor, "is_alive", False):
            raise ValueError("Native pedestrian spawn failed")
        self.walker = actor
        return actor

    def set_pedestrian_route(self, walker, route, transform):
        if walker is not self.walker or transform != self.transform:
            raise ValueError("pedestrian route actor or survey changed")
        points = world_route(route, transform)
        if len(points) < 2 or any(not all(math.isfinite(c) for c in point) for point in points):
            raise ValueError("surveyed pedestrian route incomplete")
        # native_walking.run_constructed issues the actual per-tick controls.

    def readback(self, walker, owned, map_id):
        if walker is not self.walker or not getattr(walker, "is_alive", False) or \
                self.world.get_map().name != map_id or map_id != self.survey["map_id"]:
            raise ValueError("Native pedestrian/map readback failed")
        count = sum(actor in owned and getattr(actor, "is_alive", False)
                    for actor in self.obstacles.values())
        if count != len(self.obstacles):
            raise ValueError("Native obstruction actor disappeared")
        return {"map_id": map_id, "walker_spawned": True, "obstacle_count": count}

    def destroy(self, handle):
        handle.destroy()

    def source_reader_factory(self, rig):
        """Return the Native attempt callback with a surveyed traffic roster."""
        def create(world, walker, constructed, camera_recorder):
            if world is not self.world or walker is not self.walker or \
                    rig.recorder is not camera_recorder:
                raise ValueError("source reader actor/camera ownership mismatch")
            ids = self.survey.get("traffic_actor_ids")
            if not isinstance(ids, list) or not ids or any(type(value) is not int for value in ids):
                raise ValueError("original traffic actor roster missing")
            traffic = [world.get_actor(value) for value in ids]
            if any(actor is None or not getattr(actor, "is_alive", False) for actor in traffic):
                raise ValueError("surveyed traffic actor absent from original world")
            obstruction = self.obstacles.get("impassable_sidewalk_section")
            kind = constructed["design"]["obstruction_kind"]
            return CarlaFrameReader(
                walker, obstruction, self.obstacles.get("intervening_barrier"),
                traffic, rig.sync, obstruction_kind=kind,
                gap_vertices_world_m=self.gap, survey_transform=self.transform)
        return create
