"""Synthetic 480-frame saved positive and missing-source negative diagnostics."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import verify_report
from batch_pipeline.carla import validate_attempt


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_rows(path,values):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(value,allow_nan=False)+'\n' for value in values))


def source_hashes(folder):
    return {str(p.relative_to(folder)):sha(p) for p in folder.rglob('*')
            if p.is_file() and p.name not in ('analysis-report.json','result.json')}


def make_base(destination,suffix,full_resolution=False):
    destination.mkdir();(destination/'capture').mkdir();(destination/'channels').mkdir()
    construction=json.loads((HERE/'draft-candidates'/suffix/'primary/construction.json').read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    (destination/'config.json').write_text(json.dumps(config))
    source=HERE/'draft-facility'/suffix
    shutil.copyfile(source/'native_samples.jsonl',destination/'native_samples.jsonl')
    shutil.copyfile(source/'road_geometry.json',destination/'road_geometry.json')
    shutil.copyfile(source/'exception_context.json',destination/'exception_context.json')
    exception=json.loads((destination/'exception_context.json').read_text())
    exception['requested_exception_context']={key:exception[key] for key in
        ('source_kind','exceptions','note')}
    (destination/'exception_context.json').write_text(json.dumps(exception))
    geometry=json.loads((destination/'road_geometry.json').read_text())
    (destination/'context.json').write_text(json.dumps({'surveyed_bicycle_facility_and_alley':geometry}))
    motion=rows(destination/'native_samples.jsonl')
    trace=[];evidence=[];mapping=[];body_history=[]
    for i,sample in enumerate(motion):
        frame=sample['native_frame'];time=sample['time_s'];x,y=sample['native_center_xy_m']
        body=[[a,b,z] for a,b in sample['native_body_xy_m'] for z in (0,1.5)]
        fx,fy=sample['native_forward_xy']
        trace.append({'frame':frame,'time_s':time,'position':{'x':x,'y':y,'z':.5},
                      'heading_deg':math.degrees(math.atan2(fy,fx)),
                      'speed_mps':sample['speed_mps']})
        evidence.append({'original_frame':frame,'recording_time_s':time,
                         'ego':{'body_vertices_m':body}})
        mapping.append({'video_frame':i,'native_frame':frame,
                        'carla_frame':frame,'time_s':time})
        body_history.append({'frame':frame,'time_s':time,'body_vertices_m':body})
    for name,value in (('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                       ('video_frames.jsonl',mapping),('body_history.jsonl',body_history)):
        write_rows(destination/name,value)
    (destination/'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed':True,'frames':480,'synthetic_diagnostic':True}))
    for channel in config['recording_description']['channels']:
        name=channel['name'];values=[]
        for i,sample in enumerate(motion):
            if name in ('st.bicycle_lane_or_path','st.driveway_or_alley_entrance'):value=geometry
            elif name=='rel.occupies':value=sample['native_body_xy_m']
            elif name=='kin.extent':value={'body_xy_m':sample['native_body_xy_m']}
            elif name=='kin.position':value=sample['native_center_xy_m']
            elif name=='ego_speed':value=sample['speed_mps']
            elif name=='drv.standing_or_parked':value={
                'observed_speed_mps':sample['speed_mps'],
                'requested_stop_xy_m':[-12,-1.5 if suffix=='probe_a' else -4.0]}
            elif name=='ru.pedestrian':value={
                'native_actor_id':1,'native_xy_m':[8,-4],
                'synthetic_diagnostic':True}
            elif name=='exception_context':value={
                'source':'exception_context.json','observed_exception_status':'unresolved'}
            elif name=='native_body_pose_control':value=sample
            elif name=='camera_frame_join':value=mapping[i]
            else:raise ValueError('Unknown channel '+name)
            values.append({'time_s':sample['time_s'],'value':value})
        write_rows(destination/'channels'/(name+'.jsonl'),values)
    camera_sizes={c['name']:f"{c['width']}x{c['height']}" for c in config['cameras']}
    for name in ('overview','approach','facility','driver_reference'):
        size=camera_sizes[name] if full_resolution else '32x32'
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i',f'color=c=black:s={size}:r=20:d=24',
            '-frames:v','480','-c:v','ffv1',str(destination/(name+'.mkv'))],
            check=True,timeout=120)


def run():
    env=os.environ.copy()
    env['PYTHONPATH']=os.pathsep.join((str(ROOT/'runtime/pipeline/scenario_pipeline'),
        str(ROOT/'runtime/pipeline/python'),str(ROOT/'runtime/pipeline'),
        str(HERE/'native'),env.get('PYTHONPATH','')))
    results=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c10052-saved-') as temp:
        scratch=Path(temp)
        for suffix in ('probe_a','probe_b'):
            base=scratch/(suffix+'-base');make_base(base,suffix)
            positive=scratch/(suffix+'-positive');negative=scratch/(suffix+'-negative')
            shutil.copytree(base,positive);shutil.copytree(base,negative)
            before=source_hashes(positive)
            command=[sys.executable,str(HERE/'native/finalize.py'),'--attempt',str(positive),
                     '--output',str(positive/'analysis-report.json')]
            completed=subprocess.run(command,env=env,text=True,stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT,timeout=300)
            if completed.returncode:raise RuntimeError('Positive saved finalizer failed: '+completed.stdout)
            if source_hashes(positive)!=before:raise RuntimeError('Saved finalizer rewrote acquisition')
            report=json.loads((positive/'analysis-report.json').read_text())
            result=json.loads((positive/'result.json').read_text())
            contract=json.loads((HERE/'draft-facility'/suffix/'measurement-contract.json').read_text())
            verify_report(contract,report,positive)
            config=json.loads((positive/'config.json').read_text())
            construction=json.loads((HERE/'draft-candidates'/suffix/'primary/construction.json').read_text())
            validated=validate_attempt(positive,{'case':{'case_id':result['case_id'],
                'recording_description':config['recording_description'],'sweep_measurements':[]},
                'cell':{'cell_id':'C10052'},'actor':'motor_vehicle_driver'},
                construction,{'recorded_exit_code':0},{})
            if not validated['rebuild_required'] or result['accepted'] or result['legal_verdict_claimed']:
                raise ValueError('Synthetic fixture claimed physical acceptance')
            (negative/'exception_context.json').unlink()
            failure=subprocess.run([sys.executable,str(HERE/'native/finalize.py'),
                '--attempt',str(negative),'--output',str(negative/'analysis-report.json')],
                env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
            if failure.returncode==0 or 'Missing required source: exception_context.json' not in failure.stdout:
                raise ValueError('Missing-exception-source negative did not fail')
            evidence_dir=HERE/'draft-facility'/suffix
            shutil.copyfile(positive/'analysis-report.json',evidence_dir/'saved-analysis-report.json')
            shutil.copyfile(positive/'result.json',evidence_dir/'saved-result.json')
            (evidence_dir/'missing-source.log').write_text(failure.stdout)
            results.append({'suffix':suffix,'positive_report_sha256':sha(positive/'analysis-report.json'),
                'result_sha256':sha(positive/'result.json'),
                'source_hashes':before,'source_videos':report['video_frames'],
                'native_validation_rebuild_required':True,
                'missing_source_exit_code':failure.returncode,
                'missing_source_error':'Missing required source: exception_context.json',
                'scope':'480-frame synthetic saved diagnostic; no physical Native or acceptance'})
    summary={'format':'c10052-saved-diagnostic-v1','rows':results,'ready':False}
    (HERE/'saved-diagnostic-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':print(json.dumps(run(),indent=2))
