"""480-frame synthetic saved positives and source negatives for unselected 3(c)."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(FOLDER/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from geometry import TARGET_FEET,route
from worker_exchange.measurement_contract import verify_report
from batch_pipeline.carla import validate_attempt


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path,records):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in records))


def source_hashes(folder):
    return {str(p.relative_to(folder)):sha(p) for p in folder.rglob('*')
            if p.is_file() and p.name not in ('result.json','analysis-report.json')}


def make_base(destination,suffix,full_resolution=False):
    destination.mkdir();(destination/'capture/native').mkdir(parents=True)
    (destination/'channels').mkdir()
    construction=json.loads((FOLDER/'draft-candidates'/suffix/'primary/construction.json').read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    (destination/'config.json').write_text(json.dumps(config))
    geometry=json.loads((FOLDER/'draft-measurements/native-geometry-draft.json').read_text())
    geometry.update(native_map_sha256='a'*64,
                    scope='synthetic local software fixture; no Native map readback')
    (destination/'road_geometry.json').write_text(json.dumps(geometry))
    (destination/'context.json').write_text(json.dumps({'surveyed_center_turn_lane':geometry}))
    path=route(suffix)
    samples=[];trace=[];evidence=[];mapping=[];body_history=[];capture_frames=[]
    for i in range(480):
        station=i*(len(path)-1)/479
        j=min(int(station),len(path)-2);fraction=station-j
        a,b=path[j],path[j+1]
        x=a[0]*(1-fraction)+b[0]*fraction
        y=a[1]*(1-fraction)+b[1]*fraction
        before=path[max(0,j-1)];after=path[min(len(path)-1,j+2)]
        dx=after[0]-before[0];dy=after[1]-before[1];length=math.hypot(dx,dy)
        fx,fy=dx/length,dy/length;rx,ry=-fy,fx
        corners=[[x+d*2.5*fx+s*rx,y+d*2.5*fy+s*ry]
                 for d,s in ((-1,-1),(-1,1),(1,1),(1,-1))]
        vertices=[[v[0],v[1],z] for v in corners for z in (0,1.5)]
        frame=100+i;time_s=(i+1)/20
        road=4 if j<400 else 13 if j<550 else 1
        lane=-2 if all(v[1]<=-1.75 for v in corners) else -1
        speed=math.dist([x,y],samples[-1]['native_center_xy_m'])/.05 if samples else 0
        sample={'native_frame':frame,'time_s':time_s,'native_center_xy_m':[x,y],
            'native_forward_xy':[fx,fy],'native_body_xy_m':corners,
            'native_road_id':road,'native_lane_id':lane,'speed_mps':speed,
            'controller_request':{'synthetic_diagnostic':True}}
        samples.append(sample)
        trace.append({'frame':frame,'time_s':time_s,'position':{'x':x,'y':y,'z':.5},
                      'position_m':[x,y,.5],'heading_deg':math.degrees(math.atan2(fy,fx)),
                      'speed_mps':speed,'speed_mph':speed/.44704,
                      'control':{'throttle':0,'brake':0,'hand_brake':False},
                      'synthetic_diagnostic':True})
        evidence.append({'original_frame':frame,'replay_frame':frame,'actor_id':107,
                         'recording_time_s':time_s,'replay_simulation_time_s':time_s,
                         'ego':{'position_m':[x,y,.5],
                                'heading_deg':math.degrees(math.atan2(fy,fx)),
                                'speed_mps':speed,
                                'speed_provenance':'original_trace_actor_get_velocity',
                                'body_vertices_m':vertices},
                         'world':{'weather':{'cloudiness':0,'precipitation':0,
                                            'wetness':0,'fog_density':0},
                                  'road_projection':{'road_id':road,'section_id':0,
                                                     'lane_id':lane,'s_m':x+66.5}}})
        mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,'time_s':time_s})
        body_history.append({'frame':frame,'time_s':time_s,'body_vertices_m':vertices})
        capture_frames.append({'frame':frame,'time_s':time_s,'simulation_time':time_s,
                               'base':f'graphs/base/{frame:08d}.pkl',
                               'abstract':f'graphs/abstract/{frame:08d}.pkl',
                               'synthetic_diagnostic':True})
    for name,records in [('native_samples.jsonl',samples),('trace.jsonl',trace),
                         ('capture/evidence.jsonl',evidence),('video_frames.jsonl',mapping),
                         ('body_history.jsonl',body_history),
                         ('capture/native/frames.jsonl',capture_frames)]:
        write_rows(destination/name,records)
    road=FOLDER/'draft-construction/scene.xodr'
    shutil.copyfile(road,destination/'road.xodr')
    (destination/'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    (destination/'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed':True,'frames':480,'required_observations':[],
        'sources':{'road.xodr':sha(destination/'road.xodr'),
                   'trace.jsonl':sha(destination/'trace.jsonl')},
        'synthetic_diagnostic':True}))
    for channel in config['recording_description']['channels']:
        name=channel['name'];values=[]
        for index,sample in enumerate(samples):
            if name=='st.centre_turn_lane':value=geometry
            elif name=='rel.occupies':value=sample['native_body_xy_m']
            elif name=='drv.turning':value={'observed_forward':sample['native_forward_xy']}
            elif name=='kin.path_length':value={'sampled_native_center_xy_m':sample['native_center_xy_m']}
            elif name=='drv.lane_change':value={'native_road_id':sample['native_road_id'],
                                               'native_lane_id':sample['native_lane_id']}
            elif name=='native_body_pose_control':value=sample
            elif name=='camera_frame_join':value=mapping[index]
            else:raise ValueError('Unknown channel '+name)
            values.append({'time_s':sample['time_s'],'value':value})
        write_rows(destination/'channels'/(name+'.jsonl'),values)
    for camera in config['cameras']:
        name=camera['name']
        size=f'{camera["width"]}x{camera["height"]}' if full_resolution else '32x32'
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i',f'color=c=black:s={size}:r=20:d=24',
            '-frames:v','480','-c:v','ffv1',str(destination/(name+'.mkv'))],
            check=True,timeout=60)


def run():
    env=dict(os.environ)
    env['PYTHONPATH']=os.pathsep.join((str(ROOT/'runtime/pipeline/scenario_pipeline'),
        str(ROOT/'runtime/pipeline/python'),str(ROOT/'runtime/pipeline'),
        str(FOLDER/'native'),env.get('PYTHONPATH','')))
    records=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c394300-3c-saved-') as temporary:
        scratch=Path(temporary)
        for suffix in TARGET_FEET:
            base=scratch/(suffix+'-base');make_base(base,suffix)
            positive=scratch/(suffix+'-positive');negative=scratch/(suffix+'-missing')
            wrong=scratch/(suffix+'-wrong-connector')
            for destination in (positive,negative,wrong):shutil.copytree(base,destination)
            before=source_hashes(positive)
            command=[sys.executable,str(FOLDER/'native/finalize.py'),'--attempt',str(positive),
                     '--output',str(positive/'analysis-report.json')]
            success=subprocess.run(command,env=env,text=True,stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,timeout=180)
            if success.returncode:raise RuntimeError('Positive saved finalizer failed: '+success.stdout)
            if source_hashes(positive)!=before:raise RuntimeError('Finalizer changed original sources')
            report=json.loads((positive/'analysis-report.json').read_text())
            result=json.loads((positive/'result.json').read_text())
            contract=json.loads((FOLDER/'draft-measurements'/(suffix+'-contract.json')).read_text())
            verify_report(contract,report,positive)
            construction=json.loads((FOLDER/'draft-candidates'/suffix/'primary/construction.json').read_text())
            config=json.loads((positive/'config.json').read_text())
            validated=validate_attempt(positive,{'case':{
                'case_id':result['case_id'],'recording_description':config['recording_description'],
                'sweep_measurements':[]},'cell':{'cell_id':'C394300'},
                'actor':'motor_vehicle_driver'},construction,{'recorded_exit_code':0},{})
            if not validated['rebuild_required']:
                raise RuntimeError('Synthetic saved fixture unexpectedly passed physical acceptance')
            expected={'below_50_ft':'within_50_feet','at_50_ft':'unresolved_at_50_feet',
                      'above_50_ft':'exceeds_50_feet'}[suffix]
            observed=report['measurements']['after_left_turn_distance_interval']['value']['threshold_relation']
            if observed!=expected:raise RuntimeError(f'Unexpected sampled interval: {suffix} {observed}')
            if report['original_joins']['frames']!=480 or set(report['video_frames'].values())!={480}:
                raise RuntimeError('Original 480-frame joins or video decode incomplete')
            if result['setup_confirmed'] or result['accepted'] or result['legal_verdict_claimed']:
                raise RuntimeError('Synthetic fixture claimed Native design or acceptance')
            (negative/'native_samples.jsonl').unlink()
            (wrong/'road_geometry.json').write_text(json.dumps({**json.loads((wrong/'road_geometry.json').read_text()),
                'left_turn_connector_road_id':999}))
            failures=[]
            for target,expected_error in ((negative,'Missing required source: native_samples.jsonl'),
                                          (wrong,'Observed left turn into center lane absent')):
                failed=subprocess.run([sys.executable,str(FOLDER/'native/finalize.py'),
                    '--attempt',str(target),'--output',str(target/'analysis-report.json')],
                    env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
                if failed.returncode==0 or expected_error not in failed.stdout:
                    raise RuntimeError('Negative saved fixture not rejected: '+failed.stdout)
                failures.append(expected_error)
            records.append({'case_suffix':suffix,'case_id':result['case_id'],'frames':480,
                'positive_exit_code':0,'negative_exit_codes':[1,1],
                'negative_errors':failures,'threshold_relation':observed,
                'distance_interval_m':report['measurements']['after_left_turn_distance_interval']['value']['distance_interval_m'],
                'source_unchanged':True,'video_sources_decoded':4,'setup_confirmed':False,
                'native_attempt_validator_passed':True,'rebuild_required':True,
                'analysis_report_sha256':sha(positive/'analysis-report.json'),
                'result_sha256':sha(positive/'result.json'),
                'scope':'480-frame synthetic saved software diagnostic; no Native, Core/render or compatibility receipt'})
    return records


if __name__=='__main__':print(json.dumps(run(),indent=2))
