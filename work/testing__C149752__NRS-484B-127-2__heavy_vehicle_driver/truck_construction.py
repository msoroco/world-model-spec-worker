"""Native pair construction for the truck-following branch.

Caller supplies source-reviewed blueprints and two transforms on an identified
one-direction approach. This code spawns actors and verifies their realized
widths, lane and ordering before capture. It does not classify a blueprint as
a legal truck or measure a tractor/trailer combination.
"""

from contextlib import contextmanager
import importlib.util
import math
from pathlib import Path

_site_spec = importlib.util.spec_from_file_location('truck_site', Path(__file__).with_name('truck_site.py'))
_site = importlib.util.module_from_spec(_site_spec)
_site_spec.loader.exec_module(_site)


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


@contextmanager
def spawn_exact_gap_pair(world, ego_blueprint, lead_blueprint, gap_case, transform_at,
                         tolerance_m=0.05):
    """Place both actors from realized extents on the authored one-way lane.

    `transform_at(x,y,heading_deg)` is supplied by the Native caller. The lead is
    spawned at a safe staging point, then moved after its body length is known.
    The caller must review actual vehicle class and width as well as the site.
    """
    site = _site.validate_site()
    ego_id = getattr(ego_blueprint, 'id', ego_blueprint)
    lead_id = getattr(lead_blueprint, 'id', lead_blueprint)
    if ego_id not in site['blueprint_ids'] or lead_id not in site['blueprint_ids']:
        raise ValueError('Blueprint lacks pinned truck classification')
    if tolerance_m <= 0 or not math.isfinite(tolerance_m):
        raise ValueError('Invalid gap tolerance')
    lane_y = -site['lane_width_m'] / 2
    actors = []
    try:
        for blueprint, x in ((ego_blueprint, 100.0), (lead_blueprint, 600.0)):
            actor = world.try_spawn_actor(blueprint, transform_at(x, lane_y, 0.0))
            if actor is None:
                raise ValueError('Native vehicle staging spawn failed')
            actors.append(actor)
        ego, lead = actors
        if _width(ego) < MIN_WIDTH_M or _width(lead) < MIN_WIDTH_M:
            raise ValueError('Spawned vehicle below 80-inch width')
        ego_half = _projected_half_length(ego, (1.0, 0.0))
        lead_half = _projected_half_length(lead, (1.0, 0.0))
        placement = _site.initial_pair(gap_case, ego_half, lead_half)
        _site.validate_motion_envelope(placement, lead_half)
        lead.set_transform(transform_at(*placement['lead_center_xy_m'], placement['heading_deg']))
        world.tick()
        for actor in actors:
            wp = world.get_map().get_waypoint(actor.get_location(), project_to_road=False)
            if wp is None or (wp.road_id, wp.lane_id) != (site['road_id'], site['lane_id']):
                raise ValueError('Spawned truck left authored following lane')
        actual = (_position(lead, (1.0, 0.0)) - _projected_half_length(lead, (1.0, 0.0))
                  - _position(ego, (1.0, 0.0)) - _projected_half_length(ego, (1.0, 0.0)))
        if abs(actual - placement['planned_initial_body_gap_m']) > tolerance_m:
            raise ValueError('Realized initial truck gap missed target')
        yield {'ego': ego, 'lead': lead, 'site': site, 'initial_body_gap_m': actual,
               'realized_widths_m': {'ego': _width(ego), 'lead': _width(lead)},
               'physical_motion': 'unverified'}
    finally:
        for actor in reversed(actors):
            actor.destroy()
