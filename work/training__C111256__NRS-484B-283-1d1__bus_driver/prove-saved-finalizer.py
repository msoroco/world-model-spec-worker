"""Direct saved-only finalizer proof from synthetic raw 480-frame Walk rows."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
NATIVE=HERE/'native'
OUTPUT=REPO/'.runtime-work/c111256-saved-finalizer-v1'
CAMERAS=('overview','approach','reference_corner','driver_reference')
CHANNELS=('dev.pedestrian_signal','st.crosswalk','ru.pedestrian','rel.occupies',
          'drv.yields_to','kin.velocity','native_body_pose_control','camera_frame_join')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write_rows(path,values):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(v,allow_nan=False)+'\n' for v in values))

def load_source_pair():
    if str(NATIVE) not in sys.path:sys.path.insert(0,str(NATIVE))
    spec=importlib.util.spec_from_file_location('walk_fixture',NATIVE/'prove-saved-walk.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.source_pair

def make_attempt(path,suffix):
    if path.exists():shutil.rmtree(path)
    path.mkdir(parents=True);(path/'capture').mkdir()
    source_pair=load_source_pair()
    native,mapping,geometry=source_pair(suffix=='contrast')
    mapping=[dict(frame,carla_frame=frame['native_frame']) for frame in mapping]
    config=json.loads((NATIVE/'config.json').read_text())
    config.update(case_id=HERE.name+'__'+suffix,case_suffix=suffix,candidate_id='primary',
        cameras=[{'name':name,'width':1920 if name=='overview' else 1280,
                  'height':1080 if name=='overview' else 720} for name in CAMERAS],
        recording_description={'channels':[{'name':name,'unit':'structured',
            'sampling_rate_hz':20,'method':'Retained raw Native body/signal/frame source',
            'time_window':'24 s / 480 frames','reference_frame':'Native map and frame identity',
            'uncertainty':'50 ms samples; original pixels and governance require independent audit'}
            for name in CHANNELS],
            'context_inputs':[],
            'limitations':['Synthetic diagnostic cannot establish official Walk or physical yielding']})
    (path/'config.json').write_text(json.dumps(config))
    (path/'road_geometry.json').write_text(json.dumps(geometry))
    trace=[];evidence=[];body=[]
    for row,frame in zip(native,mapping):
        ident=frame['native_frame'];time=frame['time_s'];bus=row['bus_body_xy_m']
        x=sum(p[0] for p in bus)/4;y=sum(p[1] for p in bus)/4;speed=row['bus_speed_mps']
        vertices=[[a,b,z] for a,b in bus for z in (0,1.5)]
        trace.append({'frame':ident,'time_s':time,'position':{'x':x,'y':y,'z':.5},
            'heading_deg':90,'speed_mps':speed,'position_m':[x,y,.5],
            'speed_mph':speed/.44704,'control':{'throttle':0,'brake':0,'hand_brake':False},
            'synthetic_diagnostic':True,'speed_provenance':'synthetic_native_sample'})
        evidence.append({'original_frame':ident,'recording_time_s':time,
            'replay_frame':ident,'replay_simulation_time_s':time,'actor_id':820,
            'synthetic_diagnostic':True,
            'ego':{'body_vertices_m':vertices,'position_m':[x,y,.5],
                   'heading_deg':90,'speed_mps':speed,
                   'speed_provenance':'synthetic_native_sample'},
            'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                     'road_projection':{'road_id':1,'section_id':0,'lane_id':-1,'s_m':max(0,y+100)}}})
        body.append({'frame':ident,'time_s':time,'bus_body_xy_m':bus,
                     'pedestrian_body_xy_m':row['pedestrian_body_xy_m']})
    for name,rows in (('native_samples.jsonl',native),('video_frames.jsonl',mapping),
                      ('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                      ('body_history.jsonl',body)):
        write_rows(path/name,rows)
    (path/'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed':True,'frames':480,'synthetic_diagnostic':True}))
    (path/'capture/recorder_info.txt').write_text('Create 820: vehicle.mitsubishi.fusorosa\n')
    for name in CAMERAS:
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i','color=c=black:s=32x32:r=20:d=24',
            '-frames:v','480','-c:v','ffv1',str(path/(name+'.mkv'))],check=True,timeout=120)
    return path

def source_digest(path):
    return {name:sha(path/name) for name in ('native_samples.jsonl','video_frames.jsonl',
        'trace.jsonl','capture/evidence.jsonl','body_history.jsonl','capture/manifest.json',
        'road_geometry.json',*(name+'.mkv' for name in CAMERAS))}

def run_finalizer(path):
    env=dict(os.environ);env['PYTHONDONTWRITEBYTECODE']='1'
    env['PYTHONPATH']=os.pathsep.join((str(REPO/'runtime/pipeline/scenario_pipeline'),
        str(REPO/'runtime/pipeline/python'),str(REPO/'runtime/pipeline'),env.get('PYTHONPATH','')))
    return subprocess.run([sys.executable,str(NATIVE/'finalize.py'),'--attempt',str(path),
        '--output',str(path/'analysis-report.json')],cwd=REPO,env=env,
        capture_output=True,text=True,timeout=300)

def run():
    outputs=[]
    for suffix in ('reference','contrast'):
        base=make_attempt(OUTPUT/(suffix+'-base'),suffix)
        positive=OUTPUT/(suffix+'-positive');negative=OUTPUT/(suffix+'-negative')
        provenance=OUTPUT/(suffix+'-provenance-negative')
        for target in (positive,negative,provenance):
            if target.exists():shutil.rmtree(target)
            shutil.copytree(base,target)
        before=source_digest(positive)
        success=run_finalizer(positive)
        if success.returncode:raise ValueError('Saved positive failed: '+success.stdout+success.stderr)
        if source_digest(positive)!=before:raise ValueError('Saved original source changed')
        report=json.loads((positive/'analysis-report.json').read_text())
        result=json.loads((positive/'result.json').read_text())
        observed=report['measurements']['bus_yield_observation']['value']
        if observed['simultaneous_conflict_frames']!=(0 if suffix=='reference' else 19) or \
           result['target_checks'][0]['matched'] is not True or \
           report['original_joins']['frames']!=480 or any(v!=480 for v in report['video_frames'].values()) or \
           result['setup_confirmed'] or result['behavior_attempted'] or result['accepted'] or \
           result['legal_verdict_claimed']:
            raise ValueError('Saved positive reported wrong measurement or physical scope')
        (negative/'road_geometry.json').unlink()
        missing=run_finalizer(negative)
        if missing.returncode==0 or 'Missing required source: road_geometry.json' not in missing.stderr:
            raise ValueError('Missing geometry negative accepted: '+missing.stderr)
        manifest=provenance/'capture/manifest.json'
        damaged=json.loads(manifest.read_text());damaged['synthetic_diagnostic']=False
        manifest.write_text(json.dumps(damaged))
        mixed=run_finalizer(provenance)
        if mixed.returncode==0 or 'Saved source provenance markers disagree' not in mixed.stderr:
            raise ValueError('Mixed provenance negative accepted: '+mixed.stderr)
        outputs.append({'case':suffix,'frames':480,'four_source_videos_decoded':True,
            'simultaneous_conflict_frames':observed['simultaneous_conflict_frames'],
            'analysis_sha256':sha(positive/'analysis-report.json'),
            'result_sha256':sha(positive/'result.json'),
            'original_sources_preserved':True,'missing_geometry_rejected':True,
            'mixed_provenance_rejected':True,'synthetic_only':True})
    return {'format':'c111256-saved-finalizer-proof','cases':outputs,
            'positive_passed':2,'negative_rejections':4,
            'physical_acceptance_claimed':False}

if __name__=='__main__':
    print(json.dumps(run(),sort_keys=True))
