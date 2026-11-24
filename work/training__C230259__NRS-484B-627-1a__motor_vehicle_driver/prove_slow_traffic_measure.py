"""Synthetic source-shaped positive and negative tests, not physical evidence."""
import hashlib
import json
from pathlib import Path
from slow_traffic_saved_measure import measure_original

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c230259-slow-traffic-fixtures'
SCRATCH.mkdir(parents=True,exist_ok=True)
CAMERAS=('overview','right_margin','following_traffic','lateral_position')


def fixture(name,right):
    folder=SCRATCH/name
    folder.mkdir(exist_ok=True)
    road=b'original Native OpenDRIVE surrogate for source-shaped CPU test'
    context={'assignment_id':HERE.name,'source_kind':'synthetic_native_sample',
             'map_source_sha256':hashlib.sha256(road).hexdigest(),
             'native_survey':{'lanes':[{'name':'forward','lane_id':-1},
                {'name':'opposing','lane_id':1},{'name':'right_paved_margin','lane_id':-2}]},
             'forward_lane_id':-1,'opposing_lane_id':1,'right_shoulder_lane_id':-2,
             'right_paved_edge_y_m':-6.5,'paved_width_m':10.0,
             'public_highway':None,'nrs_484b_630_applicability':None}
    trace=[]
    frames=[]
    for i in range(600):
        native=1000+i
        t=i/20
        x=-30+1.5*t
        y=-4.9 if right and i>=240 else -1.75
        fx=x-9
        cameras={name:native for name in CAMERAS}
        trace.append({'video_frame':i,'native_frame':native,'time_s':t,
                      'camera_native_frames':cameras,'ego_id':'subject-1','traffic_id':'follower-2',
                      'ego_road_id':'1','traffic_road_id':'1',
                      'ego_lane_id':-2 if right and i>=240 else -1,
                      'traffic_lane_id':-1,'ego_xy_m':[x,y],
                      'traffic_xy_m':[fx,-1.75],
                      'ego_footprint_xy_m':[[x-2,y-1],[x+2,y-1],[x+2,y+1],[x-2,y+1]],
                      'ego_speed_mps':1.5,'traffic_speed_mps':1.5,
                      'follower_command_mps':1.5 if i>=50 else 5,
                      'follower_free_flow_request_mps':5})
        frames.append({'video_frame':i,'native_frame':native,'time_s':t,
                       'camera_native_frames':cameras})
    sources=tuple(('\n'.join(json.dumps(r) for r in rows)+'\n').encode()
                  for rows in (trace,frames))+(json.dumps(context).encode(),road)
    return sources


def reject(sources,expected):
    try:
        measure_original(*sources)
    except ValueError as exc:
        assert expected in str(exc),str(exc)
        return str(exc)
    raise AssertionError('invalid source accepted')


def main():
    right=fixture('right',True)
    away=fixture('away',False)
    a=measure_original(*right)
    b=measure_original(*away)
    assert a['closest_right_body_edge_to_paved_edge_m']<b['closest_right_body_edge_to_paved_edge_m']
    assert a['follower_command_below_free_flow_frames']==b['follower_command_below_free_flow_frames']==550
    context=json.loads(right[2]);context['map_source_sha256']='0'*64
    bad_map=reject((right[0],right[1],json.dumps(context).encode(),right[3]),'OpenDRIVE source hash mismatch')
    bad_frame=reject((right[0].splitlines()[0]+b'\n',*right[1:]),'original 600-frame source missing')
    context=json.loads(right[2]);context['native_survey']['lanes'][1]['lane_id']=-1
    bad_lane=reject((right[0],right[1],json.dumps(context).encode(),right[3]),'one-lane-each-way Native survey missing')
    trace=[json.loads(line) for line in right[0].splitlines()]
    trace[10]['traffic_id']='subject-1'
    bad_identity=reject((('\n'.join(json.dumps(row) for row in trace)+'\n').encode(),*right[1:]),'participant identity changed')
    frames=[json.loads(line) for line in right[1].splitlines()]
    frames[10]['camera_native_frames'].pop('lateral_position')
    bad_camera=reject((right[0],('\n'.join(json.dumps(row) for row in frames)+'\n').encode(),*right[2:]),'four-camera original frame join missing')
    print(json.dumps({'passed':True,'fixture_kind':'synthetic_native_sample',
        'extreme_right_draft':a,'away_draft':b,'negative_map':bad_map,
        'negative_frame':bad_frame,'negative_lane':bad_lane,
        'negative_identity':bad_identity,'negative_camera':bad_camera,
        'measure_sha256':hashlib.sha256((HERE/'slow_traffic_saved_measure.py').read_bytes()).hexdigest()},sort_keys=True))


if __name__=='__main__':
    main()
