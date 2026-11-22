"""CPU geometry and yield-control plan for the sourced C125763 crossing.

Coordinates and lane/sign identities must come from a reviewed Native site.
This controller does not decide legal priority or official sign status.
"""
import math
from shapely.geometry import LineString, Point, Polygon


def _xy(value, label):
    if (not isinstance(value, (list, tuple)) or len(value) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v)
                for v in value)):
        raise ValueError(label + ' needs finite XY coordinates')
    return tuple(float(v) for v in value)


def validate_scene(scene):
    """Require both routes to enter one surveyed median crossing."""
    polygon=Polygon(scene['crossing_polygon_xy_m'])
    if not polygon.is_valid or polygon.area<=0 or scene.get('same_statutory_crossing') is not True:
        raise ValueError('One reviewed median crossing required')
    approaches=scene['approaches']
    if set(approaches)!={'ego','other'}:
        raise ValueError('Ego and other approaches required')
    ego,other=approaches['ego'],approaches['other']
    relation=scene['approach_relation']
    if relation=='different_highways':
        if ego['highway_id']==other['highway_id']:
            raise ValueError('Different-highway case has one highway')
    elif relation=='opposite_directions':
        a=_xy(ego['forward_xy'],'ego heading');b=_xy(other['forward_xy'],'other heading')
        length=math.hypot(*a)*math.hypot(*b)
        if (ego['highway_id']!=other['highway_id'] or length==0 or
                (a[0]*b[0]+a[1]*b[1])/length>-.8 or
                scene.get('other_left_turn_intended') is not True):
            raise ValueError('Opposite left-turn relation requires one highway and opposing headings')
    else:
        raise ValueError('Unknown approach relation')
    sign=scene['yield_sign']
    if not sign.get('native_id') or sign.get('governed_lane_id')!=ego['lane_id']:
        raise ValueError('Yield sign must govern ego entrance')
    for role,entry in approaches.items():
        route=[_xy(point,role+' route') for point in entry['route_xy_m']]
        if (len(route)<3 or polygon.intersects(Point(route[0])) or
                polygon.intersects(Point(route[-1])) or
                not LineString(route).intersects(polygon) or
                not any(polygon.contains(Point(point)) for point in route[1:-1]) or
                any(math.dist(a,b)<1 for a,b in zip(route,route[1:]))):
            raise ValueError(role+' route must cross the median interior from outside')
    yield_point=_xy(scene['ego_yield_line_xy_m'],'yield line')
    ego_route=[_xy(point,'ego route') for point in ego['route_xy_m']]
    if (polygon.intersects(Point(yield_point)) or
            LineString(ego_route[:2]).distance(Point(yield_point))>3):
        raise ValueError('Yield line must lie on ego approach before crossing')
    return scene


def yield_control(distance_to_line_m, speed_mps, conflict_clear,
                  target_speed_mps=5.0):
    """Brake for observed conflict; release when clear without a mandatory stop."""
    for value in (distance_to_line_m,speed_mps,target_speed_mps):
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError('Finite yield-control telemetry required')
    if type(conflict_clear) is not bool:
        raise ValueError('Measured conflict-clear boolean required')
    if distance_to_line_m < -.5 and not conflict_clear:
        raise ValueError('Ego crossed yield line into uncleared conflict')
    if not conflict_clear:
        braking_distance=speed_mps*speed_mps/(2*3.0)+1.0
        if distance_to_line_m<=braking_distance:
            return 0.0,1.0
        return min(.2,max(0.0,(2.0-speed_mps)*.1)),0.0
    return min(.45,max(0.0,(target_speed_mps-speed_mps)*.18)),0.0
