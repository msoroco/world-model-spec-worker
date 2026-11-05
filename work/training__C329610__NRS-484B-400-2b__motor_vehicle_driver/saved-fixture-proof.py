"""Two-case positive/negative saved finalizer diagnostics; synthetic only."""
import hashlib
import json
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


def make_base(destination,suffix,exit_x):
    destination.mkdir();(destination/'capture').mkdir()
    construction=json.loads((FOLDER/'draft-candidates'/suffix/'primary/construction.json').read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    config['duration_s']=.2;config['rate_hz']=20
    (destination/'config.json').write_text(json.dumps(config))
    directions={'approach_forward':[1,0],'approach_opposing':[-1,0],
                'destination_forward':[0,-1],'destination_opposing':[0,1]}
    geometry={'native_map_sha256':'a'*64,'road_directions_native':directions,
              'approach_centerline_point_native_m':[0,0],
              'approach_right_normal_native':[0,1], 'right_half_width_m':7,
              'intersection_entry_point_native_m':[-7,0],
              'approach_forward_native':[1,0],
              'destination_exit_point_native_m':[0,-7],
              'destination_forward_native':[0,-1],
              'destination_centerline_point_native_m':[0,0],
              'destination_right_normal_native':[1,0]}
    (destination/'road_geometry.json').write_text(json.dumps(geometry))
    (destination/'context.json').write_text(json.dumps({'surveyed_two_way_intersection':geometry}))
    trace=[];evidence=[];mapping=[];motion=[];history=[]
    for i,(x,y,forward) in enumerate([(-20,1.75,(1,0)),(-10,1.75,(1,0)),
                                       (-8,1.75,(1,0)),(exit_x,-12,(0,-1))]):
        frame=100+i;t=.05*(i+1)
        half_x,half_y=(2.6,1.1) if forward==(1,0) else (1.1,2.6)
        corners=[[x-half_x,y-half_y],[x-half_x,y+half_y],
                 [x+half_x,y+half_y],[x+half_x,y-half_y]]
        body=[[a,b,z] for a,b in corners for z in (0,1.5)]
        trace.append({'frame':frame,'time_s':t,
                      'position':{'x':x,'y':y,'z':0.5},
                      'heading_deg':0 if forward==(1,0) else -90,
                      'speed_mps':5.0})
        evidence.append({'original_frame':frame,'recording_time_s':t,'ego':{'body_vertices_m':body}})
        mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,'time_s':t})
        motion.append({'native_frame':frame,'time_s':t,'native_center_xy_m':[x,y],
                       'native_forward_xy':list(forward),'native_body_xy_m':corners})
        history.append({'frame':frame,'time_s':t,'body_vertices_m':body})
    for name,rows in [('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                      ('video_frames.jsonl',mapping),('native_samples.jsonl',motion),
                      ('body_history.jsonl',history)]:write_rows(destination/name,rows)
    (destination/'capture/manifest.json').write_text(json.dumps({'extraction_confirmed':True,'frames':4}))
    (destination/'channels').mkdir()
    for channel in config['recording_description']['channels']:
        name=channel['name'];values=[]
        for index,sample in enumerate(motion):
            if name=='drv.turning':value={'authored_intent':'left turn','observed_forward':sample['native_forward_xy']}
            elif name=='drv.in_intersection':value=all(-7<=a<=7 and -7<=b<=7 for a,b in sample['native_body_xy_m'])
            elif name in ('st.intersection','st.lane_enters','st.one_way_roadway','st.lane_direction'):
                value=geometry
            elif name=='st.centre_line':value=geometry['destination_centerline_point_native_m']
            elif name=='rel.occupies':value=sample['native_body_xy_m']
            elif name=='kin.position':value=sample['native_center_xy_m']
            elif name=='native_body_pose_control':value=sample
            elif name=='camera_frame_join':value=mapping[index]
            else:raise ValueError('Unknown channel '+name)
            values.append({'time_s':sample['time_s'],'value':value})
        write_rows(destination/'channels'/(name+'.jsonl'),values)
    for name in ('overview','approach','reference_corner','driver_reference'):
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i','color=c=black:s=32x32:r=20:d=0.2','-frames:v','4',
            '-c:v','ffv1',str(destination/(name+'.mkv'))],check=True,timeout=30)


def run():
    env=dict(os.environ)
    env['PYTHONPATH']=os.pathsep.join((str(ROOT/'runtime/pipeline/scenario_pipeline'),
      str(ROOT/'runtime/pipeline/python'),str(ROOT/'runtime/pipeline'),env.get('PYTHONPATH','')))
    records=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c329610-saved-') as temp:
        scratch=Path(temp)
        for suffix,lateral in (('witness_1',1.75),('witness_2',-1.75)):
            base=scratch/(suffix+'-base');make_base(base,suffix,lateral)
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
            validated=validate_attempt(positive,{'case':case,'cell':{'cell_id':'C329610'},
                'actor':'motor_vehicle_driver'},construction,{'recorded_exit_code':0},{})
            if not validated['rebuild_required']:
                raise RuntimeError('Synthetic diagnostic unexpectedly claimed physical acceptance')
            if not result['maneuver_completed'] or not result['target_checks'][0]['matched']:
                raise RuntimeError('Synthetic positive did not meet its engineering target')
            if report['original_joins']['frames']!=4 or len(report['video_frames'])!=4:
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
                'source_unchanged':True,'video_sources_decoded':4,'frames':4,
                'native_attempt_validator_passed':True,'rebuild_required':True,
                'analysis_report_sha256':sha(positive/'analysis-report.json'),
                'result_sha256':sha(positive/'result.json'),
                'scope':'Four-frame synthetic local saved-processing diagnostic, not exact 480-frame delivery compatibility or Native physical evidence'})
    return records


if __name__=='__main__':
    print(json.dumps({'format':'c329610-exit-synthetic-saved-fixture-v1','results':run()},indent=2))
