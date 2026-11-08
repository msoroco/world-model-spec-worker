"""Exercise four exact no-entry bundles through full synthetic v1 processing."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.package_compatibility import run,materialize_case
from worker_exchange.runtime_cli import execution_env
from alley_geometry import open_drive

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value

saved=module('no_entry_saved_base',HERE/'prove-alley-saved.py')
core=module('no_entry_core',HERE/'probe-core-synthetic.py')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
def write_rows(path,values):path.write_text(''.join(json.dumps(v,allow_nan=False)+'\n' for v in values))

def prepare(root):
    package=root/'package';package.mkdir()
    manifest=HERE/'draft-no-entry-execution-manifest.json'
    shutil.copyfile(manifest,package/manifest.name)
    shutil.copytree(HERE/'draft-no-entry-candidates',package/'draft-no-entry-candidates')
    construction=json.loads((HERE/'draft-no-entry-candidates/probe_d_no_entry/primary/construction.json').read_text())
    config=json.loads(next(item['content'] for item in construction['files'] if item['path']=='config.json'))
    proposal={'case_id':config['case_id'],'target_law_id':'NRS-484B-270-3',
        'target_type':'exact_clause','cell_id':'C10052','actor':'motor_vehicle_driver',
        'recording_description':config['recording_description'],'sweep_measurements':[],
        'comparison_variable':'moving_facility_entry','requested_setting':'straight driving lane',
        'status':'unselected_synthetic_diagnostic'}
    (package/'proposals').mkdir()
    (package/'proposals/cases.json').write_text(json.dumps({'cases':[proposal]})+'\n')
    return package/manifest.name,config['case_id']

def fixture(root,candidate):
    folder=root/'fixture'
    saved.build(folder,full_resolution=True)
    trigger_root=HERE/'no-entry-trigger-sources'/candidate
    original=rows(trigger_root/'native_samples.jsonl')
    geometry=trigger_root/'road_geometry.json'
    shutil.copyfile(geometry,folder/'road_geometry.json')
    trace=[];evidence=[];history=[];mapping=[]
    for index,row in enumerate(original):
        frame,time=row['native_frame'],row['time_s']
        x,y=row['native_center_xy_m']
        body=[[a,b,z] for a,b in row['native_body_xy_m'] for z in (0,1.5)]
        trace.append({'frame':frame,'time_s':time,'position':{'x':x,'y':y,'z':.5},
                      'heading_deg':0.0,'speed_mps':row['speed_mps']})
        evidence.append({'original_frame':frame,'recording_time_s':time,
                         'ego':{'body_vertices_m':body}})
        history.append({'frame':frame,'time_s':time,'body_vertices_m':body})
        mapping.append({'video_frame':index,'native_frame':frame,'carla_frame':frame,'time_s':time})
    for name,values in (('native_samples.jsonl',original),('trace.jsonl',trace),
        ('capture/evidence.jsonl',evidence),('body_history.jsonl',history),
        ('video_frames.jsonl',mapping)):
        write_rows(folder/name,values)
    entry_source={'format':'c10052-entry-sources-v1',
                  'source_kind':'synthetic_cpu_fixture',
                  'sha256':{name:sha(folder/name) for name in
                            ('native_samples.jsonl','road_geometry.json')}}
    (folder/'entry-sources.json').write_text(json.dumps(entry_source)+'\n')
    shutil.copyfile(trigger_root/'camera_visibility.jsonl',
                    folder/'camera_visibility.jsonl')
    trigger_source={'format':'c10052-no-entry-trigger-sources-v1',
                    'source_kind':'synthetic_cpu_fixture',
                    'sha256':{name:sha(folder/name) for name in
                              ('native_samples.jsonl','road_geometry.json','camera_visibility.jsonl')}}
    (folder/'no-entry-trigger-sources.json').write_text(json.dumps(trigger_source)+'\n')
    (folder/'alley-transition-sources.json').unlink()
    for channel in (folder/'channels').glob('*.jsonl'):
        name=channel.stem
        values=rows(channel)
        for index,value in enumerate(values):
            row=original[index]
            if name=='rel.occupies':value['value']=row['native_body_xy_m']
            elif name=='kin.extent':value['value']={'body_xy_m':row['native_body_xy_m']}
            elif name=='kin.position':value['value']=row['native_center_xy_m']
            elif name=='ego_speed':value['value']=row['speed_mps']
            elif name=='drv.standing_or_parked':value['value']={'observed_speed_mps':row['speed_mps']}
            elif name=='native_body_pose_control':value['value']=row
            elif name=='camera_frame_join':value['value']=mapping[index]
            value['time_s']=row['time_s']
        write_rows(channel,values)
    core.enrich(folder)
    (folder/'road.xodr').write_text(open_drive())
    manifest=json.loads((folder/'capture/manifest.json').read_text())
    manifest['sources']['road.xodr']=sha(folder/'road.xodr')
    (folder/'capture/manifest.json').write_text(json.dumps(manifest)+'\n')
    (folder/'config.json').unlink()
    return folder

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--candidate',choices=('primary','fallback1','fallback2','fallback3'),default='primary')
    args=parser.parse_args()
    root=Path(tempfile.mkdtemp(dir=REPO/'.runtime-work',prefix='c10052-no-entry-v1-'))
    manifest,case=prepare(root);source=fixture(root,args.candidate)
    positive=root/'positive'
    receipt=run(manifest,case,source,positive,REPO/'runtime/pipeline/library',
        REPO/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',args.candidate)
    result=json.loads((positive/'result.json').read_text())
    if result['measured_values']['moving_entry_measured'] or result['measured_values']['moving_occupied_frames']:
        raise ValueError('No-entry package yielded moving facility occupancy')
    triggers=json.loads((positive/'analysis-report.json').read_text())['measurements']['no_entry_fallback_triggers']
    expected={'primary':(42.0,2.5,.866667),
              'fallback1':(52.0,2.5,.863415),
              'fallback2':(42.0,1.8,.866667),
              'fallback3':(42.0,2.5,1.0)}[args.candidate]
    if (tuple(triggers[key] for key in
              ('approach_runway_to_alley_m','peak_approach_speed_mps',
               'reference_body_visibility_fraction'))!=expected or
        any(result['measured_values'][key]!=triggers[key] for key in
            ('approach_runway_to_alley_m','peak_approach_speed_mps',
             'reference_body_visibility_fraction','fallback1_trigger_measured',
             'fallback2_trigger_measured','fallback3_trigger_measured'))):
        raise ValueError('Exact package fallback trigger measurement differs')
    negative=root/'negative'
    materialize_case(manifest,case,negative,source,args.candidate)
    (negative/'entry-sources.json').unlink()
    failure=subprocess.run([sys.executable,str(negative/'finalize_no_entry.py'),
        '--attempt',str(negative),'--output',str(negative/'analysis-report.json')],
        cwd=negative,env=execution_env(),text=True,stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,timeout=300)
    (root/'negative.log').write_text(failure.stdout)
    if failure.returncode==0 or 'entry-sources.json' not in failure.stdout:
        raise ValueError('Exact no-entry missing-source negative did not reject')
    trigger_negative=root/'trigger-negative'
    materialize_case(manifest,case,trigger_negative,source,args.candidate)
    (trigger_negative/'no-entry-trigger-sources.json').unlink()
    trigger_failure=subprocess.run([sys.executable,str(trigger_negative/'finalize_no_entry.py'),
        '--attempt',str(trigger_negative),'--output',str(trigger_negative/'analysis-report.json')],
        cwd=trigger_negative,env=execution_env(),text=True,stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,timeout=300)
    (root/'trigger-negative.log').write_text(trigger_failure.stdout)
    if trigger_failure.returncode==0 or 'no-entry-trigger-sources.json' not in trigger_failure.stdout:
        raise ValueError('Exact no-entry missing trigger source negative did not reject')
    summary={'format':'c10052-no-entry-unselected-exact-v1-probe',
        'source_root':root.relative_to(REPO).as_posix(),'candidate_id':args.candidate,
        'manifest_sha256':sha(manifest),'construction_sha256':receipt['construction_sha256'],
        'fixture_sha256':receipt['fixture_sha256'],
        'positive_receipt_sha256':sha(positive/'compatibility.json'),
        'positive_analysis_sha256':sha(positive/'analysis-report.json'),
        'negative_exit_code':failure.returncode,'negative_log_sha256':sha(root/'negative.log'),
        'trigger_negative_exit_code':trigger_failure.returncode,
        'trigger_negative_log_sha256':sha(root/'trigger-negative.log'),
        'selected':False,'accepted':False}
    (HERE/('no-entry-package-'+args.candidate+'-summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
