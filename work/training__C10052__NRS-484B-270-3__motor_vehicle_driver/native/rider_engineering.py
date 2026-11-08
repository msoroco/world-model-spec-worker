"""C10052 rider-yield route and candidate control geometry for CPU preflight."""
import math
from alley_geometry import route
from geometry import body
from measure_facility import overlap_area

CONFLICT_BOUNDS_M=(-2.5,-5.0,2.5,-3.0)
RIDER_Y_M=-4.0
HOLD_ROUTE_INDEX=360
ROUTE_STEP_PER_FRAME=4
RELEASE_FRAME={'clear':249,'conflict':174}


def rider_body(x):
    return [[x-1.0,RIDER_Y_M-.35],[x-1.0,RIDER_Y_M+.35],
            [x+1.0,RIDER_Y_M+.35],[x+1.0,RIDER_Y_M-.35]]


def ego_route_index(frame,response,start_x=-45.0,release_shift_frames=0):
    if response not in RELEASE_FRAME or type(frame) is not int or frame<0:
        raise ValueError('Unknown rider response/frame')
    if start_x not in (-45.0,-55.0) or type(release_shift_frames) is not int or not 0<=release_shift_frames<=5:
        raise ValueError('Unknown rider candidate controls')
    path=route(start_x)
    hold=round((-9.0-start_x)/.1)
    approach=min(hold,frame*ROUTE_STEP_PER_FRAME)
    progress=max(0,frame-RELEASE_FRAME[response]-release_shift_frames)*ROUTE_STEP_PER_FRAME
    return min(len(path)-2,approach+progress)


def ego_pose(frame,response,start_x=-45.0,release_shift_frames=0):
    path=route(start_x)
    index=ego_route_index(frame,response,start_x,release_shift_frames)
    x,y=path[index]
    nx,ny=path[index+1]
    distance=math.hypot(nx-x,ny-y)
    heading=((nx-x)/distance,(ny-y)/distance)
    return {'center_xy':[x,y],'body_xy':body(x,y,heading),
            'forward_xy':list(heading),'route_index':index,
            'road_id':2 if y < -5 else 1,
            'speed_mps':8.0 if (frame<round((-9.0-start_x)/.4) or
                                 frame>RELEASE_FRAME[response]+release_shift_frames) and
                                 index<len(path)-2 else 0.0}


def rider_pose(frame):
    if type(frame) is not int or frame<0:
        raise ValueError('Invalid rider frame')
    x=-20+.2*max(0,min(frame-100,200))
    return {'center_xy':[x,RIDER_Y_M],'body_xy':rider_body(x),
            'speed_mps':4.0 if 100<frame<=300 else 0.0,
            'road_id':1,'lane_id':-2}


def check():
    path=route()
    assert path[0]==(-45.0,-1.5) and path[-1]==(0.0,-12.0)
    assert path[HOLD_ROUTE_INDEX]==(-9.0,-1.5)
    result={}
    for response in RELEASE_FRAME:
        occupied=[i for i in range(480)
                  if overlap_area(ego_pose(i,response)['body_xy'],CONFLICT_BOUNDS_M)>.01]
        result[response]={'first_conflict_index':occupied[0],
                          'last_conflict_index':occupied[-1],
                          'held_at_route_index':ego_route_index(120,response)}
        assert occupied[0]==(262 if response=='clear' else 187)
        assert ego_route_index(120,response)==HOLD_ROUTE_INDEX
        assert ego_pose(479,response)['road_id']==2
        assert ego_route_index(120,response,-55.0)==460
        assert ego_pose(0,response,-55.0)['center_xy']==[-55.0,-1.5]
        assert ego_pose(479,response,-55.0)['road_id']==2
        assert ego_route_index(480,response,-45.0,5)>500
    rider=[i for i in range(480) if overlap_area(rider_pose(i)['body_xy'],CONFLICT_BOUNDS_M)>.01]
    assert rider[0]==183 and rider[-1]==217
    return {'route_points':len(path),'rider_conflict_indices':[rider[0],rider[-1]],
            'ego':result,'native_readback_verified':False,'physical_success_claimed':False}


if __name__=='__main__':
    import json
    print(json.dumps(check(),indent=2))
