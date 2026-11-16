"""Parametric, source checked truck gap placement for a later judgment sweep.

The sweep samples physical conditions. It makes no legal classification. Native
body extents and lane readbacks are required before a capture can proceed.
"""
from contextlib import contextmanager
import importlib.util
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


site = _module('truck_site')
construction = _module('truck_construction')

# Coverage points span shorter, statutory-reference, and longer separation.
# They are engineering setpoints, never legal judgment boundaries.
GAP_POINTS_M = (120.0, 152.4, 200.0)
SPEED_MPS = 12.0
DURATION_S = 45.0


def placement(gap_m, ego_half_m, lead_half_m):
    source = site.validate_site()
    if gap_m not in GAP_POINTS_M:
        raise ValueError('Unselected sweep point')
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or
           not math.isfinite(v) or v <= 0 for v in (ego_half_m, lead_half_m)):
        raise ValueError('Realized positive body half lengths required')
    ego_x = site.EGO_S_M
    lead_x = ego_x + ego_half_m + gap_m + lead_half_m
    if ego_x - ego_half_m < site.MIN_EDGE_MARGIN_M:
        raise ValueError('Ego body violates authored-road entry margin')
    end_front = lead_x + lead_half_m + SPEED_MPS * DURATION_S
    if end_front > site.ROAD_LENGTH_M - site.MIN_EDGE_MARGIN_M:
        raise ValueError('Sweep point exceeds authored-road motion envelope')
    return {'ego_center_xy_m': [ego_x, -source['lane_width_m'] / 2],
            'lead_center_xy_m': [lead_x, -source['lane_width_m'] / 2],
            'target_body_gap_m': gap_m, 'projected_end_front_m': end_front,
            'road_sha256': source['road_sha256'], 'road_id': source['road_id'],
            'lane_id': source['lane_id'], 'source_length_m': site.ROAD_LENGTH_M,
            'physical_motion': 'unverified'}


@contextmanager
def spawn_sweep_pair(world, ego_blueprint, lead_blueprint, gap_m, transform_at,
                     tolerance_m=0.05):
    """Stage, measure Native extents, move, read back and clean up both actors."""
    source = site.validate_site()
    if gap_m not in GAP_POINTS_M:
        raise ValueError('Unselected sweep point')
    if not math.isfinite(tolerance_m) or tolerance_m <= 0:
        raise ValueError('Invalid gap tolerance')
    ids = source['blueprint_ids']
    if any(getattr(bp, 'id', bp) not in ids for bp in (ego_blueprint, lead_blueprint)):
        raise ValueError('Blueprint lacks pinned truck classification')
    lane_y = -source['lane_width_m'] / 2
    actors = []
    try:
        for blueprint, x in ((ego_blueprint, 100.0), (lead_blueprint, 600.0)):
            actor = world.try_spawn_actor(blueprint, transform_at(x, lane_y, 0.0))
            if actor is None:
                raise ValueError('Native sweep truck spawn failed')
            actors.append(actor)
        ego, lead = actors
        if any(construction._width(actor) < construction.MIN_WIDTH_M for actor in actors):
            raise ValueError('Spawned sweep vehicle below 80-inch width')
        ego_half = construction._projected_half_length(ego, (1.0, 0.0))
        lead_half = construction._projected_half_length(lead, (1.0, 0.0))
        plan = placement(gap_m, ego_half, lead_half)
        lead.set_transform(transform_at(*plan['lead_center_xy_m'], 0.0))
        world.tick()
        for actor in actors:
            wp = world.get_map().get_waypoint(actor.get_location(), project_to_road=False)
            if wp is None or (wp.road_id, wp.lane_id) != (source['road_id'], source['lane_id']):
                raise ValueError('Sweep truck left authored following lane')
        actual = (construction._position(lead, (1.0, 0.0)) -
                  construction._projected_half_length(lead, (1.0, 0.0)) -
                  construction._position(ego, (1.0, 0.0)) -
                  construction._projected_half_length(ego, (1.0, 0.0)))
        if abs(actual - gap_m) > tolerance_m:
            raise ValueError('Native sweep gap readback missed setpoint')
        yield {'ego': ego, 'lead': lead, 'placement': plan,
               'initial_body_gap_m': actual,
               'realized_widths_m': {'ego': construction._width(ego),
                                     'lead': construction._width(lead)},
               'physical_motion': 'unverified'}
    finally:
        for actor in reversed(actors):
            actor.destroy()
