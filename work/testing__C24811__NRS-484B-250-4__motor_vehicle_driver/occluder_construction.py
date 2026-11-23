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
def spawn_verified_occluder(world, blueprint, transform, approach_rays,
                            vehicle_corridors=None, minimum_clearance_m=0):
    """Check realized sight obstruction and clearance from both travel paths."""
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
        clearances = {}
        if vehicle_corridors is not None:
            if (set(vehicle_corridors) != {"ego", "other"} or
                    not math.isfinite(minimum_clearance_m) or minimum_clearance_m < 1):
                raise ValueError("Two corridors and positive engineering clearance required")
            for name, points in vehicle_corridors.items():
                if len(points) < 2:
                    raise ValueError("Vehicle corridor requires two points")
                corridor = LineString([_xy(point) for point in points])
                clearances[name] = footprint.distance(corridor)
                if clearances[name] < minimum_clearance_m:
                    raise ValueError("Spawned occluder intrudes on vehicle corridor: " + name)
        yield {"actor": actor, "footprint_xy_m": list(footprint.exterior.coords),
               "approach_ray_intersections": hits,
               "vehicle_corridor_clearance_m": clearances}
    finally:
        actor.destroy()
