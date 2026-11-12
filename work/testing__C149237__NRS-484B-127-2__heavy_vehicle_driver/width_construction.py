"""Prospective Native construction for the statutory 80-inch width controls.

The caller supplies actual CARLA blueprint objects. A pinned truck class entry
only establishes the exported simulator class; legal truck/combination status
and realized overall width remain original-source review questions.
"""
from contextlib import contextmanager
import math

from truck_construction import _position, _projected_half_length, _width
from truck_site import CLASS_MAP, MIN_EDGE_MARGIN_M, ROAD_LENGTH_M, validate_site


WIDTH_M = 80 * .0254
CASES = {'ego_width_below_80in': ('ego','below'),
         'ego_width_at_80in': ('ego','at'),
         'lead_width_below_80in': ('lead','below')}


def _truck_blueprint(blueprint):
    identifier=getattr(blueprint,'id',blueprint)
    if not isinstance(identifier,str) or f"'{identifier}': 'truck'" not in CLASS_MAP.read_text():
        raise ValueError('Width candidate lacks pinned truck classification')
    return identifier


def _matches(width,category,tolerance_m):
    if category=='below':return width < WIDTH_M-tolerance_m
    if category=='at':return abs(width-WIDTH_M)<=tolerance_m
    raise ValueError('Unknown width category')


@contextmanager
def spawn_width_control_pair(world, case, fixed_blueprint, varied_blueprints,
                             transform_at, *, width_tolerance_m=.005,
                             gap_tolerance_m=.05):
    """Select by measured body width, stage both actors, and place a 152.4 m gap.

    Failure to find an exact width is reported honestly before capture; the
    synthetic CPU test does not assert that a shipped CARLA asset meets it.
    """
    if case not in CASES:raise ValueError('Unknown width control case')
    if not 0<width_tolerance_m<.05 or not 0<gap_tolerance_m<.5:
        raise ValueError('Invalid width/gap tolerance')
    site=validate_site();varied_role,category=CASES[case]
    _truck_blueprint(fixed_blueprint)
    if not isinstance(varied_blueprints,(tuple,list)) or not varied_blueprints:
        raise ValueError('Supply pinned truck width candidates')
    for blueprint in varied_blueprints:_truck_blueprint(blueprint)
    lane_y=-site['lane_width_m']/2
    actors=[]
    try:
        def spawn_matching(role):
            varied=role==varied_role
            options=varied_blueprints if varied else (fixed_blueprint,)
            x=100.0 if role=='ego' else 600.0
            for blueprint in options:
                actor=world.try_spawn_actor(blueprint,transform_at(x,lane_y,0.0))
                if actor is None:continue
                width=_width(actor)
                valid=(_matches(width,category,width_tolerance_m) if varied
                       else width>=WIDTH_M)
                if valid:
                    actors.append(actor)
                    return actor
                actor.destroy()
            raise ValueError('No pinned truck blueprint meets '+role+' width control '+category)
        ego=spawn_matching('ego')
        lead=spawn_matching('lead')
        ego_half=_projected_half_length(ego,(1,0))
        lead_half=_projected_half_length(lead,(1,0))
        target=152.4
        lead_x=_position(ego,(1,0))+ego_half+target+lead_half
        if _position(ego,(1,0))-ego_half<MIN_EDGE_MARGIN_M or lead_x+lead_half>ROAD_LENGTH_M-MIN_EDGE_MARGIN_M:
            raise ValueError('Width-control bodies exceed authored road margin')
        lead.set_transform(transform_at(lead_x,lane_y,0.0))
        world.tick()
        for role,actor in (('ego',ego),('lead',lead)):
            waypoint=world.get_map().get_waypoint(actor.get_location(),project_to_road=False)
            if waypoint is None or (waypoint.road_id,waypoint.lane_id)!=(site['road_id'],site['lane_id']):
                raise ValueError('Width-control '+role+' left authored following lane')
            _projected_half_length(actor,(1,0))
        actual=(_position(lead,(1,0))-_projected_half_length(lead,(1,0))
                -_position(ego,(1,0))-_projected_half_length(ego,(1,0)))
        if not math.isclose(actual,target,abs_tol=gap_tolerance_m):
            raise ValueError('Realized width-control body gap missed target')
        widths={'ego':_width(ego),'lead':_width(lead)}
        if not _matches(widths[varied_role],category,width_tolerance_m):
            raise ValueError('Selected width no longer matches target after staging')
        yield {'ego':ego,'lead':lead,'site':site,'width_control_case':case,
               'varied_role':varied_role,'width_category':category,
               'realized_widths_m':widths,'initial_body_gap_m':actual,
               'physical_motion':'unverified','legal_truck_class':'unresolved'}
    finally:
        for actor in reversed(actors):actor.destroy()
