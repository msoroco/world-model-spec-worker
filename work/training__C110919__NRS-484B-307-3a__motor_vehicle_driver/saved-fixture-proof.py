"""Synthetic Native-shaped positive/negative saved processing for both cases."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
import os
import pickle
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
NATIVE=FOLDER/'native'
sys.path.insert(0,str(NATIVE))
from measure import synthetic

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write_rows(path,values):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(value,allow_nan=False)+'\n' for value in values))
def digest(path):
    return {str(p.relative_to(path)):sha(p) for p in path.rglob('*')
            if p.is_file() and p.name not in ('analysis-report.json','result.json')}

def make_attempt(destination: Path,case: str,full_resolution: bool=False):
    destination.mkdir();(destination/'capture').mkdir()
    construction=json.loads((FOLDER/'draft-candidates'/case/'primary/construction.json').read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    (destination/'config.json').write_text(json.dumps(config))
    geometry={'native_map_sha256':'a'*64,'signal_actor_id':601,
              'right_arrow_actor_id':603,'opposing_signal_actor_id':604,
              'right_arrow_glyph_physically_verified':False,
              'turn_prohibition_survey':{'authored_signs':[],'native_traffic_sign_actors':[]},
              'stop_line_y_m':-14.0,'nearest_crosswalk_y_m':-11.0,
              'destination_crosswalk_x_m':10.0,
              'lanes':{'approach_right':{'road_id':1,'lane_id':-1,'forward_xy':[0,1]},
                       'approach_left':{'road_id':1,'lane_id':1,'forward_xy':[0,-1]},
                       'destination_right':{'road_id':2,'lane_id':-1,'forward_xy':[1,0]},
                       'destination_left':{'road_id':2,'lane_id':1,'forward_xy':[-1,0]}},
              'synthetic_diagnostic':True}
    (destination/'road_geometry.json').write_text(json.dumps(geometry))
    (destination/'context.json').write_text(json.dumps({'surveyed_right_turn':geometry}))
    frames=synthetic(case)['frames']
    trace=[];evidence=[];mapping=[];native=[];body=[]
    for i,row in enumerate(frames):
        frame=100+i;time=(i+1)/20;x=row['ego_x_m'];y=row['ego_y_m']
        turn=181 if case=='witness_1' else 145
        if i<turn:heading=90.0
        elif i<=turn+60:heading=90-(i-turn)*1.5
        else:heading=0.0
        angle=math.radians(heading);fx,fy=math.cos(angle),math.sin(angle);rx,ry=-fy,fx
        corners=[[round(x+direction*2.6*fx+side*1.1*rx,5),
                  round(y+direction*2.6*fy+side*1.1*ry,5)]
                 for direction,side in ((-1,-1),(-1,1),(1,1),(1,-1))]
        vertices=[[a,b,z] for a,b in corners for z in (0,1.5)]
        speed=row['ego_speed_m_s']
        trace.append({'frame':frame,'time_s':time,'position':{'x':x,'y':y,'z':.5},
                      'heading_deg':heading,'speed_mps':speed,
                      'position_m':[x,y,.5],'speed_mph':speed/.44704,
                      'control':{'throttle':0,'brake':0,'hand_brake':False}})
        evidence.append({'original_frame':frame,'recording_time_s':time,
                         'replay_frame':frame,'replay_simulation_time_s':time,
                         'actor_id':107,
                         'ego':{'body_vertices_m':vertices,'position_m':[x,y,.5],
                                'heading_deg':heading,'speed_mps':speed,
                                'speed_provenance':'original_trace_actor_get_velocity'},
                         'world':{'weather':{'cloudiness':0,'precipitation':0,
                                             'wetness':0,'fog_density':0},
                                  'road_projection':{'road_id':1 if i<turn else 13 if i<=turn+60 else 2,
                                                     'section_id':0,'lane_id':-1,'s_m':max(0,y+100)}}})
        mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,'time_s':time})
        native.append({'native_frame':frame,'time_s':time,'native_center_xy_m':[x,y],
                       'native_yaw_deg':heading,'native_body_xy_m':corners,'speed_mps':speed,
                       'walker_center_xy_m':[10,0 if row['pedestrian_conflict_occupied'] else 5],
                       'walker_conflict_occupied':row['pedestrian_conflict_occupied'],
                       'cross_traffic_conflict_occupied':row['cross_traffic_conflict_occupied'],
                       'turn_prohibition_present':False,
                       'ego_turn_entered':row['ego_turn_entered'],
                       'signal_state_observed':'Green',
                       'right_arrow_state_observed':'Green',
                       'opposing_signal_state_observed':'Red',
                       'right_arrow_actor_id':603,
                       'opposing_signal_actor_id':604,
                       'right_arrow_glyph_physically_verified':False,
                       'controller_request':{'synthetic_diagnostic':True}})
        body.append({'frame':frame,'time_s':time,'body_vertices_m':vertices})
    for name,values in [('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                        ('video_frames.jsonl',mapping),('native_samples.jsonl',native),
                        ('body_history.jsonl',body)]:write_rows(destination/name,values)
    (destination/'capture/manifest.json').write_text(json.dumps({'extraction_confirmed':True,'frames':480,
                                                                   'synthetic_diagnostic':True}))
    (destination/'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    (destination/'channels').mkdir()
    for channel in config['recording_description']['channels']:
        name=channel['name'];values=[]
        for i,sample in enumerate(native):
            if name=='dev.traffic_signal':value={'observed_state':'Green','native_actor_id':601,
                'authored_right_arrow':'green_arrow(right)','right_arrow_actor_id':603,
                'right_arrow_state':'Green','opposing_signal_actor_id':604,
                'opposing_signal_state':'Red','arrow_glyph_physically_verified':False}
            elif name=='st.stop_line':value=-14.0
            elif name=='st.crosswalk':value=-11.0
            elif name=='drv.stopped':value=sample['speed_mps']<.05
            elif name=='kin.velocity':value=sample['speed_mps']
            elif name=='drv.extreme_lane':value=geometry['lanes']['approach_right']
            elif name=='st.one_way_roadway':value=geometry['lanes']
            elif name=='drv.yields_to':value={'walker_conflict_occupied':sample['walker_conflict_occupied'],
                'cross_traffic_conflict_occupied':sample['cross_traffic_conflict_occupied']}
            elif name=='native_body_pose_control':value=sample
            elif name=='camera_frame_join':value=mapping[i]
            else:raise ValueError('Unknown channel: '+name)
            values.append({'time_s':sample['time_s'],'value':value})
        write_rows(destination/'channels'/(name+'.jsonl'),values)
    sizes={camera['name']:f"{camera['width']}x{camera['height']}" for camera in config['cameras']}
    for name in ('overview','approach','signal','destination'):
        size=sizes[name] if full_resolution else '32x32'
        subprocess.run([str(ROOT/'.runtime-work/linux_arm64/ffmpeg'),'-nostdin','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i',f'color=c=black:s={size}:r=20:d=24',
            '-frames:v','480','-c:v','ffv1',str(destination/(name+'.mkv'))],
            check=True,timeout=120)
    if full_resolution:
        # Retained graph topology is diagnostic software input. Frame/pose and
        # provenance are synthesized here and never presented as original CARLA.
        sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
        from traffic_spec_adapter.adapter import load_graph
        from geometry import open_drive
        graph=load_graph(ROOT/'runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl')
        graph_dir=destination/'capture/native/graphs/base';graph_dir.mkdir(parents=True)
        frame_rows=[]
        for item in mapping:
            frame=item['native_frame'];time=item['time_s']
            graph.graph['frame']=frame
            (graph_dir/f'{frame:08d}.pkl').write_bytes(pickle.dumps(graph,protocol=4))
            frame_rows.append({'frame':frame,'simulation_time':time,'time_s':time,
                               'base':f'graphs/base/{frame:08d}.pkl',
                               'abstract':f'graphs/abstract/{frame:08d}.pkl',
                               'synthetic_diagnostic':True})
        write_rows(destination/'capture/native/frames.jsonl',frame_rows)
        (destination/'road.xodr').write_text(open_drive())
        manifest=json.loads((destination/'capture/manifest.json').read_text())
        manifest['sources']={'road.xodr':sha(destination/'road.xodr'),
                             'trace.jsonl':sha(destination/'trace.jsonl')}
        (destination/'capture/manifest.json').write_text(json.dumps(manifest))

def run():
    env=dict(os.environ)
    env['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    env['PYTHONPATH']=os.pathsep.join((str(ROOT/'runtime/pipeline/scenario_pipeline'),
        str(ROOT/'runtime/pipeline/python'),str(ROOT/'runtime/pipeline'),env.get('PYTHONPATH','')))
    records=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c110919-8c-saved-') as tmp:
        for case in ('witness_1','witness_2'):
            base=Path(tmp)/(case+'-base');make_attempt(base,case)
            positive=Path(tmp)/(case+'-positive');negative=Path(tmp)/(case+'-negative')
            shutil.copytree(base,positive);shutil.copytree(base,negative)
            before=digest(positive)
            command=[sys.executable,str(NATIVE/'finalize.py'),'--attempt',str(positive),
                     '--output',str(positive/'analysis-report.json')]
            success=subprocess.run(command,env=env,text=True,stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,timeout=300)
            if success.returncode:raise RuntimeError('Positive saved finalization failed: '+success.stdout)
            if digest(positive)!=before:raise RuntimeError('Saved finalizer changed acquisition')
            report=json.loads((positive/'analysis-report.json').read_text())
            result=json.loads((positive/'result.json').read_text())
            sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
            from worker_exchange.measurement_contract import verify_report
            contract=json.loads((FOLDER/'draft-candidates'/case/'measurement-contract.json').read_text())
            verify_report(contract,report,positive)
            assert report['original_joins']['frames']==480
            assert result['target_checks'][0]['matched']
            assert result['maneuver_completed']
            (negative/'road_geometry.json').unlink()
            failure=subprocess.run([sys.executable,str(NATIVE/'finalize.py'),'--attempt',str(negative),
                                    '--output',str(negative/'analysis-report.json')],
                                   env=env,text=True,stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,timeout=300)
            if failure.returncode==0 or 'Missing required source: road_geometry.json' not in failure.stdout:
                raise RuntimeError('Negative missing-source diagnostic accepted: '+failure.stdout)
            records.append({'case':case,'positive_exit_code':success.returncode,
                            'negative_exit_code':failure.returncode,
                            'analysis_sha256':sha(positive/'analysis-report.json'),
                            'result_sha256':sha(positive/'result.json'),
                            'source_unchanged':True,'video_decoded':4,'frames':480,
                            'scope':'synthetic saved finalization only; no CARLA/physical/acceptance'})
    return records

if __name__=='__main__':
    print(json.dumps({'format':'c110919-synthetic-saved-proof-v1','results':run()},indent=2))
