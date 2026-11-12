"""CPU geometry and observations for one-way to one-way left turns.

Curb gaps are measured physical quantities, not a legal definition of
'as close as practicable'. The two one-way directions are north and west.
"""
from dataclasses import dataclass
from math import cos, sin, pi, isfinite, hypot

@dataclass(frozen=True)
class Case:
    name: str
    approach_center_x: float
    departure_center_y: float

CASES={
 'left_edge_reference':Case('left_edge_reference',-4.5,-4.5),
 'approach_shifted_right':Case('approach_shifted_right',-3.5,-4.5),
 'departure_shifted_right':Case('departure_shifted_right',-4.5,-3.5),
}

CURB=-6.0
BODY_HALF_WIDTH=.9


def route(case, samples=12):
    """Continuous quarter arc with tangent northbound entry and westbound exit."""
    if samples<3: raise ValueError('arc sampling too sparse')
    # The centre of curvature lies to the left of the incoming heading.
    radius=4.5
    cx=case.approach_center_x-radius
    cy=case.departure_center_y-radius
    arc=[(cx+radius*cos(i*pi/(2*samples)),cy+radius*sin(i*pi/(2*samples)))
         for i in range(samples+1)]
    points=[(case.approach_center_x,-60.0),(case.approach_center_x,cy)]
    points.extend(arc[1:])
    points.append((-60.0,case.departure_center_y))
    return points


def construct(adapter,case):
    roads=adapter.one_way_intersection(approach_direction='north',
                                       departure_direction='west',
                                       approach_left_curb_x=CURB,
                                       departure_left_curb_y=CURB,
                                       roadway_half_width_m=6.0)
    path=route(case)
    ego=adapter.vehicle(role='ego',route=path,maneuver='left_turn',target_mps=5.0)
    return {'roads':roads,'ego':ego,'route':path}


def measure(samples):
    """Measure full-body left edge against the corresponding physical curb."""
    if len(samples)<2: raise ValueError('missing approach/departure history')
    observed=[]; last=None
    for s in samples:
        if not s.get('body_corners_xy') or len(s['body_corners_xy'])<4:
            raise ValueError('missing measured body footprint')
        if any(len(p)!=2 or not all(isinstance(v,(int,float)) and isfinite(v) for v in p)
               for p in s['body_corners_xy']):
            raise ValueError('invalid measured body footprint')
        if s.get('native_road_direction') not in ('north','turn','west'):
            raise ValueError('one-way direction unverified')
        if not isinstance(s.get('time_s'),(int,float)) or not isfinite(s['time_s']) or (last is not None and s['time_s']<=last):
            raise ValueError('nonmonotonic time')
        last=s['time_s']
        if s['native_road_direction']=='north':
            if not isinstance(s.get('observed_left_curb_x'),(int,float)) or not isfinite(s['observed_left_curb_x']):
                raise ValueError('missing original approach curb')
            gap=min(p[0] for p in s['body_corners_xy'])-s['observed_left_curb_x']
            segment='approach'
        elif s['native_road_direction']=='west':
            if not isinstance(s.get('observed_left_curb_y'),(int,float)) or not isfinite(s['observed_left_curb_y']):
                raise ValueError('missing original departure curb')
            gap=min(p[1] for p in s['body_corners_xy'])-s['observed_left_curb_y']
            segment='departure'
        else:
            polyline=s.get('turn_left_edge_polyline_xy')
            if (not isinstance(polyline,list) or len(polyline)<2 or
                    any(not isinstance(p,list) or len(p)!=2 or
                        any(type(v) not in (int,float) or not isfinite(v) for v in p)
                        for p in polyline)):
                raise ValueError('missing surveyed turn curb polyline')
            def signed_gap(point):
                choices=[]
                for a,b in zip(polyline,polyline[1:]):
                    dx,dy=b[0]-a[0],b[1]-a[1]
                    length2=dx*dx+dy*dy
                    if length2<=1e-12:raise ValueError('degenerate turn curb polyline')
                    t=max(0.,min(1.,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length2))
                    px,py=a[0]+t*dx,a[1]+t*dy
                    distance=hypot(point[0]-px,point[1]-py)
                    cross=dx*(point[1]-py)-dy*(point[0]-px)
                    choices.append((distance,distance if cross<=0 else -distance))
                return min(choices)[1]
            gap=min(signed_gap(p) for p in s['body_corners_xy'])
            segment='turn'
        observed.append({'time_s':s['time_s'],'segment':segment,'left_body_to_curb_gap_m':gap,
                         'source':s['source']})
    if {'approach','turn','departure'}!={r['segment'] for r in observed}:
        raise ValueError('approach, turn and departure all required')
    return {'samples':observed,
            'minimum_approach_gap_m':min(r['left_body_to_curb_gap_m'] for r in observed if r['segment']=='approach'),
            'minimum_departure_gap_m':min(r['left_body_to_curb_gap_m'] for r in observed if r['segment']=='departure'),
            'minimum_turn_gap_m':min((r['left_body_to_curb_gap_m'] for r in observed if r['segment']=='turn'),default=None),
            'legal_practicability_judgment':'unresolved'}


def audit_comparison(a,b,declared):
    if not a.get('samples') or not b.get('samples'):
        raise ValueError('missing measured body history')
    for key in ('map_hash','curb_geometry_hash','road_directions','controller_policy_hash',
                'camera_plan_hash','duration_s'):
        if a.get(key) is None or a.get(key)!=b.get(key):
            raise ValueError('fixed condition differs: '+key)
    changed={key for key in ('approach_center_x','departure_center_y') if a.get(key)!=b.get(key)}
    if changed!=set(declared): raise ValueError('undeclared approach/departure difference')
    return {'fixed_conditions_checked':True,'legal_practicability_judgment':'unresolved'}
