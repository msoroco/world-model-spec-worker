"""Build one bounded text diagnostic recipe from retained U-turn source frames."""
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
CASE=sys.argv[1] if len(sys.argv)>1 else 'reference'
if CASE not in ('reference','contrast','divided_reference','divided_opening'):
    raise ValueError('Unknown authored case')
CANDIDATE=sys.argv[2] if len(sys.argv)>2 else 'primary'
if CANDIDATE not in ('primary','fallback1','fallback2','fallback3'):
    raise ValueError('Unknown authored candidate')
SELECTED=len(sys.argv)>3 and sys.argv[3]=='selected'
if len(sys.argv)>3 and not SELECTED:
    raise ValueError('Unknown recipe scope')
LABEL=CASE if CANDIDATE=='primary' else CASE+'-'+CANDIDATE
SOURCE=(ROOT/'native/selected-diagnostic'/CASE/CANDIDATE/'raw.json' if SELECTED else
        ROOT/'native'/('divided-opening' if CASE.startswith('divided_') else '')/'synthetic'/CASE/CANDIDATE/'raw.json')
PREFIX='selected' if SELECTED else 'current'
SPEC=ROOT/f'update015-{PREFIX}-{LABEL}-diagnostic.json'
RECIPE=ROOT/f'update015-{PREFIX}-{LABEL}-recipe.json'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(rows):return ''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n' for row in rows)


def build():
    source=json.loads(SOURCE.read_text())
    trace=[];mapping=[];evidence=[];frames=[];graphs=[]
    for row in source['rows']:
        index,time=row['frame'],row['time_s']
        ego=row['ego'];xyz=ego['center_xyz_m'];velocity=ego['velocity_xyz_mps']
        body=ego['body_xyz_m'];heading=ego['heading_rad']*180/math.pi
        observation={'frame':index,'time_s':time,'participants':[{
            'actor_id':ego['actor_id'],'blueprint':ego['blueprint'],
            'body_vertices_m':body,'heading_deg':heading,'velocity_mps':velocity,
            'speed_mps':ego['speed_mps'],'accel_longitudinal_mps2':0.0}],
            'world_settings':{'no_rendering_mode':False},
            'rgb_sensors':{'overview':{'frame':index}}}
        trace.append({'frame':index,'time_s':time,'position':dict(zip(('x','y','z'),xyz)),
                      'position_m':xyz,'heading_deg':heading,'speed_mps':ego['speed_mps'],
                      'speed_mph':ego['speed_mps']*2.2369362921,'velocity_mps':velocity,
                      'control':{'throttle':0.0,'brake':0.0,'hand_brake':False}})
        mapping.append({'carla_frame':index,'native_frame':index,
                        'synthetic_frame_only':True,'time_s':time,'video_frame':index})
        evidence.append({'original_frame':index,'replay_frame':index,'actor_id':ego['actor_id'],
                         'recording_time_s':time,'replay_simulation_time_s':time,
                         'ego':{'position_m':xyz,'heading_deg':heading,'speed_mps':ego['speed_mps'],
                                'speed_provenance':'synthetic_native_sample','body_vertices_m':body},
                         'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                                  'road_projection':{'road_id':1,'section_id':0,'lane_id':-1,'s_m':max(0.0,xyz[0]+100)}},
                         'original_observations':observation})
        frames.append({'frame':index,'time_s':time,'simulation_time':time,
                       'base':f'graphs/base/{index:08d}.pkl'})
        graphs.append({'path':f'capture/native/graphs/base/{index:08d}.pkl',
                       'attributes':{'frame':index,'observed_evidence':observation},
                       'nodes':[],'edges':[]})
    files={'trace.jsonl':lines(trace),'video_frames.jsonl':lines(mapping),
           'capture/evidence.jsonl':lines(evidence),
           'capture/native/frames.jsonl':lines(frames),
           'capture/recorder_info.txt':'Create 10: vehicle.tesla.model3\n',
           'acquisition-provenance.json':json.dumps({'provenance_kind':'synthetic_fixture',
                                                      'diagnostic_fixture':True,
                                                      'native_executed':False})+'\n'}
    files['capture/manifest.json']=json.dumps({'extraction_confirmed':True,'frames':800,
        'acquisition':'synthetic_cpu_fixture','observation_contract_version':2,
        'required_observations':(['kin.position','kin.heading','rel.occupies'] if CASE.startswith('divided_')
                                 else ['kin.position','kin.heading','st.intersection','rel.occupies']),
        'sources':{'road.xodr':sha(ROOT/'native'/('divided-opening' if CASE.startswith('divided_') else '')/'drafts'/CASE/CANDIDATE/('divided-highway.xodr' if CASE.startswith('divided_') else 'district-crossroads.xodr')),
                   'trace.jsonl':hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()}},indent=2)+'\n'
    videos=[{'path':name+'.mkv','frames':800,'width':width,'height':height,
             'fps':20,'color':color} for name,width,height,color in (
                 ('overview',1920,1080,'blue'),('approach',1280,720,'green'),
                 ('reference_corner',1280,720,'white'),('driver_reference',1280,720,'red'))]
    SPEC.write_text(json.dumps({'files':files,'graphs':graphs,'videos':videos},separators=(',',':'))+'\n')
    rel_spec=SPEC.relative_to(REPO).as_posix()
    rel_source=SOURCE.relative_to(REPO).as_posix()
    RECIPE.write_text(json.dumps({'format':'worker-fixture-recipe','sources':[
        {'path':'diagnostic-input.json','source':rel_spec,'sha256':sha(SPEC)},
        {'path':'raw.json','source':rel_source,'sha256':sha(SOURCE)}],
        'generator':{'source':rel_spec,'sha256':sha(SPEC)}},indent=2)+'\n')
    if SPEC.stat().st_size>2*1024*1024:raise ValueError('Diagnostic text exceeds return file cap')
    print(json.dumps({'frames':800,'spec_bytes':SPEC.stat().st_size,'recipe_sha256':sha(RECIPE)}))


if __name__=='__main__':build()
