"""Exercise exact unselected exception_c bundles with synthetic saved acquisition."""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE/'native'))
sys.path.insert(0, str(ROOT/'runtime/pipeline/scenario_pipeline'))
from exception_c_engineering import policy, measure, triggers
from exception_c_geometry import open_drive
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env

def module(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE/file)
    item = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(item)
    return item

saved = module('exception_c_saved_fixture', 'saved-fixture-proof.py')
core = module('exception_c_core_fixture', 'probe-core-synthetic.py')
MANIFEST = HERE/'draft-exception-c-execution-manifest.json'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True, allow_nan=False)+'\n' for row in values))

def prepare(root):
    package = root/'package'
    package.mkdir()
    shutil.copyfile(MANIFEST, package/MANIFEST.name)
    shutil.copytree(HERE/'draft-exception-c-exact-cases', package/'draft-exception-c-exact-cases')
    proposals = []
    for entry in json.loads(MANIFEST.read_text())['cases']:
        bundle = json.loads((HERE/entry['construction']).read_text())
        config = json.loads(next(f['content'] for f in bundle['files'] if f['path']=='config.json'))
        proposals.append({'case_id':entry['case_id'],'target_law_id':'NRS-484B-270-3',
            'target_type':'other_traffic_conflict_avoidance_probe','cell_id':'C10052',
            'actor':'motor_vehicle_driver','recording_description':config['recording_description'],
            'sweep_measurements':[],'comparison_variable':'conflicting_traffic_presence_and_ego_diversion',
            'status':'unselected_synthetic_diagnostic'})
    (package/'proposals').mkdir()
    (package/'proposals/cases.json').write_text(json.dumps({'cases':proposals})+'\n')
    return package/MANIFEST.name

def fixture(root, response, candidate):
    folder = root/'fixture'
    saved.make_base(folder, 'probe_b', full_resolution=True)
    source = HERE/'draft-exception-c-cases'/response/candidate
    traffic = saved.rows(source/'source-rows.jsonl')
    assert len(traffic)==480
    motion=[]; trace=[]; evidence=[]; history=[]; mapping=[]
    for index,row in enumerate(traffic):
        frame,time=row['native_frame'],row['time_s']
        body=row['ego_body_xy'];center=row['ego_center_xy']
        speed=0.0 if index==0 else round(math.dist(center,motion[-1]['native_center_xy_m'])*20,4)
        native={'native_frame':frame,'time_s':time,'native_center_xy_m':center,
            'native_forward_xy':[1,0],'native_body_xy_m':body,'native_road_id':1,
            'native_lane_id':-2 if -5<=center[1]<-3 else -1,
            'speed_mps':speed,'synthetic_diagnostic':True}
        motion.append(native)
        vertices=[[x,y,z] for x,y in body for z in (0,1.5)]
        trace.append({'frame':frame,'time_s':time,'position':{'x':center[0],'y':center[1],'z':.5},
            'heading_deg':0,'speed_mps':speed})
        evidence.append({'original_frame':frame,'recording_time_s':time,
            'ego':{'body_vertices_m':vertices}})
        history.append({'frame':frame,'time_s':time,'body_vertices_m':vertices})
        mapping.append({'video_frame':index,'native_frame':frame,'carla_frame':frame,'time_s':time})
    for name,values in (('native_samples.jsonl',motion),('exception_c_native_samples.jsonl',traffic),
        ('trace.jsonl',trace),('capture/evidence.jsonl',evidence),('body_history.jsonl',history),
        ('video_frames.jsonl',mapping)):
        write_rows(folder/name,values)
    (folder/'exception-c-source-manifest.json').write_text(json.dumps({
        'source_kind':'synthetic_cpu_fixture','accepted':False,
        'samples_sha256':sha(folder/'exception_c_native_samples.jsonl')},sort_keys=True)+'\n')
    (folder/'facility.mkv').rename(folder/'reference_corner.mkv')
    core.enrich(folder)
    (folder/'road.xodr').write_text(open_drive())
    capture=json.loads((folder/'capture/manifest.json').read_text())
    capture['sources']['road.xodr']=sha(folder/'road.xodr')
    (folder/'capture/manifest.json').write_text(json.dumps(capture)+'\n')
    entry=next(e for e in json.loads(MANIFEST.read_text())['cases']
               if e['case_id'].endswith('__exception_c_'+response))
    exact=json.loads((HERE/entry['construction']).read_text())
    geometry=json.loads((folder/'road_geometry.json').read_text())
    for channel in exact['recording_description']['channels']:
        name=channel['name']; values=[]
        for index,(ego,traffic_row) in enumerate(zip(motion,traffic)):
            if name in ('st.bicycle_lane_or_path','st.driveway_or_alley_entrance'): value=geometry
            elif name=='rel.occupies':value=ego['native_body_xy_m']
            elif name=='kin.extent':value={'body_xy_m':ego['native_body_xy_m']}
            elif name=='kin.position':value=ego['native_center_xy_m']
            elif name=='ego_speed':value=ego['speed_mps']
            elif name=='drv.standing_or_parked':value={'observed_speed_mps':ego['speed_mps']}
            elif name=='ru.vehicle':value={'native_actor_id':traffic_row['conflict_actor_id'],
                'native_body_xy_m':traffic_row['conflict_actor_body_xy'],'synthetic_diagnostic':True}
            elif name=='exception_context':value={'source':'exception_context.json','observed_exception_status':'unresolved'}
            elif name=='native_body_pose_control':value=ego
            elif name=='camera_frame_join':value=mapping[index]
            else:raise ValueError('Unknown traffic channel '+name)
            values.append({'time_s':ego['time_s'],'value':value})
        write_rows(folder/'channels'/(name+'.jsonl'),values)
    (folder/'config.json').unlink()
    return folder

