"""Authored exit-side pair for NRS 484B.400(2)(b) at the frozen C329610 cell.

The source map is copied from the neighboring (2)(a) draft. The wrong-side
endpoint is deliberately in an opposing lane; Native path control and actual
clearance remain unverified. No legal verdict follows from the requested path.
"""
import math
from shapely.geometry import Point,Polygon,box
from shapely.ops import unary_union
from base_geometry import open_drive

EXIT_X_M={'witness_1':1.75,'witness_2':-1.75}


def route(exit_x_m,turn_entry_x_m=-7):
    if exit_x_m not in EXIT_X_M.values():raise ValueError('Unknown controlled exit side')
    if turn_entry_x_m not in (-7,-10):raise ValueError('Unknown turn entry station')
    approach_steps=round((turn_entry_x_m+50)/.1)
    points=[[-50+i*.1,-1.75] for i in range(approach_steps+1)]
    p0=(turn_entry_x_m,-1.75);p1=(turn_entry_x_m+4,-1.75);p2=(exit_x_m,0);p3=(exit_x_m,7)
    for i in range(1,151):
        t=i/150
        points.append([(1-t)**3*p0[j]+3*(1-t)**2*t*p1[j]+3*(1-t)*t*t*p2[j]+t**3*p3[j]
                       for j in (0,1)])
    points.extend([[exit_x_m,7+i*.1] for i in range(1,431)])
    return points


def check():
    surface=unary_union((box(-100,-7,100,7),box(-7,-100,7,100)))
    results={}
    for suffix,x in EXIT_X_M.items():
        points=route(x)
        assert all(abs(y+1.75)<1e-9 for px,y in points if px<=-7)
        assert all(surface.covers(Point(p)) for p in points)
        gaps=[math.dist(a,b) for a,b in zip(points,points[1:])]
        assert gaps and max(gaps)<.3
        for a,b in zip(points,points[1:]):
            angle=math.atan2(b[1]-a[1],b[0]-a[0]);c=math.cos(angle);s=math.sin(angle)
            body=Polygon([(a[0]+c*u-s*v,a[1]+s*u+c*v) for u,v in
                          ((-2.6,-1.1),(-2.6,1.1),(2.6,1.1),(2.6,-1.1))])
            assert surface.covers(body),'Prospective body leaves authored pavement'
        results[suffix]={'requested_exit_x_m':x,'route_points':len(points),
                         'maximum_sample_gap_m':max(gaps),
                         'destination_side':'right_of_centerline' if x>0 else 'left_of_centerline'}
    assert results['witness_1']['requested_exit_x_m']!=results['witness_2']['requested_exit_x_m']
    return {'passed':True,'map_from':'same frozen C329610 two-way intersection as (2)(a) draft',
            'authored_approach_y_m':-1.75,'destination_centerline_x_m':0,
            'cases':results,'native_verified':False,
            'opposing_lane_path_accepted':False,'legal_outcome_claimed':False}


if __name__=='__main__':
    import json
    print(json.dumps(check()))
