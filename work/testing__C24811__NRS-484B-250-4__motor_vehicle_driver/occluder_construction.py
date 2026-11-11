"""Spawn a physical sight occluder and verify two approach rays intersect it.

The caller supplies a source-reviewed blueprint and clear roadway placement.
Planar ray intersection is a CPU geometry check, not proof of camera visibility.
"""

from contextlib import contextmanager
import math

from shapely.geometry import LineString, MultiPoint


def _xy(point):
    x, y = float(point.x), float(point.y)
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("Nonfinite ray or occluder position")
    return x, y


@contextmanager
def spawn_verified_occluder(world, blueprint, transform, approach_rays):
    """Require a realized footprint to cross each declared viewpoint-to-target ray."""
    if not isinstance(approach_rays, dict) or set(approach_rays) != {"ego", "other"}:
        raise ValueError("Two approach rays required")
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise ValueError("Native occluder spawn failed")
    try:
        vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
        if len(vertices) < 4:
            raise ValueError("Native occluder body vertices missing")
        footprint = MultiPoint([_xy(point) for point in vertices]).convex_hull
        if footprint.area <= 0:
            raise ValueError("Native occluder footprint has no area")
        hits = {}
        for name, pair in approach_rays.items():
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ValueError("Invalid approach ray: " + name)
            ray = LineString([_xy(point) for point in pair])
            if ray.length <= 0:
                raise ValueError("Zero approach ray: " + name)
            hits[name] = ray.intersects(footprint)
        if not all(hits.values()):
            raise ValueError("Spawned geometry does not obstruct both approach rays")
        yield {"actor": actor, "footprint_xy_m": list(footprint.exterior.coords),
               "approach_ray_intersections": hits}
    finally:
        actor.destroy()
