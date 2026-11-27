"""Inventoried synthetic color-video sources for parked-lamp software checks.

Uniform pixels cannot prove optical lamp state, civil nighttime or lawful parking.
The annotations exercise saved-source joins and negative-source rejection only.
"""
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent
ASSIGNMENT=ROOT.parent.name
REPO=ROOT.parents[2]
SCRATCH=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
CAMERAS=('overview','approach','reference_corner','driver_reference')
MODES={'witness_1':'low','witness_2':'high','exception_1_1':'high','exception_1_2':'high_with_parking'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')


def lines(rows):
    return ''.join(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n' for row in rows)


def build(suffix):
    if suffix not in MODES:raise ValueError('Unknown exact lamp suffix')
    case=ASSIGNMENT+'__'+suffix;mode=MODES[suffix]
    folder=ROOT/'diagnostic-sources'/suffix;folder.mkdir(parents=True,exist_ok=True)
    original={
        'highway':{'source_kind':'synthetic_diagnostic','highway':True,'road_id':1},
        'parking_rule':{'source_kind':'synthetic_diagnostic','reviewed_lawful_parking':True,
                        'legal_rule_composition_not_inferred':True},
        'civil_clock':{'source_kind':'synthetic_diagnostic',
                       'civil_start_iso':'2026-11-26T20:00:00-08:00'},
        'sunset_sunrise':{'source_kind':'synthetic_diagnostic',
                          'sunset_iso':'2026-11-26T16:35:00-08:00',
                          'sunrise_iso':'2026-11-27T06:40:00-08:00'}}
    for name,value in original.items():write(folder/('original-'+name+'.json'),value)
    scene={'case_id':case,'source_kind':'synthetic_diagnostic','map_name':'Town03',
           'sources':{name:{'path':'diagnostic fixture only',
              'sha256':sha(folder/('original-'+name+'.json'))} for name in original},
           'requested_sun_altitude_deg':-15,'physical_verified':False,
           'lawfully_parked_verified':False}
    write(folder/'original-scene-review.json',scene)
    trace=[{'source_kind':'synthetic_native_sample','video_frame':i,
            'native_frame':1000+i,'native_elapsed_s':50+i/20,'time_s':i/20,
            'vehicle_actor_id':1,'road_id':1,'lane_id':-1,
            'ego_speed_mps':0.0,'headlamp_request':mode,
            'native_light_state_readback':mode,
            'optical_state_observed':None,'lawfully_parked_observed':None}
           for i in range(600)]
    mapping=[{'video_frame':i,'carla_frame':1000+i,'native_frame':1000+i,
              'native_elapsed_s':50+i/20,'time_s':i/20} for i in range(600)]
    (folder/'parked-lamp-trace.jsonl').write_text(lines(trace))
    (folder/'video_frames.jsonl').write_text(lines(mapping))
    generic=[{'frame':1000+i,'time_s':i/20,'position':{'x':0,'y':0,'z':0},'position_m':[0,0,0],
              'speed_mps':0.0,'speed_mph':0.0,'velocity_mps':[0,0,0],
              'heading_deg':0,'control':{'throttle':0.0,'brake':1.0,'hand_brake':True}}
             for i in range(600)]
    (folder/'trace.jsonl').write_text(lines(generic))
    road=(REPO/'work/training__C276263__NRS-484B-533__motor_vehicle_driver/native/diagnostic-sources/reference/road.xodr').read_text()
    road=road.replace('C276263-grade','C229422-parked-lamp-diagnostic').replace('graded-highway-proposal','parked-lamp-diagnostic').replace('b=".04"','b="0"')
    (folder/'road.xodr').write_text(road.rstrip()+'\n')
    specimen=json.loads((REPO/'work/training__C276263__NRS-484B-533__motor_vehicle_driver/native/reference-adapter-video-spec.json').read_text())
    graphs=specimen['graphs']
    for i,graph in enumerate(graphs):
        old,new=900+i,1000+i
        graph['path']=graph['path'].replace(f'{old:08d}',f'{new:08d}')
        graph['attributes']['frame']=new;graph['attributes']['source']='C229422 synthetic diagnostic graph'
        graph['nodes'][0]['attributes']['entity_id']=1;graph['nodes'][0]['attributes']['vertex']=[0,0,0]
    frames=[json.loads(row) for row in specimen['files']['capture/native/frames.jsonl'].splitlines()]
    evidence=[json.loads(row) for row in specimen['files']['capture/evidence.jsonl'].splitlines()]
    for i,(frame,item) in enumerate(zip(frames,evidence)):
        old,new=900+i,1000+i;frame['frame']=new
        frame['adapter_graph']=frame['adapter_graph'].replace(f'{old:08d}',f'{new:08d}')
        frame['base']=frame['base'].replace(f'{old:08d}',f'{new:08d}')
        item['original_frame']=new;item['replay_frame']=new;item['actor_id']=1
        item['ego']['position_m']=[0,0,0];item['ego']['synthetic_diagnostic']=True
    files={'capture/native/frames.jsonl':lines(frames),
           'capture/evidence.jsonl':lines(evidence),
           'capture/recorder_info.txt':'Create 1: vehicle.tesla.model3\n',
           'capture/manifest.json':json.dumps({'extraction_confirmed':True,'frames':600,
             'synthetic_diagnostic':True,'sources':{'trace.jsonl':sha(folder/'trace.jsonl'),
             'road.xodr':sha(folder/'road.xodr')}},sort_keys=True,separators=(',',':'))+'\n'}
    spec={'files':files,'graphs':graphs,'videos':specimen['videos']}
    spec_path=ROOT/(suffix+'-diagnostic-spec.json');write(spec_path,spec)
    from worker_exchange.fixture_generator import generate
    temp=SCRATCH/('generated-lamp-'+suffix)
    if temp.exists():raise ValueError('Use fresh scratch generator output')
    temp.mkdir(parents=True);generate(spec,temp)
    camera_hashes={name:sha(temp/(name+'.mkv')) for name in CAMERAS}
    review={'assignment_id':ASSIGNMENT,'case_id':case,'source_kind':'synthetic_diagnostic',
        'trace_sha256':sha(folder/'parked-lamp-trace.jsonl'),
        'frame_map_sha256':sha(folder/'video_frames.jsonl'),
        'scene_sha256':sha(folder/'original-scene-review.json'),
        'camera_sha256':camera_hashes,'reviewer_id':'synthetic-software-fixture',
        'lawful_parking_source':'synthetic original-parking_rule.json',
        'civil_night_source':'synthetic original-civil_clock.json',
        'highway_source':'synthetic original-highway.json',
        'lawfully_parked':True,'highway':True,'civil_night':True,
        'optical_observations':[{'video_frame':i,'source_camera':'approach',
            'pixel_box_xyxy':[1,1,8,8],'lights_displayed':True,
            'depressed_or_dimmed':mode=='low','undepressed_headlamp':mode in ('high','high_with_parking'),
            'cowl_or_parking_used':mode=='high_with_parking'} for i in range(600)]}
    write(folder/'lamp-pixel-review.json',review)
    inventory=[{'path':p.name,'source':str(p.relative_to(REPO)),'sha256':sha(p)}
               for p in sorted(folder.iterdir()) if p.is_file()]
    recipe={'format':'worker-fixture-recipe','sources':inventory,
            'generator':{'source':str(spec_path.relative_to(REPO)),'sha256':sha(spec_path)}}
    recipe_path=ROOT/(suffix+'-fixture-recipe.json');write(recipe_path,recipe)
    return {'case_id':case,'source_count':len(inventory),'recipe_sha256':sha(recipe_path),
            'diagnostic_only':True}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--case-suffix',choices=tuple(MODES),required=True)
    a=p.parse_args();print(json.dumps(build(a.case_suffix),sort_keys=True))
