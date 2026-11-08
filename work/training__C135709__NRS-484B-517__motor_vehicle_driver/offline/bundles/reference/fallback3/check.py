"""Check exact frozen C135709 request sources and authored stand trajectories."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def check(bundle):
    bundle=Path(bundle)
    cfg=json.loads((bundle/'config.json').read_text())
    assignment=json.loads((bundle/'assignment-source.json').read_text())
    plan=json.loads((bundle/'case-plan.json').read_text())
    track=bundle/'requested-tracks.jsonl';road=bundle/'stand-road.xodr'
    witness=cfg.get('case_id','').removeprefix(cfg.get('assignment_id','')+'__')
    candidate=cfg.get('candidate_id')
    if (cfg.get('assignment_id')!='training__C135709__NRS-484B-517__motor_vehicle_driver' or
        cfg.get('law_id')!='NRS-484B-517' or cfg.get('cell_id')!='C135709' or
        cfg.get('actor')!='motor_vehicle_driver' or
        cfg.get('case_id')!=cfg['assignment_id']+'__'+witness or
        witness not in ('reference','contrast') or
        candidate not in ('primary','fallback1','fallback2','fallback3') or
        cfg.get('frames')!=240 or cfg.get('rate_hz')!=20 or
        cfg.get('assignment_sha256')!=sha(bundle/'assignment-source.json') or
        cfg.get('case_plan_sha256')!=sha(bundle/'case-plan.json') or
        cfg.get('tracks_sha256')!=sha(track) or cfg.get('road_sha256')!=sha(road) or
        cfg.get('original_native_observed') is not False or
        cfg.get('status')!='unselected_native_request'):
        raise ValueError('C135709 source/config mismatch')
    law=assignment.get('law_record',{})
    if (assignment.get('assignment_id')!=cfg['assignment_id'] or
        law.get('id')!='NRS-484B-517' or
        'taxicab in a taxicab stand' not in law.get('text','') or
        'expeditiously loading or unloading of passengers' not in law.get('text','') or
        len(assignment.get('local_snapshot',{}).get('memberships',{}).get('full-train',[]))!=0 or
        plan.get('assignment_id')!=cfg['assignment_id'] or
        plan.get('scope_branches')!=['Non-taxicab parking in a taxicab stand'] or
        len(plan.get('cases',[]))!=2):
        raise ValueError('C135709 frozen legal scope differs')
    root=ET.parse(road).getroot();roads=root.findall('road')
    if len(roads)!=1 or roads[0].get('id')!='517' or roads[0].get('length')!='120':
        raise ValueError('C135709 road geometry differs')
    lanes={int(x.get('id')):x.get('type') for x in roads[0].findall('./lanes/laneSection/right/lane')}
    objects={x.get('id'):x for x in roads[0].findall('./objects/object')}
    if (lanes!={-1:'driving',-2:'parking'} or set(objects)!={'1','2'} or
        objects['1'].get('name')!='TAXICAB STAND authored sign' or
        objects['2'].get('type')!='parkingSpace'):
        raise ValueError('C135709 stand/sign request differs')
    expected_camera='elevated_overview' if candidate=='fallback2' else 'standard'
    expected_motion='slow_approach' if candidate=='fallback1' else 'stop_before_stand' if candidate=='fallback3' else 'normal_approach'
    if (cfg.get('camera_policy')!=expected_camera or cfg.get('motion_policy')!=expected_motion or
        cfg.get('approach_frames')!=(200 if candidate=='fallback1' else 100) or
        cfg.get('target_x_m')!=(40 if candidate=='fallback3' else 60) or
        cfg.get('requested_stand_occupancy')!=(witness=='contrast' and candidate!='fallback3')):
        raise ValueError('C135709 candidate policy differs')
    data=rows(track)
    if len(data)!=240:raise ValueError('C135709 request length differs')
    occupied=0;parked=0;prior=(10,-1.75)
    for i,row in enumerate(data):
        fraction=min(1,(i+1)/cfg['approach_frames'])
        x=10+(cfg['target_x_m']-10)*fraction
        y=(-1.75-4.75*min(1,max(0,(fraction-.65)/.35))
            if witness=='contrast' and candidate!='fallback3' else -1.75)
        phase=('prestand' if candidate=='fallback3' else 'approach') if fraction<1 else ('hold_before_stand' if candidate=='fallback3' else 'parked')
        speed=20*math.hypot(x-prior[0],y-prior[1]);prior=(x,y)
        occupancy=witness=='contrast' and candidate!='fallback3' and phase=='parked'
        if (row.get('frame')!=i or row.get('time_s')!=(i+1)/20 or
            row.get('witness')!=witness or row.get('candidate_id')!=candidate or
            row.get('road_id')!=517 or row.get('lane_id')!=(-2 if y<-3.5 else -1) or
            abs(row.get('ego_x_m',float('nan'))-x)>1e-5 or
            abs(row.get('ego_y_m',float('nan'))-y)>1e-5 or
            row.get('ego_heading_deg')!=0 or
            abs(row.get('ego_speed_mps',float('nan'))-speed)>1e-5 or
            row.get('phase')!=phase or
            row.get('stand_polygon_occupied_requested') is not occupancy or
            any(row.get(k) is not False for k in
                ('official_designation_verified','sign_appropriateness_verified',
                 'non_taxicab_actual_use_verified','passenger_loading_exception_verified',
                 'actual_parking_observed'))):
            raise ValueError(f'C135709 request row differs at {i}')
        occupied+=occupancy;parked+=phase=='parked'
    return {'case_id':cfg['case_id'],'candidate_id':candidate,'frames':240,
        'requested_occupied_frames':occupied,'requested_parked_frames':parked,
        'original_native_observed':False,'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    print(json.dumps(check(p.parse_args().bundle)))
