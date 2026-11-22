"""Native pair placement for the two available same-direction lanes case."""
from contextlib import contextmanager
import math

from truck_construction import _position,_projected_half_length,_width
from truck_site import TRUCK_BLUEPRINTS
from two_lane_site import validate_site

MIN_WIDTH_M=80*.0254


@contextmanager
def spawn_two_lane_pair(world,ego_blueprint,lead_blueprint,transform_at,
                        *,gap_tolerance_m=.05):
    site=validate_site()
    ids=[getattr(bp,'id',bp) for bp in (ego_blueprint,lead_blueprint)]
    if any(identifier not in TRUCK_BLUEPRINTS for identifier in ids):
        raise ValueError('Two-lane pair lacks pinned truck classification')
    actors=[];lane_y=-site['lane_width_m']/2
    try:
        for blueprint,x in ((ego_blueprint,100.0),(lead_blueprint,600.0)):
            actor=world.try_spawn_actor(blueprint,transform_at(x,lane_y,0.0))
            if actor is None:raise ValueError('Two-lane truck staging spawn failed')
            actors.append(actor)
        ego,lead=actors
        if any(_width(actor)<MIN_WIDTH_M for actor in actors):
            raise ValueError('Two-lane truck width below 80 inches')
        ego_half=_projected_half_length(ego,(1,0));lead_half=_projected_half_length(lead,(1,0))
        lead_x=_position(ego,(1,0))+ego_half+150.0+lead_half
        if lead_x+lead_half>1150:raise ValueError('Two-lane body exceeds road travel margin')
        lead.set_transform(transform_at(lead_x,lane_y,0.0));world.tick()
        for actor in actors:
            waypoint=world.get_map().get_waypoint(actor.get_location(),project_to_road=False)
            if waypoint is None or (waypoint.road_id,waypoint.lane_id)!=(site['road_id'],site['following_lane_id']):
                raise ValueError('Two-lane pair left sourced following lane')
        actual=(_position(lead,(1,0))-_projected_half_length(lead,(1,0))
                -_position(ego,(1,0))-_projected_half_length(ego,(1,0)))
        if not math.isclose(actual,150.0,abs_tol=gap_tolerance_m):
            raise ValueError('Two-lane pair missed fixed body-gap target')
        yield {'ego':ego,'lead':lead,'site':dict(site,lane_id=site['following_lane_id']),
               'initial_body_gap_m':actual,
               'realized_widths_m':{'ego':_width(ego),'lead':_width(lead)},
               'physical_motion':'unverified'}
    finally:
        for actor in reversed(actors):actor.destroy()
