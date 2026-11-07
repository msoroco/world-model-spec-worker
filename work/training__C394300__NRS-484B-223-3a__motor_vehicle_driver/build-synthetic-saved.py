"""Build 480-frame CPU-only saved movement fixtures for the 3(a) pair."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(FOLDER/'native'))
from geometry import route
from measure_saved import LAW_TEXT_SHA256,measure


def _body(points,index):
    x,y=points[index];a=points[max(0,index-1)];b=points[min(len(points)-1,index+1)]
    dx=b[0]-a[0];dy=-(b[1]-a[1]);norm=math.hypot(dx,dy)
    ux,uy=dx/norm,dy/norm
    return [[round(x+ux*s-uy*t,5),round(-y+uy*s+ux*t,5)]
            for s,t in ((-2.2,-1),(-2.2,1),(2.2,1),(2.2,-1))]


def _lane(case,index,x,y):
    if case=='controlled_1':
        if index<=850:return 1,-1 if y> -1.75 else -2
        if index<=1000:return 13,-1
        return 4,-1
    if index<=850:return 1,-1 if y> -1.75 else -2
    if index<=860:return 14,-1
    if index<=1350:return 2,-2 if y< -1.75 else -1
    if index<=1500:return 23,-1
    return 24,-1


def build():
    root=FOLDER/'synthetic-local';root.mkdir(exist_ok=True)
    outputs=[]
    for case in ('controlled_1','controlled_2'):
        destination=root/case;destination.mkdir(exist_ok=True)
        shutil.copyfile(FOLDER/'draft-construction/scene.xodr',destination/'scene.xodr')
        map_sha=hashlib.sha256((destination/'scene.xodr').read_bytes()).hexdigest()
        survey={'source_kind':'synthetic_cpu','authored_map_sha256':map_sha,
                'native_lane_types_verified':True,'native_lane_types_observed_in_carla':False,
                'mocked_lane_ids':{'center':[1,14,2,-1],'through':[2,-2]}}
        (destination/'road_geometry.json').write_text(json.dumps(survey,indent=2)+'\n')
        declaration=('left_turn_from_center_at_first_opportunity' if case=='controlled_1'
                     else 'through_travel_then_later_left_from_through_lane')
        purpose={'source_kind':'synthetic_cpu','case':case,'law_text_sha256':LAW_TEXT_SHA256,
                 'declaration':declaration,'observed_driver_intent':False}
        (destination/'declared_purpose.json').write_text(json.dumps(purpose,indent=2)+'\n')
        path=route(case)
        samples=[]
        for frame in range(480):
            index=round(frame*(len(path)-1)/479)
            x,y=path[index];road,lane=_lane(case,index,x,y)
            samples.append({'native_frame':frame,'time_s':round(frame*.05,5),
                            'source_kind':'synthetic_cpu','native_center_xy_m':[x,-y],
                            'native_body_xy_m':_body(path,index),
                            'native_road_id':road,'native_lane_id':lane})
        (destination/'native_samples.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in samples))
        report=measure(destination)
        (destination/'analysis-report.json').write_text(json.dumps(report,indent=2)+'\n')
        outputs.append({'case':case,'frames':len(samples),
                        'movement_observed_in_synthetic_rows':report['requested_movement_observed_in_saved_rows'],
                        'center_full_body_frames':report['measured']['center_full_body_frames']})
    return outputs


if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
