"""Exercise the 3(a) finalizer on complete CPU synthetic saved captures."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
sys.path.insert(0,str(FOLDER/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import verify_report
from worker_exchange.native_output import validate_result


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows))


def build(destination,case,full_resolution=False):
    source=FOLDER/'synthetic-local'/case
    destination.mkdir();(destination/'capture/native').mkdir(parents=True)
    (destination/'channels').mkdir()
    for name in ('scene.xodr','road_geometry.json','declared_purpose.json','native_samples.jsonl'):
        shutil.copyfile(source/name,destination/name)
    construction=json.loads((FOLDER/'draft-candidates'/case/'primary/construction.json').read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    (destination/'config.json').write_text(json.dumps(config)+'\n')
    samples=[json.loads(s) for s in (destination/'native_samples.jsonl').read_text().splitlines()]
    trace=[];evidence=[];mapping=[];body=[];frames=[]
    channels={name:[] for name in config['mandatory_channels']}
    survey=json.loads((destination/'road_geometry.json').read_text())
    for index,sample in enumerate(samples):
        frame=sample['native_frame'];time=sample['time_s'];x,y=sample['native_center_xy_m']
        corners=sample['native_body_xy_m'];vertices=[[v[0],v[1],z] for v in corners for z in (0,1.5)]
        trace.append({'frame':frame,'time_s':time,'position':{'x':x,'y':y,'z':.5},
            'position_m':[x,y,.5],'heading_deg':0,'speed_mps':0,'speed_mph':0,
            'control':{'throttle':0,'brake':0,'hand_brake':False},'synthetic_diagnostic':True})
        evidence.append({'original_frame':frame,'replay_frame':frame,'actor_id':107,
            'recording_time_s':time,'replay_simulation_time_s':time,
            'ego':{'position_m':[x,y,.5],'heading_deg':0,'speed_mps':0,
                   'speed_provenance':'original_trace_actor_get_velocity','body_vertices_m':vertices},
            'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                     'road_projection':{'road_id':sample['native_road_id'],'section_id':0,
                                        'lane_id':sample['native_lane_id'],'s_m':x+100}}})
        mapping.append({'video_frame':index,'native_frame':frame,'carla_frame':frame,'time_s':time})
        body.append({'frame':frame,'time_s':time,'body_vertices_m':vertices})
        frames.append({'frame':frame,'time_s':time,'simulation_time':time,
            'base':f'graphs/base/{frame:08d}.pkl',
            'abstract':f'graphs/abstract/{frame:08d}.pkl','synthetic_diagnostic':True})
        values={'st.intersection':survey,'st.centre_turn_lane':survey,'rel.occupies':corners,
            'kin.position':[x,y],'kin.path_length':{'observed_cumulative_m':0},
            'kin.heading':0,'drv.turning':{'authored_intent':config['case_suffix'],
                'observed_forward':[1,0],'observed_road_id':sample['native_road_id']},
            'native_body_pose_control':sample,'camera_frame_join':mapping[-1]}
        for name in channels:channels[name].append({'time_s':time,'value':values[name]})
    for name,rows in [('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
        ('video_frames.jsonl',mapping),('body_history.jsonl',body),
        ('capture/native/frames.jsonl',frames)]:write_rows(destination/name,rows)
    for name,rows in channels.items():write_rows(destination/'channels'/(name+'.jsonl'),rows)
    shutil.copyfile(destination/'scene.xodr',destination/'road.xodr')
    (destination/'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    (destination/'capture/manifest.json').write_text(json.dumps({'extraction_confirmed':True,
        'frames':480,'required_observations':[],'synthetic_diagnostic':True,
        'sources':{'road.xodr':sha(destination/'road.xodr'),
                   'trace.jsonl':sha(destination/'trace.jsonl')}})+'\n')
    (destination/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'synthetic_local_diagnostic','diagnostic_fixture':True,
        'native_executed':False})+'\n')
    for camera in config['cameras']:
        name=camera['name']
        size=f'{camera["width"]}x{camera["height"]}' if full_resolution else '32x32'
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i',f'color=c=black:s={size}:r=20:d=24',
            '-frames:v','480','-c:v','ffv1',str(destination/(name+'.mkv'))],check=True,timeout=120)


def run():
    env=dict(os.environ)
    env['PYTHONPATH']=os.pathsep.join((str(ROOT/'runtime/pipeline/scenario_pipeline'),
        str(FOLDER/'native'),env.get('PYTHONPATH','')))
    records=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c394300-3a-saved-') as temporary:
        scratch=Path(temporary)
        for case in ('controlled_1','controlled_2'):
            base=scratch/(case+'-base');build(base,case)
            positive=scratch/(case+'-positive');negative=scratch/(case+'-negative')
            wrong_join=scratch/(case+'-wrong-join')
            for destination in (positive,negative,wrong_join):shutil.copytree(base,destination)
            originals={str(p.relative_to(positive)):sha(p) for p in positive.rglob('*') if p.is_file()}
            command=[sys.executable,str(FOLDER/'native/finalize.py'),'--attempt',str(positive),
                     '--output',str(positive/'analysis-report.json')]
            success=subprocess.run(command,env=env,text=True,stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,timeout=180)
            if success.returncode:raise RuntimeError(success.stdout)
            if any(sha(positive/name)!=digest for name,digest in originals.items()):
                raise RuntimeError('Finalizer changed acquisition source')
            report=json.loads((positive/'analysis-report.json').read_text())
            result=validate_result(json.loads((positive/'result.json').read_text()))
            contract=json.loads((FOLDER/'draft-measurements'/(case+'-contract.json')).read_text())
            verify_report(contract,report,positive)
            if not report['measurements']['center_turn_purpose_and_movement']['value']['requested_movement_observed_in_saved_rows']:
                raise RuntimeError('Synthetic movement did not exercise requested case')
            if result['setup_confirmed'] or result['behavior_attempted'] or result['maneuver_completed'] or result['accepted']:
                raise RuntimeError('Diagnostic result claimed physical success')
            (negative/'declared_purpose.json').unlink()
            failure=subprocess.run([sys.executable,str(FOLDER/'native/finalize.py'),
                '--attempt',str(negative),'--output',str(negative/'analysis-report.json')],
                env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            if failure.returncode==0 or 'Missing required source: declared_purpose.json' not in failure.stdout:
                raise RuntimeError('Missing purpose negative did not reject: '+failure.stdout)
            changed=[json.loads(row) for row in (wrong_join/'video_frames.jsonl').read_text().splitlines()]
            changed[100]['native_frame']+=1
            write_rows(wrong_join/'video_frames.jsonl',changed)
            join_failure=subprocess.run([sys.executable,str(FOLDER/'native/finalize.py'),
                '--attempt',str(wrong_join),'--output',str(wrong_join/'analysis-report.json')],
                env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
            if join_failure.returncode==0 or 'Original frame/time mapping invalid' not in join_failure.stdout:
                raise RuntimeError('Frame-join negative did not reject: '+join_failure.stdout)
            records.append({'case':case,'frames':report['original_joins']['frames'],
                'source_videos':report['video_frames'],'positive_exit':0,
                'missing_purpose_exit':failure.returncode,'wrong_frame_join_exit':join_failure.returncode,
                'acquisition_unchanged':True,'physical_flags_false':True,
                'result_sha256':sha(positive/'result.json'),
                'analysis_sha256':sha(positive/'analysis-report.json'),
                'scope':'CPU synthetic saved finalizer; no CARLA, Core, Lean or render'})
    return records


if __name__=='__main__':print(json.dumps(run(),indent=2))
