"""Source-bound bicycle/motorist effect diagnostic; intent remains unproven."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

FRAMES=480
RATE_HZ=20
CASES=('witness_1','witness_2')
INTERSECTION=(-7.,-7.,7.,7.)

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def bicycle_y(case:str,frame:int)->float:
    return (-25+.13*frame if frame<100 else -12. if frame<190 else -12+.13*(frame-190)) if case=='witness_1' else -25+.13*frame
def motor_x(case:str,frame:int)->float:
    return -25+.2*frame if case=='witness_1' else -25+.2*frame if frame<75 else -10. if frame<250 else -10+.2*(frame-250)
def bicycle_body(x:float,y:float)->list[list[float]]:
    return [[x-.35,y-.9],[x+.35,y-.9],[x+.35,y+.9],[x-.35,y+.9]]
def motor_body(x:float,y:float)->list[list[float]]:
    return [[x-2.5,y-1.1],[x+2.5,y-1.1],[x+2.5,y+1.1],[x-2.5,y+1.1]]
def bounds(body:list[list[float]])->tuple[float,float,float,float]:
    return min(p[0] for p in body),min(p[1] for p in body),max(p[0] for p in body),max(p[1] for p in body)
def overlaps(a:tuple[float,float,float,float],b:tuple[float,float,float,float])->bool:
    return a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]
def clearance(a:tuple[float,float,float,float],b:tuple[float,float,float,float])->float:
    dx=max(0.,a[0]-b[2],b[0]-a[2]);dy=max(0.,a[1]-b[3],b[1]-a[3])
    return math.hypot(dx,dy)

def synthetic(case:str,map_sha256:str)->dict:
    if case not in CASES or len(map_sha256)!=64:raise ValueError('Unknown case or map hash')
    rows=[]
    for frame in range(FRAMES):
        by=bicycle_y(case,frame);mx=motor_x(case,frame)
        rows.append({'frame':frame,'video_frame':frame,'native_frame':frame,'time_s':frame/RATE_HZ,
            'bicycle':{'actor_id':101,'class':'human_powered_bicycle','center_xy_m':[1.75,by],
                       'body_xy_m':bicycle_body(1.75,by),'speed_mps':0. if case=='witness_1' and 100<=frame<190 else 2.6},
            'motor_vehicle':{'actor_id':202,'class':'motor_vehicle','center_xy_m':[mx,-1.75],
                             'body_xy_m':motor_body(mx,-1.75),'speed_mps':0. if case=='witness_2' and 75<=frame<250 else 4.,
                             'brake_applied':case=='witness_2' and 75<=frame<250}})
    return {'format':'c111294-cycle-motor-source-v1','source_kind':'synthetic_cpu',
            'law_id':'NRS-484B-270-7a','cell_id':'C111294','actor':'cycle_or_scooter_operator',
            'case':case,'map_sha256':map_sha256,'rider_command_declared':
                'hold_before_motorist_crosses' if case=='witness_1' else 'enter_before_motorist_crosses',
            'intent_physically_verified':False,'legal_interference_claimed':False,'frames':rows}

def measure(source:Path,expected_sha256:str,road:Path)->dict:
    if not source.is_file():raise ValueError('Missing required source: interaction.json')
    if sha(source)!=expected_sha256:raise ValueError('Original interaction source missing or changed')
    data=json.loads(source.read_text())
    if data.get('format')!='c111294-cycle-motor-source-v1' or data.get('source_kind') not in (
            'synthetic_cpu','synthetic_original_shape_emulation','original_native_and_video'):
        raise ValueError('Wrong bicycle/motorist source format')
    if (data.get('law_id'),data.get('cell_id'),data.get('actor'))!=('NRS-484B-270-7a','C111294','cycle_or_scooter_operator'):
        raise ValueError('Frozen law/cell/actor source differs')
    if not road.is_file() or data.get('map_sha256')!=sha(road):raise ValueError('Authored road source differs')
    case=data.get('case')
    if case not in CASES or data.get('intent_physically_verified') is not False or data.get('legal_interference_claimed') is not False:
        raise ValueError('Case or intent claim differs')
    command='hold_before_motorist_crosses' if case=='witness_1' else 'enter_before_motorist_crosses'
    if data.get('rider_command_declared')!=command:raise ValueError('Rider command source differs')
    rows=data.get('frames')
    if not isinstance(rows,list) or len(rows)!=FRAMES:raise ValueError('Full 480-frame interaction source required')
    bike_cross=[];motor_cross=[];brake=[];minimum=math.inf
    prior=None;previous_native_frame=None
    original=data['source_kind'] in ('synthetic_original_shape_emulation','original_native_and_video')
    for index,row in enumerate(rows):
        native_frame=row.get('native_frame')
        native_ok=(type(native_frame) is int and native_frame>=0 and
                   (previous_native_frame is None or native_frame>previous_native_frame)) if original else native_frame==index
        if (row.get('frame'),row.get('video_frame'))!=(index,index) or not native_ok or abs(row.get('time_s',-1)-index/RATE_HZ)>1e-8:
            raise ValueError('Original frame/time join differs')
        previous_native_frame=native_frame
        bike=row.get('bicycle');motor=row.get('motor_vehicle')
        if not isinstance(bike,dict) or not isinstance(motor,dict) or bike.get('actor_id')==motor.get('actor_id'):
            raise ValueError('Separate source actors required')
        if bike.get('class')!=('bicycle_blueprint_unverified_propulsion' if original else 'human_powered_bicycle') or motor.get('class')!='motor_vehicle':
            raise ValueError('Bicycle/motorist class source differs')
        if original and (bike.get('blueprint_id')!='vehicle.bh.crossbike' or
                         not str(motor.get('blueprint_id','')).startswith('vehicle.')):
            raise ValueError('Original bicycle/motorist blueprint source differs')
        for actor,name,half in ((bike,'bicycle',bicycle_body),(motor,'motor',motor_body)):
            center=actor.get('center_xy_m');body=actor.get('body_xy_m');speed=actor.get('speed_mps')
            if not isinstance(center,list) or len(center)!=2 or not isinstance(body,list) or len(body)!=4 or type(speed) not in (int,float) or speed<0:
                raise ValueError('Original body/pose/speed absent: '+name)
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in center):raise ValueError('Original center invalid')
            if original:
                if any(not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) for p in body):
                    raise ValueError('Original body/pose differs: '+name)
                if len({tuple(round(v,4) for v in p) for p in body})!=4:
                    raise ValueError('Original body corners differ: '+name)
                box=bounds(body)
                if not (box[0]<=center[0]<=box[2] and box[1]<=center[1]<=box[3] and box[2]-box[0]>.1 and box[3]-box[1]>.1):
                    raise ValueError('Original body/pose differs: '+name)
            elif {tuple(round(v,4) for v in p) for p in body}!={tuple(round(v,4) for v in p) for p in half(*center)}:
                raise ValueError('Original body/pose differs: '+name)
        if prior and (math.dist(bike['center_xy_m'],prior[0])>.21 or math.dist(motor['center_xy_m'],prior[1])>.21):
            raise ValueError('Original actor path discontinuity')
        prior=(bike['center_xy_m'],motor['center_xy_m'])
        bb=bounds(bike['body_xy_m']);mb=bounds(motor['body_xy_m'])
        if overlaps(bb,INTERSECTION):bike_cross.append(index)
        if overlaps(mb,INTERSECTION):motor_cross.append(index)
        if motor.get('brake_applied') is True:brake.append(index)
        if overlaps(bb,INTERSECTION) or overlaps(mb,INTERSECTION):minimum=min(minimum,clearance(bb,mb))
    if not bike_cross or not motor_cross or not math.isfinite(minimum):raise ValueError('Interaction traversal source absent')
    if minimum<=0:raise ValueError('Actor bodies collide in source')
    if (case=='witness_1' and brake) or (case=='witness_2' and not brake):raise ValueError('Motorist response source differs')
    return {'format':'c111294-interaction-measurement-v1','case':case,
            'source_sha256':expected_sha256,'road_sha256':sha(road),'frames':FRAMES,
            'bicycle_intersection_first_frame':bike_cross[0],'motor_intersection_first_frame':motor_cross[0],
            'motor_braking_frames':len(brake),'minimum_actor_body_clearance_m':round(minimum,5),
            'motorist_braked':bool(brake),'bicycle_class_source_checked':True,
            'human_propulsion_physically_verified':False,
            'separate_motor_vehicle_source_checked':True,'rider_command_declared':command,
            'intent_physically_verified':False,'legal_interference_claimed':False,
            'physical_behavior_observed':data['source_kind']=='original_native_and_video'}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--sha256',required=True);p.add_argument('--road',type=Path,required=True)
    a=p.parse_args();print(json.dumps(measure(a.source,a.sha256,a.road),sort_keys=True))
