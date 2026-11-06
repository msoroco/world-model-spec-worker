"""Two-case positive/negative saved finalizer diagnostics; synthetic only."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import verify_report
from batch_pipeline.carla import validate_attempt

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
FINALIZER=FOLDER/'native/finalize.py'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('\n'.join(json.dumps(row) for row in rows)+'\n')


def source_digest(folder):
    return {str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file() and p.name not in ('analysis-report.json','result.json')}


def make_base(destination,suffix,approach_y,frame_count=4,full_resolution=False):
    destination.mkdir();(destination/'capture').mkdir()
    construction=json.loads((FOLDER/'draft-candidates'/suffix/'primary/construction.json').read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    if frame_count not in (4,480):raise ValueError('Only defined diagnostic frame counts are supported')
    config['duration_s']=frame_count/20;config['rate_hz']=20
    (destination/'config.json').write_text(json.dumps(config))
    geometry={'native_map_sha256':'a'*64,'approach_road_id':1,
              'turn_connector_road_id':13,'right_turn_lane_id':-2,
              'right_turn_lane_native_y_bounds_m':[3.5,7.0],
              'intersection_native_xy_bounds_m':[-7,-7,7,7],
              'right_turn_lane_design_native_verified':False}
    (destination/'road_geometry.json').write_text(json.dumps(geometry))
    (destination/'context.json').write_text(json.dumps({'surveyed_right_turn_lane_intersection':geometry}))
    trace=[];evidence=[];mapping=[];motion=[];history=[]
    lane=-2 if suffix=='witness_1' else -1
    if frame_count==4:
        states=[(-20,approach_y,(1,0),1,lane),(-12,approach_y,(1,0),1,lane),
                (-3,2,(.7,.714142842),13,-2),(-5.25,12,(0,1),4,-2)]
    else:
        states=[]
        for index in range(frame_count):
            if index<160:
                x=-40+30*index/159;y=approach_y;angle=0;road_id=1;lane_id=lane
            elif index<320:
                progress=(index-160)/159
                x=-9.5+4.25*progress;y=approach_y+(12-approach_y)*progress
                angle=math.pi*progress/2;road_id=13;lane_id=-2
            else:
                x=-5.25;y=12+18*(index-320)/159;angle=math.pi/2;road_id=4;lane_id=-2
            states.append((x,y,(math.cos(angle),math.sin(angle)),road_id,lane_id))
    for i,(x,y,forward,road_id,lane_id) in enumerate(states):
        frame=100+i;t=.05*(i+1)
        fx,fy=forward;rx,ry=-fy,fx
        corners=[[x+direction*2.6*fx+side*1.1*rx,
                  y+direction*2.6*fy+side*1.1*ry]
                 for direction,side in ((-1,-1),(-1,1),(1,1),(1,-1))]
        body=[[a,b,z] for a,b in corners for z in (0,1.5)]
        trace.append({'frame':frame,'time_s':t,
                      'position':{'x':x,'y':y,'z':0.5},
                      'heading_deg':math.degrees(math.atan2(fy,fx)),
                      'speed_mps':5.0})
        evidence.append({'original_frame':frame,'recording_time_s':t,'ego':{'body_vertices_m':body}})
        mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,'time_s':t})
        motion.append({'native_frame':frame,'time_s':t,'native_center_xy_m':[x,y],
                       'native_forward_xy':list(forward),'native_body_xy_m':corners,
                       'native_road_id':road_id,'native_lane_id':lane_id})
        history.append({'frame':frame,'time_s':t,'body_vertices_m':body})
    for name,rows in [('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                      ('video_frames.jsonl',mapping),('native_samples.jsonl',motion),
                      ('body_history.jsonl',history)]:write_rows(destination/name,rows)
    (destination/'capture/manifest.json').write_text(json.dumps({'extraction_confirmed':True,'frames':frame_count}))
    (destination/'channels').mkdir()
    for channel in config['recording_description']['channels']:
        name=channel['name'];values=[]
        for index,sample in enumerate(motion):
            if name=='drv.turning':value={'authored_intent':'right turn','observed_forward':sample['native_forward_xy']}
            elif name in ('st.intersection','st.turn_lane'):
                value=geometry
            elif name in ('drv.extreme_lane','st.lane_adjacency'):
                value={'observed_lane_id':sample['native_lane_id'],'rightmost_lane_id':-2}
            elif name=='drv.approaching':value=max(a for a,b in sample['native_body_xy_m'])<-7
            elif name=='rel.occupies':value=sample['native_body_xy_m']
            elif name=='native_body_pose_control':value=sample
            elif name=='camera_frame_join':value=mapping[index]
            else:raise ValueError('Unknown channel '+name)
            values.append({'time_s':sample['time_s'],'value':value})
        write_rows(destination/'channels'/(name+'.jsonl'),values)
    camera_sizes={camera['name']:f"{camera['width']}x{camera['height']}" for camera in config['cameras']}
    for name in ('overview','approach','reference_corner','driver_reference'):
        size=camera_sizes[name] if full_resolution else '32x32'
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i',f'color=c=black:s={size}:r=20:d={frame_count/20}',
            '-frames:v',str(frame_count),
            '-c:v','ffv1',str(destination/(name+'.mkv'))],check=True,timeout=30)


def run(frame_count=4):
    env=dict(os.environ)
    env['PYTHONPATH']=os.pathsep.join((str(ROOT/'runtime/pipeline/scenario_pipeline'),
      str(ROOT/'runtime/pipeline/python'),str(ROOT/'runtime/pipeline'),env.get('PYTHONPATH','')))
    records=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c382355-saved-') as temp:
        scratch=Path(temp)
        for suffix,lateral in (('witness_1',5.25),('witness_2',1.75)):
            base=scratch/(suffix+'-base');make_base(base,suffix,lateral,frame_count)
            positive=scratch/(suffix+'-positive');negative=scratch/(suffix+'-negative')
            shutil.copytree(base,positive);shutil.copytree(base,negative)
            before=source_digest(positive)
            command=[sys.executable,str(FINALIZER),'--attempt',str(positive),
                     '--output',str(positive/'analysis-report.json')]
            success=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
            if success.returncode:
                raise RuntimeError('Positive finalizer failed: '+success.stdout)
            after=source_digest(positive)
            if before!=after:raise RuntimeError('Saved finalizer changed acquisition')
            report=json.loads((positive/'analysis-report.json').read_text())
            result=json.loads((positive/'result.json').read_text())
            contract=json.loads((FOLDER/'draft-candidates'/suffix/'measurement-contract.json').read_text())
            verify_report(contract,report,positive)
            construction=json.loads((FOLDER/'draft-candidates'/suffix/'primary/construction.json').read_text())
            proposal=json.loads((FOLDER/'proposals/cases.json').read_text())
            case=next(c for c in proposal['cases'] if c['case_id']==result['case_id'])
            validated=validate_attempt(positive,{'case':case,'cell':{'cell_id':'C382355'},
                'actor':'motor_vehicle_driver'},construction,{'recorded_exit_code':0},{})
            if not validated['rebuild_required']:
                raise RuntimeError('Synthetic diagnostic unexpectedly claimed physical acceptance')
            if not result['maneuver_completed'] or not result['target_checks'][0]['matched']:
                raise RuntimeError('Synthetic positive did not meet its engineering target')
            if report['original_joins']['frames']!=frame_count or len(report['video_frames'])!=4 or any(v!=frame_count for v in report['video_frames'].values()):
                raise RuntimeError('Synthetic video/trace join absent')
            (negative/'native_samples.jsonl').unlink()
            bad_command=[sys.executable,str(FINALIZER),'--attempt',str(negative),
                         '--output',str(negative/'analysis-report.json')]
            failure=subprocess.run(bad_command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
            expected='Missing required source: native_samples.jsonl'
            if failure.returncode==0 or expected not in failure.stdout:
                raise RuntimeError('Missing-source negative did not reject: '+failure.stdout)
            records.append({'case_suffix':suffix,'case_id':result['case_id'],
                'positive_exit_code':success.returncode,'negative_exit_code':failure.returncode,
                'negative_expected_error':expected,'positive_log':success.stdout.strip(),
                'negative_log_tail':failure.stdout.strip().splitlines()[-1],
                'source_unchanged':True,'video_sources_decoded':4,'frames':frame_count,
                'native_attempt_validator_passed':True,'rebuild_required':True,
                'analysis_report_sha256':sha(positive/'analysis-report.json'),
                'result_sha256':sha(positive/'result.json'),
                'scope':f'{frame_count}-frame synthetic local saved-processing diagnostic, not pinned-runtime Core compatibility or Native physical evidence'})
    return records


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--frames',type=int,choices=(4,480),default=4)
    args=parser.parse_args()
    print(json.dumps({'format':'c382355-right-synthetic-saved-fixture-v1','results':run(args.frames)},indent=2))
