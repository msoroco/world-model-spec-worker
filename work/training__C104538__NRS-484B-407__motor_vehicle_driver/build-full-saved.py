"""Full-duration synthetic saved-source compatibility probe; never a Native run."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT/'native'))
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from test_finalize import CAMERAS,CHANNELS,prepare
from test_measure_native import box,put,put_rows
from worker_exchange.measurement_contract import verify_report


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    parent=REPO/'.runtime-work/c104538/full-saved-v1'
    if parent.exists():raise ValueError('Retain prior full-duration diagnostic; choose a new version')
    summary=json.loads((ROOT/'pinned-contract-summary.json').read_text())
    binary=REPO/'.runtime-work/linux_arm64/ffmpeg'
    probe=REPO/'.runtime-work/linux_arm64/ffprobe'
    if not binary.is_file() or not probe.is_file():raise ValueError('Local video tools unavailable')
    env=dict(os.environ)
    env['PATH']=str(binary.parent)+os.pathsep+env.get('PATH','')
    env['PYTHONPATH']=os.pathsep.join([str(REPO/'runtime/pipeline/scenario_pipeline'),str(ROOT/'native'),env.get('PYTHONPATH','')])
    parent.mkdir(parents=True)
    video=parent/'synthetic-480.mkv'
    subprocess.run([str(binary),'-nostdin','-hide_banner','-loglevel','error','-n',
        '-f','lavfi','-i','color=c=black:s=16x16:r=20:d=24',
        '-frames:v','480','-c:v','ffv1',str(video)],check=True,timeout=120)
    results=[]
    for item in summary['cases']:
        case_id=item['case_id'];suffix=case_id.split('__')[-1]
        positive=parent/suffix/'positive';positive.mkdir(parents=True)
        prepare(positive)
        config=json.loads((positive/'config.json').read_text())
        config.update(case_id=case_id,case_suffix=suffix,duration_s=24,rate_hz=20,synthetic_fixture=True)
        put(positive/'config.json',config)
        context=json.loads((positive/'native-construction-context.json').read_text())
        context['case_id']=case_id
        put(positive/'native-construction-context.json',context)
        trace=[];evidence=[];history=[];viewpoints=[];mapping=[]
        for i in range(480):
            frame=1001+i;time=round((i+1)/20,4)
            if i<160:x=6*i/159;heading=0.;velocity=[.75,0,0]
            elif i<320:x=6-4*(i-160)/159;heading=90.;velocity=[0,-.5,0]
            else:x=2+8*(i-320)/159;heading=180.;velocity=[-.75,0,0]
            body=box(x,0)
            views={role:{'driver_viewpoint_xyz_m':[x+(100 if role=='reference_left' else -100),10,4],
                         'driver_eye_point_is_assumed':True}
                   for role in ('reference_left','reference_right')}
            trace.append({'frame':frame,'time_s':time,'position_m':[x,0,0],
                'velocity_mps':velocity,'c104538_native':{'ego_body_vertices_m':body},
                'approaching_driver_views':views})
            evidence.append({'original_frame':frame,'recording_time_s':time,
                'ego':{'body_vertices_m':body}})
            history.append({'native_frame':frame,'time_s':time,
                'ego_body_vertices_m':body,'ego_heading_deg':heading,
                'ego_center_xyz_m':[x,0,0]})
            viewpoints.append({'native_frame':frame,'time_s':time,'views':views})
            mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,
                'time_s':time,'original_rgb_sha256':{name:'a'*64 for name in CAMERAS}})
        for name,values in [('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                ('native_body_history.jsonl',history),('driver_eye_rays.jsonl',viewpoints),
                ('video_frames.jsonl',mapping)]:put_rows(positive/name,values)
        put(positive/'capture/manifest.json',{'case_id':case_id,'frames':480,
            'extraction_confirmed':True,'synthetic_fixture':True})
        for name in CHANNELS:
            put_rows(positive/'channels'/(name+'.jsonl'),[
                {'native_frame':row['native_frame'],'time_s':row['time_s'],'value':{}}
                for row in mapping])
        for name in CAMERAS:
            path=positive/(name+'.mkv');path.unlink();shutil.copyfile(video,path)
        negative=parent/suffix/'negative_missing_body';shutil.copytree(positive,negative)
        (negative/'native_body_history.jsonl').unlink()
        receipts=[]
        contract=json.loads((ROOT/item['contract']).read_text())
        for label,attempt in [('positive',positive),('negative_missing_body',negative)]:
            command=['python3.11',str(ROOT/'native/finalize.py'),'--attempt',str(attempt),
                     '--output',str(attempt/'analysis-report.json')]
            run=subprocess.run(command,capture_output=True,text=True,env=env,timeout=120)
            log=ROOT/'full-saved-logs'/suffix/(label+'.log');log.parent.mkdir(parents=True,exist_ok=True)
            log.write_text(run.stdout+run.stderr)
            if label=='positive':
                assert run.returncode==0,(case_id,run.stderr)
                report=json.loads((positive/'analysis-report.json').read_text())
                values=verify_report(contract,report,positive)
                result=json.loads((positive/'result.json').read_text())
                assert len(values)==4 and report['video_frames']=={name:480 for name in CAMERAS}
                assert result['provenance_kind']=='synthetic' and not result['accepted']
                assert not result['setup_confirmed'] and not result['legal_verdict_claimed']
                assert not result['target_checks'][0]['matched']
            else:
                assert run.returncode!=0 and contract['negative']['error_contains'] in run.stderr,(case_id,run.stderr)
            receipts.append({'label':label,'exit_code':run.returncode,
                'log':str(log.relative_to(ROOT)),'log_sha256':sha(log)})
        results.append({'case_id':case_id,'contract_sha256':sha(ROOT/item['contract']),
            'positive_report_sha256':sha(positive/'analysis-report.json'),
            'positive_result_sha256':sha(positive/'result.json'),
            'positive_trace_sha256':sha(positive/'trace.jsonl'),
            'positive_video_sha256':sha(positive/'ego.mkv'),
            'receipts':receipts})
    output={'format':'c104538-full-duration-synthetic-saved-v1','cases':results,
        'frames_per_case':480,'positive_count':3,'negative_count':3,
        'contract_values_verified_per_case':4,'original_native_measurement_count':0,
        'selected_case_count':0,'recording_accepted':False,
        'scope':'full-duration synthetic saved finalizer/contract proof; no physical visibility or Core package proof'}
    path=ROOT/'full-saved-summary.json';put(path,output)
    return output


if __name__=='__main__':print(json.dumps(build()))
