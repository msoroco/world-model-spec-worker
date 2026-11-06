"""Full-window synthetic saved positives and source negatives; no Native claim."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
sys.path.insert(0,str(HERE/'native'))
from worker_exchange.measurement_contract import verify_report


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows))


def source_hashes(folder):
    return {str(path.relative_to(folder)):sha(path) for path in folder.rglob('*')
            if path.is_file() and path.name not in ('result.json','analysis-report.json')}


def make_base(destination,suffix,env):
    destination.mkdir()
    (destination/'capture/native').mkdir(parents=True)
    (destination/'channels').mkdir()
    construction=json.loads((HERE/'draft-bundles'/suffix/'primary/construction.json').read_text())
    config=json.loads(next(x['content'] for x in construction['files'] if x['path']=='config.json'))
    (destination/'config.json').write_text(json.dumps(config)+'\n')
    source=ROOT/'.runtime-work/c10316-crosswalk-synthetic'/suffix
    shutil.copy2(source/'native_samples.jsonl',destination/'native_samples.jsonl')
    shutil.copy2(source/'crosswalk-context.json',destination/'crosswalk-context.json')
    samples=[json.loads(line) for line in (destination/'native_samples.jsonl').read_text().splitlines()]
    trace=[];evidence=[];mapping=[];native=[]
    channel_values={item['name']:[] for item in config['recording_description']['channels']}
    for i,item in enumerate(samples):
        frame,time=100+i,item['time_s'];item['native_frame']=frame
        x,y=item['pedestrian_xy_m'];body=item['pedestrian_footprint_xy_m']
        body3=[[p[0],p[1],z] for p in body for z in (0,1.8)]
        trace.append({'frame':frame,'time_s':time,'position':{'x':x,'y':y,'z':.5},
                      'position_m':[x,y,.5],'heading_deg':0,
                      'speed_mps':item['speed_mps'],'speed_mph':item['speed_mps']/.44704,
                      'synthetic_diagnostic':True})
        evidence.append({'original_frame':frame,'replay_frame':frame,'actor_id':107,
                         'recording_time_s':time,'replay_simulation_time_s':time,
                         'ego':{'position_m':[x,y,.5],'heading_deg':0,
                                'speed_mps':item['speed_mps'],
                                'speed_provenance':'synthetic_request_not_native',
                                'body_vertices_m':body3},
                         'synthetic_diagnostic':True,
                         'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0}}})
        mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,'time_s':time})
        native.append({'frame':frame,'time_s':time,'simulation_time':time,
                       'base':f'graphs/base/{frame:08d}.pkl',
                       'abstract':f'graphs/abstract/{frame:08d}.pkl',
                       'synthetic_diagnostic':True})
        values={'kin.position':[x,y],'kin.heading':[1,0],
                'rel.occupies':{'crosswalk_id':item['crosswalk_id'],
                                'original_footprint_xy_m':body},
                'native_pedestrian_pose':item,'camera_frame_join':mapping[-1]}
        for name in channel_values:
            channel_values[name].append({'time_s':time,'value':values[name]})
    write_rows(destination/'native_samples.jsonl',samples)
    for name,rows in (('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                      ('video_frames.jsonl',mapping),('capture/native/frames.jsonl',native)):
        write_rows(destination/name,rows)
    for name,rows in channel_values.items():
        write_rows(destination/'channels'/(name+'.jsonl'),rows)
    shutil.copy2(HERE/'native/road.xodr',destination/'road.xodr')
    (destination/'capture/recorder_info.txt').write_text('Create 107: walker.pedestrian.synthetic\n')
    (destination/'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed':True,'frames':240,'required_observations':[],
        'sources':{'trace.jsonl':sha(destination/'trace.jsonl'),
                   'road.xodr':sha(destination/'road.xodr')},
        'synthetic_diagnostic':True})+'\n')
    for camera in config['cameras']:
        size=f"{camera['width']}x{camera['height']}"
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                        '-f','lavfi','-i',f'color=c=black:s={size}:r=20:d=12',
                        '-frames:v','240','-c:v','ffv1','-threads','1',
                        str(destination/(camera['name']+'.mkv'))],
                       check=True,env=env,timeout=120)
    return construction,config


def main():
    env=dict(os.environ)
    env['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    env['PYTHONPATH']=os.pathsep.join((str(ROOT/'runtime/pipeline/scenario_pipeline'),
        str(ROOT/'runtime/pipeline/python'),str(ROOT/'runtime/pipeline'),
        str(HERE/'native'),env.get('PYTHONPATH','')))
    retained=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c10316-retained-saved-'))
    records=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c10316-saved-') as temporary:
        scratch=Path(temporary)
        for suffix in ('reference','contrast'):
            base=scratch/(suffix+'-base')
            _,config=make_base(base,suffix,env)
            positive,missing,wrong,video=(scratch/(suffix+label) for label in
                ('-positive','-missing','-wrong-footprint','-missing-video'))
            for dest in (positive,missing,wrong,video):shutil.copytree(base,dest)
            before=source_hashes(positive)
            command=[sys.executable,str(HERE/'native/finalize.py'),
                     '--attempt',str(positive),'--output',str(positive/'analysis-report.json')]
            success=subprocess.run(command,env=env,text=True,stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,timeout=180)
            if success.returncode:raise RuntimeError('Saved positive failed: '+success.stdout)
            if source_hashes(positive)!=before:raise RuntimeError('Finalizer rewrote original source')
            report=json.loads((positive/'analysis-report.json').read_text())
            result=json.loads((positive/'result.json').read_text())
            contract=json.loads((HERE/'draft-crosswalk'/suffix/'measurement-contract.json').read_text())
            verify_report(contract,report,positive)
            assert result['accepted'] is False and result['legal_verdict_claimed'] is False
            assert result['behavior_attempted'] is False and result['maneuver_completed'] is False
            (missing/'native_samples.jsonl').unlink()
            wrong_rows=[json.loads(line) for line in (wrong/'capture/evidence.jsonl').read_text().splitlines()]
            wrong_rows[10]['ego']['body_vertices_m'][0][0]+=1
            write_rows(wrong/'capture/evidence.jsonl',wrong_rows)
            (video/'overview.mkv').unlink()
            errors=[]
            for folder,expected in ((missing,'Missing required source: native_samples.jsonl'),
                                    (wrong,'Original pedestrian footprint differs'),
                                    (video,'Missing required source: overview.mkv')):
                failure=subprocess.run([sys.executable,str(HERE/'native/finalize.py'),
                    '--attempt',str(folder),'--output',str(folder/'analysis-report.json')],
                    env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
                if failure.returncode==0 or expected not in failure.stdout:
                    raise RuntimeError('Saved negative did not reject: '+failure.stdout)
                errors.append(expected)
            for label,folder in (('positive',positive),('missing',missing),
                                 ('wrong-footprint',wrong),('missing-video',video)):
                shutil.copytree(folder,retained/(suffix+'-'+label))
            records.append({'case_id':result['case_id'],'case_suffix':suffix,
                            'frames':240,'positive_exit_code':0,
                            'negative_exit_codes':[1,1,1],'negative_errors':errors,
                            'observed_half':report['measurements']['right_half_passage']['value']['observed_half'],
                            'video_sources_decoded':4,'source_unchanged':True,
                            'retained_positive':str(retained/(suffix+'-positive')),
                            'original_source_hashes':before,
                            'analysis_report_sha256':sha(positive/'analysis-report.json'),
                            'result_sha256':sha(positive/'result.json'),
                            'scope':'240-frame synthetic saved diagnostic; no Native or accepted recording'})
    (HERE/'saved-crosswalk-summary.json').write_text(json.dumps({
        'format':'c10316-retained-synthetic-saved-proof-v1',
        'retained_root':str(retained),'records':records},indent=2)+'\n')
    print(json.dumps({'cases':2,'frames_per_case':240,'video_sources_per_case':4,
                      'negative_rejections':6,'accepted_recordings':0},sort_keys=True))


if __name__=='__main__':main()
