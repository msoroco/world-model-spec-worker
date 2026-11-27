"""Generate source-shaped software fixtures for eight selected arrow cases.

The generic adapter/media skeleton is reused only for CPU conversion testing.
Every signal, motion, participant and case-specific map row is generated here;
none represents original Native evidence or physical acceptance.
"""

import hashlib
import json
import math
import os
from pathlib import Path

from build_config import AID
from controller import SUFFIXES

ROOT=Path(__file__).resolve().parent.parent
SCRATCH=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
TEMPLATE=Path('work/training__C132924__NRS-484B-627-1b__motor_vehicle_driver/selected-generator-probe_a.json')
INTERSECTION_MAP=Path('work/training__C111334__NRS-484B-307-4b__pedestrian/native/road.xodr')


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path,obj):
    SCRATCH.mkdir(parents=True,exist_ok=True)
    stage=SCRATCH/('c111603-'+path.parent.name+'-'+path.name+'.stage')
    stage.write_text(json.dumps(obj,separators=(',',':'),ensure_ascii=False)+'\n')
    os.replace(stage,path)


def line_rows(text):
    return [json.loads(line) for line in text.splitlines()]


def serial(rows):
    return ''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n' for row in rows)


def ego_x(i,suffix):
    if suffix=='pedestrian_yield' and i>=245:
        return 4.5 if i<=295 else 4.5+(i-295)*0.1
    if suffix=='traffic_yield' and i>=295:
        return 9.5 if i<=345 else 9.5+(i-345)*0.1
    return (i-200)*0.1


def profile(i,suffix):
    x=ego_x(i,suffix)
    turn_sign=-1 if suffix=='direction_contrary' else 1
    y=turn_sign*max(0,x-2)*0.5
    heading=turn_sign*math.degrees(math.atan2(0.5,1)) if x>2 else 0.0
    speed=0 if ((suffix=='pedestrian_yield' and 245<=i<=295)
                or (suffix=='traffic_yield' and 295<=i<=345)) else 2.0
    lit=100<=i<=500 and not (suffix=='arrow_expired' and i>=200)
    ped_here=suffix in ('pedestrian_yield','pedestrian_overlap') and 250<=i<=290
    other_here=suffix in ('traffic_yield','traffic_overlap') and 300<=i<=340
    return x,y,heading,speed,lit,ped_here,other_here


def actor(actor_id,role,x,y,heading,speed):
    return {'actor_id':actor_id,'type_id':'walker.pedestrian.0001' if role=='pedestrian'
            else 'vehicle.tesla.model3','x_m':x,'y_m':y,'z_m':1.0,
            'yaw_deg':heading,'speed_mps':speed,
            'body_vertices_native_m':[[x-0.1,y-0.1,0.0],[x+0.1,y+0.1,0.0],
                                      [x-0.1,y-0.1,1.5],[x+0.1,y+0.1,1.5]]}


