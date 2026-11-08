"""Author unselected C135709 road, curb stand and two-witness parking requests."""
import hashlib
import json
import math
from pathlib import Path

CASE=Path(__file__).resolve().parents[1]
ROOT=CASE.parents[1]
NATIVE=CASE/'native'
ASSIGNMENT='training__C135709__NRS-484B-517__motor_vehicle_driver'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def write_rows(path,items):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(x,allow_nan=False)+'\n' for x in items))

def road():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="C135709 authored taxicab stand request" version="1.00" date="2026-11-08" north="10" south="-10" east="120" west="0" vendor="worker"/>
  <road name="narrow road with curb stand request" length="120" id="517" junction="-1">
    <planView><geometry s="0" x="0" y="0" hdg="0" length="120"><line/></geometry></planView>
    <elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>
    <lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" width="0.15" color="yellow"/></lane></center>
      <right><lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" width="0.15" color="white"/></lane>
      <lane id="-2" type="parking" level="false"><width sOffset="0" a="4.75" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" width="0.15" color="white"/></lane></right></laneSection></lanes>
    <objects><object id="1" name="TAXICAB STAND authored sign" type="sign" s="50" t="-8.3" zOffset="2" hdg="3.14159265359" pitch="0" roll="0" orientation="+" length="0.1" width="0.9" height="0.6"/>
    <object id="2" name="authored curb stand polygon marker" type="parkingSpace" s="62.5" t="-5.875" zOffset="0" hdg="0" pitch="0" roll="0" orientation="none" length="25" width="4.75" height="0.02"/></objects>
  </road>
</OpenDRIVE>
'''

def build():
    NATIVE.mkdir(parents=True,exist_ok=True)
    roadpath=NATIVE/'stand-road.xodr';roadpath.write_text(road())
    src=ROOT/'inputs'/ASSIGNMENT/'assignment.json'
    plan=CASE/'case-plan.json'
    entries=[]
    for witness in ('reference','contrast'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            slow=candidate=='fallback1';stop=candidate=='fallback3'
            approach=200 if slow else 100
            target=40 if stop else 60
            start=10
            tracks=[];prior=None
            for i in range(240):
                fraction=min(1,(i+1)/approach)
                x=start+(target-start)*fraction
                if witness=='contrast' and not stop:
                    lateral=min(1,max(0,(fraction-.65)/.35))
                    y=-1.75-4.75*lateral
                else:y=-1.75
                if prior is None: speed=math.hypot(x-start,y+1.75)*20
                else:speed=math.hypot(x-prior[0],y-prior[1])*20
                phase=('prestand' if stop else 'approach') if fraction<1 else ('hold_before_stand' if stop else 'parked')
                tracks.append({'frame':i,'time_s':(i+1)/20,'witness':witness,
                    'candidate_id':candidate,'road_id':517,
                    'lane_id':-2 if y < -3.5 else -1,
                    'ego_x_m':round(x,6),'ego_y_m':round(y,6),
                    'ego_heading_deg':0,'ego_speed_mps':round(speed,6),
                    'phase':phase,'stand_polygon_occupied_requested':
                        witness=='contrast' and not stop and phase=='parked',
                    'official_designation_verified':False,
                    'sign_appropriateness_verified':False,
                    'non_taxicab_actual_use_verified':False,
                    'passenger_loading_exception_verified':False,
                    'actual_parking_observed':False})
                prior=(x,y)
            target_dir=NATIVE/'drafts'/witness/candidate
            track=target_dir/'requested-tracks.jsonl';write_rows(track,tracks)
            cfg={'format':'c135709-stand-request-v1','assignment_id':ASSIGNMENT,
                'case_id':ASSIGNMENT+'__'+witness,'candidate_id':candidate,
                'law_id':'NRS-484B-517','cell_id':'C135709',
                'actor':'motor_vehicle_driver','rate_hz':20,'frames':240,
                'road_sha256':sha(roadpath),'tracks_sha256':sha(track),
                'assignment_sha256':sha(src),'case_plan_sha256':sha(plan),
                'requested_stand_occupancy':witness=='contrast' and not stop,
                'requested_vehicle_class':'non_taxicab_passenger_vehicle',
                'camera_policy':'elevated_overview' if candidate=='fallback2' else 'standard',
                'motion_policy':'slow_approach' if slow else 'stop_before_stand' if stop else 'normal_approach',
                'approach_frames':approach,'target_x_m':target,
                'original_native_observed':False,'status':'unselected_native_request'}
            write(target_dir/'config.json',cfg)
            entries.append({'case_id':cfg['case_id'],'candidate_id':candidate,
                'config_sha256':sha(target_dir/'config.json'),
                'tracks_sha256':sha(track),'requested_parked_frames':
                    sum(x['stand_polygon_occupied_requested'] for x in tracks),
                'status':'unselected_native_request'})
    manifest={'format':'c135709-stand-construction-v1',
        'assignment_id':ASSIGNMENT,'assignment_sha256':sha(src),
        'case_plan_sha256':sha(plan),'road_sha256':sha(roadpath),
        'entries':entries,'original_native_observed':False,'delivery_ready':False}
    write(NATIVE/'manifest.json',manifest)
    return manifest

if __name__=='__main__':print(json.dumps({'requests':len(build()['entries'])}))
