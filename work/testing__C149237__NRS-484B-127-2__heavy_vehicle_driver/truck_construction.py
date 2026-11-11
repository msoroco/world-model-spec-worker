"""Native pair construction for the truck-following branch.

Caller supplies source-reviewed blueprints and two transforms on an identified
one-direction approach. This code spawns actors and verifies their realized
widths, lane and ordering before capture. It does not classify a blueprint as
a legal truck or measure a tractor/trailer combination.
"""

from contextlib import contextmanager
import math


MIN_WIDTH_M = 80 * 0.0254


def _width(actor):
    extent = actor.bounding_box.extent
    width = 2.0 * float(extent.y)
    if not math.isfinite(width) or width <= 0:
        raise ValueError("Native vehicle width missing")
    return width


def _position(actor, tangent):
    point = actor.get_location()
    return point.x * tangent[0] + point.y * tangent[1]


def _projected_half_length(actor, tangent):
    forward = actor.get_transform().get_forward_vector()
    fx, fy = float(forward.x), float(forward.y)
    dot = fx * tangent[0] + fy * tangent[1]
    if not math.isfinite(dot) or dot <= 0:
        raise ValueError("Spawned vehicle faces against selected lane direction")
    cross = fx * tangent[1] - fy * tangent[0]
    extent = actor.bounding_box.extent
    return abs(dot) * float(extent.x) + abs(cross) * float(extent.y)


@contextmanager
def spawn_qualifying_pair(world, ego_blueprint, lead_blueprint,
                          ego_transform, lead_transform, road_id, lane_id,
                          lane_forward_xy):
    """Spawn and check two >=80-inch vehicles, then always destroy owned actors."""
    tx, ty = map(float, lane_forward_xy)
    norm = math.hypot(tx, ty)
    if not math.isfinite(norm) or norm == 0:
        raise ValueError("Invalid sourced lane tangent")
    tangent = (tx / norm, ty / norm)
    actors = []
    try:
        for blueprint, transform in ((ego_blueprint, ego_transform),
                                     (lead_blueprint, lead_transform)):
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError("Native vehicle spawn failed")
            actors.append(actor)
        ego, lead = actors
        for actor in actors:
            if _width(actor) < MIN_WIDTH_M:
                raise ValueError("Spawned vehicle below 80-inch width")
            waypoint = world.get_map().get_waypoint(actor.get_location(), project_to_road=False)
            if waypoint is None or waypoint.road_id != road_id or waypoint.lane_id != lane_id:
                raise ValueError("Spawned vehicle outside selected following lane")
        front = _position(ego, tangent) + _projected_half_length(ego, tangent)
        rear = _position(lead, tangent) - _projected_half_length(lead, tangent)
        gap = rear - front
        if gap < 0:
            raise ValueError("Lead does not begin ahead of ego without overlap")
        yield {"ego": ego, "lead": lead, "initial_longitudinal_body_gap_m": gap,
               "realized_widths_m": {"ego": _width(ego), "lead": _width(lead)},
               "road_id": road_id, "lane_id": lane_id}
    finally:
        for actor in reversed(actors):
            actor.destroy()
