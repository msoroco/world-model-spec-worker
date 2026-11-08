"""Author paragraph (c)(1) unmarked-pavement boundary requests."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent.parent
ROOT=CASE.parents[1]
SOURCE='does not travel more than 200 feet in the section of pavement not marked as a traffic lane; or (2)'
BOUNDARY_M=60.96
POLICIES={'primary':(8.0,'standard',None),
          'fallback1':(7.0,'standard',None),
          'fallback2':(8.0,'elevated_overview',None),
          'fallback3':(8.0,'standard',45.0)}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def put_rows(path,values):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(v,sort_keys=True,allow_nan=False)+'\n'
                            for v in values))


def road():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE><header revMajor="1" revMinor="4" name="C146314 paragraph c1 authored unmarked pavement" version="1.00" date="2026-11-08" north="3.5" south="-7" east="300" west="0" vendor="worker"/>
<road name="driving line with unmarked right pavement" length="300" id="212" junction="-1">
<type s="0" type="town"><speed max="35" unit="mph"/></type>
<planView><geometry s="0" x="0" y="0" hdg="0" length="300"><line/></geometry></planView>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center>
<right><lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane>
<lane id="-2" type="shoulder" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="none" color="white" width="0"/></lane></right></laneSection></lanes>
<objects/><signals/></road></OpenDRIVE>
'''


def build():
    plan=json.loads((CASE/'case-plan.json').read_text())
    if SOURCE not in plan['source_law']['text']:
        raise ValueError('paragraph (c)(1) source differs')
    road_path=HERE/'unmarked-pass.xodr';road_path.write_text(road())
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    entries=[]
    for witness,distance in (('exception_3_1',61.06),('exception_3_2',BOUNDARY_M)):
        exit_x=20+distance
        for candidate,(speed,camera,stop) in POLICIES.items():
            target=HERE/'drafts'/witness/candidate
            case_id=CASE.name+'__'+witness
            values=[]
            for i in range(240):
                t=(i+1)/20;x=min(stop or 300,5+speed*t)
                blend=max(0,min(1,(x-15)/5,(exit_x+5-x)/5))
                y=-1.75-3.5*blend
                values.append({'frame':i,'time_s':t,
                    'source_kind':'authored_native_request',
                    'source_branch':'NRS 484B.210(1)(c)(1)',
                    'case_id':case_id,'candidate_id':candidate,
                    'road_id':212,'ego_x_m':round(x,6),
                    'ego_y_m':round(y,6),
                    'requested_surface':'unmarked_right_pavement' if blend>=.99 else 'driving_or_transition',
                    'lead_x_m':round(35+4*t,6),'lead_y_m':-1.75,
                    'unmarked_segment_start_x_m':20,
                    'unmarked_segment_end_x_m':round(exit_x,6),
                    'requested_excursion_m':distance,
                    'private_way_or_intersection_crossing_verified':False,
                    'unmarked_pavement_verified':False,
                    'pavement_unobstructed_verified':False,
                    'no_parked_vehicles_verified':False,
                    'actual_right_pass_observed':False,
                    'legal_verdict':None})
            track=target/'requested-tracks.jsonl';put_rows(track,values)
            cfg={'format':'c146314-paragraph-c1-request-v1',
                'assignment_id':CASE.name,'case_id':case_id,
                'candidate_id':candidate,'source_branch':'NRS 484B.210(1)(c)(1)',
                'assignment_sha256':sha(assignment),
                'case_plan_sha256':sha(CASE/'case-plan.json'),
                'road_sha256':sha(road_path),'tracks_sha256':sha(track),
                'rate_hz':20,'frames':240,
                'requested_ego_speed_mps':speed,'camera_policy':camera,
                'stop_x_m':stop,'unmarked_segment_start_x_m':20,
                'unmarked_segment_end_x_m':round(exit_x,6),
                'requested_excursion_m':distance,
                'requested_c1_within_200ft':distance<=BOUNDARY_M,
                'c2_crossing_verified':False,
                'unmarked_pavement_verified':False,
                'actual_excursion_observed':False,
                'actual_right_pass_observed':False,
                'original_native_observed':False,
                'status':'unselected_native_request'}
            put(target/'config.json',cfg)
            entries.append({'case_id':case_id,'candidate_id':candidate,
                'config_sha256':sha(target/'config.json'),
                'tracks_sha256':sha(track),'status':'unselected_native_request'})
    manifest={'format':'c146314-paragraph-c1-construction-v1',
        'assignment_id':CASE.name,'assignment_sha256':sha(assignment),
        'case_plan_sha256':sha(CASE/'case-plan.json'),
        'road_sha256':sha(road_path),
        'capture_sha256':sha(HERE/'capture.py'),
        'measurement_contract_sha256':sha(HERE/'measurement-contract.json'),
        'entries':entries,
        'original_native_observed':False,'delivery_ready':False}
    put(HERE/'manifest.json',manifest)
    return manifest


if __name__=='__main__':
    print(json.dumps({'requests':len(build()['entries'])}))