def build_one(suffix,template):
    case_id=AID+'__'+suffix
    source_dir=ROOT/'selected-source'/suffix
    source_dir.mkdir(parents=True,exist_ok=True)
    context={'case_id':case_id,'source_kind':'generated_software_diagnostic',
        'arrow_direction':'left','intersection_bounds_m':[0,20,-8,8],
        'adjacent_crosswalk_bounds_m':[8,12,-8,8],
        'arrow_facing_source':'synthetic_fixture_not_original_pixels',
        'physical_signal_governance_verified':False,
        'participant_lawfulness_verified':False}
    context_path=source_dir/'intersection-context.json'
    atomic(context_path,context)
    road=INTERSECTION_MAP.read_text().replace('C111334','C111603')
    files={key:value for key,value in template['files'].items()
           if key not in ('native.jsonl','road.xodr')}
    files['road.xodr']=road
    native=[];signals=[];motions=[]
    trace=line_rows(files['trace.jsonl'])
    evidence=line_rows(files['capture/evidence.jsonl'])
    for i in range(600):
        x,y,heading,speed,lit,ped_here,other_here=profile(i,suffix)
        ped_xy=(10.0,0.0) if ped_here else (50.0,50.0)
        other_xy=(5.0,0.0) if other_here else (50.0,50.0)
        actors={'ego':actor(101,'ego',x,y,heading,speed),
                'pedestrian':actor(102,'pedestrian',*ped_xy,0.0,1.0 if ped_here else 0.0),
                'other_traffic':actor(103,'other',*other_xy,0.0,2.0 if other_here else 0.0)}
        native.append({'source_kind':'generated_software_diagnostic',
            'native_frame':2000+i,'time_s':i/20,'actors':actors,
            'signal':{'opendrive_id':'201','native_actor_id':201,
                      'raw_state':'green' if lit else 'red',
                      'green_turn_arrow_alone_verified':False},
            'requested_phase':suffix,'legal_verdict':None})
        signals.append({'native_frame':2000+i,'time_s':i/20,
                        'green_arrow_alone':lit,'illuminated':lit,
                        'synthetic_diagnostic':True})
        motions.append({'native_frame':2000+i,'time_s':i/20,
            'ego_xy_m':[x,y],'pedestrian_xy_m':list(ped_xy),
            'other_traffic_xy_m':list(other_xy),
            'ego_speed_mps':speed,
            'ego_heading_xy':[math.cos(math.radians(heading)),
                              math.sin(math.radians(heading))],
            'synthetic_diagnostic':True})
        trace[i].update(position={'x':x,'y':y,'z':1.0},position_m=[x,y,1.0],
                        heading_deg=heading,speed_mps=speed,
                        speed_mph=speed*2.2369362921,
                        velocity_mps=[speed*math.cos(math.radians(heading)),
                                      speed*math.sin(math.radians(heading)),0.0],
                        speed_provenance='synthetic_native_sample')
        evidence[i]['ego'].update(position_m=[x,y,1.0],heading_deg=heading,
            speed_mps=speed,speed_provenance='synthetic_native_sample')
    files['native.jsonl']=serial(native)
    files['signal_frames.jsonl']=serial(signals)
    files['motion_frames.jsonl']=serial(motions)
    files['trace.jsonl']=serial(trace)
    files['capture/evidence.jsonl']=serial(evidence)
    capture_manifest=json.loads(files['capture/manifest.json'])
    capture_manifest['sources']={
        'trace.jsonl':sha_bytes(files['trace.jsonl'].encode()),
        'intersection-context.json':sha_bytes(context_path.read_bytes()),
        'road.xodr':sha_bytes(road.encode())}
    files['capture/manifest.json']=json.dumps(capture_manifest,indent=2)+'\n'
    spec={'files':files,'graphs':template['graphs'],'videos':template['videos']}
    spec_path=ROOT/('selected-generator-'+suffix+'.json')
    atomic(spec_path,spec)
    recipe={'format':'worker-fixture-recipe','sources':[{
        'path':'intersection-context.json',
        'source':str(context_path.relative_to(Path.cwd())),
        'sha256':sha_bytes(context_path.read_bytes())}],
        'generator':{'source':str(spec_path.relative_to(Path.cwd())),
                     'sha256':sha_bytes(spec_path.read_bytes())}}
    recipe_path=ROOT/('selected-recipe-'+suffix+'.json')
    atomic(recipe_path,recipe)
    return {'case_id':case_id,'generator_bytes':spec_path.stat().st_size,
            'generator_sha256':sha_bytes(spec_path.read_bytes()),
            'recipe_sha256':sha_bytes(recipe_path.read_bytes())}


def main():
    template=json.loads(TEMPLATE.read_text())
    rows=[build_one(suffix,template) for suffix in SUFFIXES]
    if any(row['generator_bytes']>2*1024*1024 for row in rows):
        raise ValueError('Returned diagnostic generator exceeds 2 MiB')
    print(json.dumps({'selected_cases':len(rows),'max_generator_bytes':max(
        row['generator_bytes'] for row in rows)}))


if __name__=='__main__':
    main()