def main():
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    parser=argparse.ArgumentParser()
    parser.add_argument('--response',choices=('avoid','no_conflict'),required=True)
    parser.add_argument('--candidate',choices=('primary','fallback1','fallback2','fallback3'),required=True)
    args=parser.parse_args()
    root=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c10052-exception_c-v1-'))
    manifest=prepare(root)
    case=HERE.name+'__exception_c_'+args.response
    source=fixture(root,args.response,args.candidate)
    output=root/'positive'
    receipt=run(manifest,case,source,output,ROOT/'runtime/pipeline/library',
        ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',args.candidate)
    report=json.loads((output/'analysis-report.json').read_text())
    measured=report['measurements']
    assert receipt['passed'] and report['accepted'] is False
    assert measured['actual_collision_frames']==0
    negative=root/'negative'
    materialize_case(manifest,case,negative,source,args.candidate)
    with (negative/'exception_c_native_samples.jsonl').open('a') as stream:stream.write(' ')
    command=[sys.executable,str(negative/'finalize_exception_c.py'),'--attempt',str(negative),
             '--output',str(negative/'analysis-report.json')]
    failure=subprocess.run(command,cwd=negative,env=execution_env(),text=True,
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    (root/'negative.log').write_text(failure.stdout)
    assert failure.returncode!=0 and 'Synthetic conflict source hash differs' in failure.stdout
    assert not (negative/'result.json').exists()
    candidate_policy=policy(args.response,args.candidate)
    source_rows=saved.rows(source/'exception_c_native_samples.jsonl')
    trigger_result=triggers(source_rows,candidate_policy)
    summary={'format':'c10052-exception-c-unselected-exact-v1-probe','passed':True,
        'case_id':case,'candidate_id':args.candidate,'manifest_sha256':sha(MANIFEST),
        'construction_sha256':receipt['construction_sha256'],
        'source_root':source.relative_to(ROOT).as_posix(),
        'output_root':output.relative_to(ROOT).as_posix(),
        'positive_receipt_sha256':sha(output/'compatibility.json'),
        'negative_exit_code':failure.returncode,'negative_log_sha256':sha(root/'negative.log'),
        'actual_collision_frames':measured['actual_collision_frames'],
        'synthetic_avoidance_geometry':measured['synthetic_avoidance_geometry'],
        'triggers':trigger_result,'selected':False,'accepted':False,
        'original_native_capture_executed':False}
    path=HERE/('exception-c-package-'+args.response+'-'+args.candidate+'.json')
    path.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=='__main__':main()
