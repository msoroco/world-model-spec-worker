"""LVMC C110454 parking positive and missing-source diagnostics; synthetic only."""
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


def make_base(destination,suffix,frame_count=480,full_resolution=False):
    destination.mkdir();(destination/'capture').mkdir()
    construction=json.loads((FOLDER/'draft-candidates'/suffix/'primary/construction.json').read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    if frame_count!=480:raise ValueError('Full 480-frame parking interval required')
    config['duration_s']=frame_count/20;config['rate_hz']=20
    (destination/'config.json').write_text(json.dumps(config))
    directions={'approach_forward':[1,0],'approach_opposing':[-1,0],
                'destination_forward':[1,0],'destination_opposing':[-1,0]}
    geometry={'native_map_sha256':'a'*64,'road_directions_native':directions,
              'approach_centerline_point_native_m':[0,0],
              'approach_right_normal_native':[0,-1], 'right_half_width_m':3.5,
              'intersection_entry_point_native_m':[-7,0],
              'approach_forward_native':[1,0],
              'destination_exit_point_native_m':[7,0],
              'destination_forward_native':[1,0],
              'intersection_parking_boundary_native_x_m':7}
    (destination/'road_geometry.json').write_text(json.dumps(geometry))
    (destination/'context.json').write_text(json.dumps({'surveyed_two_way_intersection':geometry}))
    trace=[];evidence=[];mapping=[];motion=[];history=[]
    route=json.loads((FOLDER/'native/routes'/f'{suffix}.json').read_text())
    states=[(*route[min(round(i*(len(route)-1)/399),len(route)-1)],(1,0))
            for i in range(frame_count)]
    for i,(x,y,forward) in enumerate(states):
        frame=100+i;t=.05*(i+1)
        fx,fy=forward;rx,ry=-fy,fx
        corners=[[x+direction*2.6*fx+side*1.1*rx,
                  y+direction*2.6*fy+side*1.1*ry]
                 for direction,side in ((-1,-1),(-1,1),(1,1),(1,-1))]
        body=[[a,b,z] for a,b in corners for z in (0,1.5)]
        trace.append({'frame':frame,'time_s':t,
                      'position':{'x':x,'y':y,'z':0.5},
                      'heading_deg':math.degrees(math.atan2(fy,fx)),
                      'speed_mps':0.0 if i>=400 else 5.0})
        evidence.append({'original_frame':frame,'recording_time_s':t,'ego':{'body_vertices_m':body}})
        mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,'time_s':t})
        motion.append({'native_frame':frame,'time_s':t,'native_center_xy_m':[x,y],
                       'native_forward_xy':list(forward),'native_body_xy_m':corners,
                       'video_frame':i,'body_xy_m':corners,
                       'speed_m_s':0.0 if i>=400 else 5.0,
                       'two_way_native_survey':True})
        history.append({'frame':frame,'time_s':t,'body_vertices_m':body})
    for name,rows in [('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                      ('video_frames.jsonl',mapping),('native_samples.jsonl',motion),
                      ('body_history.jsonl',history)]:write_rows(destination/name,rows)
    (destination/'native_parking_history.json').write_text(json.dumps({
        'source_kind':'native_frame_schema',
        'intersection_boundary_source':'native_map_readback',
        'native_map_sha256':geometry['native_map_sha256'],
        'intersection_entry_boundary_x_m':7,
        'frames':[{'video_frame':row['video_frame'],'native_frame':row['native_frame'],
                   'time_s':row['time_s'],'body_xy_m':row['body_xy_m'],
                   'speed_m_s':row['speed_m_s']} for row in motion]}))
    (destination/'capture/manifest.json').write_text(json.dumps({'extraction_confirmed':True,'frames':frame_count}))
    (destination/'channels').mkdir()
    for channel in config['recording_description']['channels']:
        name=channel['name'];values=[]
        for index,sample in enumerate(motion):
            if name=='drv.standing_or_parked':value={'native_frame':sample['native_frame'],'speed_m_s':sample['speed_m_s']}
            elif name=='st.intersection':
                value=geometry
            elif name=='rel.occupies':value=sample['native_body_xy_m']
            elif name=='kin.extent':value={'body_xy_m':sample['native_body_xy_m']}
            elif name=='rel.centre_distance':value={'nearest_body_x_m':min(p[0] for p in sample['native_body_xy_m']), 'intersection_boundary_x_m':7}
            elif name=='native_body_pose_control':value=sample
            elif name=='camera_frame_join':value=mapping[index]
            else:raise ValueError('Unknown channel '+name)
            values.append({'time_s':sample['time_s'],'value':value})
        write_rows(destination/'channels'/(name+'.jsonl'),values)
    camera_sizes={camera['name']:f"{camera['width']}x{camera['height']}" for camera in config['cameras']}
    for name in ('overview','approach','intersection','parking'):
        size=camera_sizes[name] if full_resolution else '32x32'
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i',f'color=c=black:s={size}:r=20:d={frame_count/20}',
            '-frames:v',str(frame_count),
            '-c:v','ffv1',str(destination/(name+'.mkv'))],check=True,timeout=30)


def run(frame_count=480):
    env=dict(os.environ)
    env['PYTHONPATH']=os.pathsep.join((str(ROOT/'runtime/pipeline/scenario_pipeline'),
      str(ROOT/'runtime/pipeline/python'),str(ROOT/'runtime/pipeline'),env.get('PYTHONPATH','')))
    records=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c110454-lvmc-saved-') as temp:
        scratch=Path(temp)
        for suffix in ('witness_1','witness_2'):
            base=scratch/(suffix+'-base');make_base(base,suffix,frame_count)
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
            contract=json.loads((FOLDER/'draft-measurement-contracts'/suffix/'measurement-contract.json').read_text())
            verify_report(contract,report,positive)
            construction=json.loads((FOLDER/'draft-candidates'/suffix/'primary/construction.json').read_text())
            proposal=json.loads((FOLDER/'proposals/cases.json').read_text())
            case=next(c for c in proposal['cases'] if c['case_id']==result['case_id'])
            validated=validate_attempt(positive,{'case':case,'cell':{'cell_id':'C110454'},
                'actor':'motor_vehicle_driver'},construction,{'recorded_exit_code':0},{})
            if not validated['rebuild_required']:
                raise RuntimeError('Synthetic diagnostic unexpectedly claimed physical acceptance')
            if not result['target_checks'][0]['matched']:
                raise RuntimeError('Synthetic positive did not meet its engineering target')
            if report['original_joins']['frames']!=frame_count or len(report['video_frames'])!=4 or any(v!=frame_count for v in report['video_frames'].values()):
                raise RuntimeError('Synthetic video/trace join absent')
            (negative/'native_parking_history.json').unlink()
            bad_command=[sys.executable,str(FINALIZER),'--attempt',str(negative),
                         '--output',str(negative/'analysis-report.json')]
            failure=subprocess.run(bad_command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
            expected='Missing required source: native_parking_history.json'
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
    parser=argparse.ArgumentParser();parser.add_argument('--frames',type=int,choices=(480,),default=480)
    args=parser.parse_args()
    print(json.dumps({'format':'c110454-lvmc-synthetic-saved-fixture-v1','results':run(args.frames)},indent=2))
