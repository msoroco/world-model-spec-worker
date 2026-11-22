"""Stage a truck pair for an attempted pass using the opposing lane."""
from contextlib import contextmanager
import math

from overtaking_site import validate_site
from truck_construction import _position, _projected_half_length, _width
from truck_site import TRUCK_BLUEPRINTS

MIN_WIDTH_M = 80*.0254


@contextmanager
def spawn_overtaking_pair(world, ego_blueprint, lead_blueprint, transform_at,
                          *, gap_tolerance_m=.05):
    site = validate_site()
    ids = [getattr(bp, 'id', bp) for bp in (ego_blueprint, lead_blueprint)]
    if any(identifier not in TRUCK_BLUEPRINTS for identifier in ids):
        raise ValueError('Overtaking pair lacks pinned truck classification')
    actors = []
    lane_y = -site['lane_width_m']/2
    try:
        for blueprint, x in ((ego_blueprint, 100.0), (lead_blueprint, 600.0)):
            actor = world.try_spawn_actor(blueprint, transform_at(x, lane_y, 0.0))
            if actor is None:
                raise ValueError('Overtaking truck staging spawn failed')
            actors.append(actor)
        ego, lead = actors
        if any(_width(actor) < MIN_WIDTH_M for actor in actors):
            raise ValueError('Overtaking truck width below 80 inches')
        ego_half = _projected_half_length(ego, (1, 0))
        lead_half = _projected_half_length(lead, (1, 0))
        lead_x = _position(ego, (1, 0))+ego_half+150.0+lead_half
        if lead_x+lead_half+8*45 > 1150 or 100+20*45+ego_half > 1150:
            raise ValueError('Overtaking motion budget exceeds authored road')
        lead.set_transform(transform_at(lead_x, lane_y, 0.0))
        world.tick()
        for actor in actors:
            waypoint = world.get_map().get_waypoint(actor.get_location(), project_to_road=False)
            if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (site['road_id'], site['lane_id']):
                raise ValueError('Overtaking pair left sourced forward lane')
        gap = (_position(lead, (1, 0))-_projected_half_length(lead, (1, 0))
               -_position(ego, (1, 0))-_projected_half_length(ego, (1, 0)))
        if not math.isclose(gap, 150.0, abs_tol=gap_tolerance_m):
            raise ValueError('Overtaking pair missed fixed initial body gap')
        yield {'ego': ego, 'lead': lead, 'site': site, 'initial_body_gap_m': gap,
               'realized_widths_m': {'ego': _width(ego), 'lead': _width(lead)},
               'physical_motion': 'unverified'}
    finally:
        for actor in reversed(actors):
            actor.destroy()
