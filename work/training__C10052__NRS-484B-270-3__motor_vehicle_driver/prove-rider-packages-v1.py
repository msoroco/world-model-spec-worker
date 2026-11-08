"""Exact unselected rider bundles through full synthetic v1 package processing."""
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

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from rider_engineering import ego_pose
from alley_geometry import open_drive
from worker_exchange.package_compatibility import run,materialize_case
from worker_exchange.runtime_cli import execution_env

spec=importlib.util.spec_from_file_location('saved_fixture',HERE/'saved-fixture-proof.py')
saved=importlib.util.module_from_spec(spec);spec.loader.exec_module(saved)
core_spec=importlib.util.spec_from_file_location('core_fixture',HERE/'probe-core-synthetic.py')
core=importlib.util.module_from_spec(core_spec);core_spec.loader.exec_module(core)
MANIFEST=HERE/'draft-rider-execution-manifest.json'
PROTOTYPE=ROOT/'.runtime-work/c10052-rider-yield-timing'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows))


def prepare(root):
    package=root/'package';package.mkdir()
    shutil.copyfile(MANIFEST,package/MANIFEST.name)
    shutil.copytree(HERE/'draft-rider-cases',package/'draft-rider-cases')
    proposals=[]
    for entry in json.loads(MANIFEST.read_text())['cases']:
        bundle=json.loads((HERE/entry['construction']).read_text())
        config=json.loads(next(f['content'] for f in bundle['files'] if f['path']=='config.json'))
        proposals.append({'case_id':entry['case_id'],'target_law_id':'NRS-484B-270-3',
            'target_type':'rider_yield_timing_probe','cell_id':'C10052',
            'actor':'motor_vehicle_driver','recording_description':config['recording_description'],
            'sweep_measurements':[],'comparison_variable':'ego_entry_relative_to_rider_clearance',
            'status':'unselected_synthetic_diagnostic'})
    (package/'proposals').mkdir()
    (package/'proposals/cases.json').write_text(json.dumps({'cases':proposals})+'\n')
    return package/MANIFEST.name


def fixture(root,rider_type,response):
    folder=root/'fixture'
    saved.make_base(folder,'probe_b',full_resolution=True)
    source=PROTOTYPE/(rider_type+'-'+response)
    rider_rows=[json.loads(line) for line in (source/'native_rider_ego_samples.jsonl').read_text().splitlines()]
    assert len(rider_rows)==480
    base_mapping=saved.rows(folder/'video_frames.jsonl')
    native=[];trace=[];evidence=[];history=[];mapping=[]
    for index,(rider,base) in enumerate(zip(rider_rows,base_mapping)):
        pose=ego_pose(index,response)
        frame,time=base['native_frame'],base['time_s']
        center=pose['center_xy'];body=pose['body_xy'];heading=pose['forward_xy']
        lane=-2 if -5<=center[1]<-3 else -1
        motion={'native_frame':frame,'time_s':time,'native_center_xy_m':center,
            'native_forward_xy':heading,'native_body_xy_m':body,
            'native_road_id':pose['road_id'],'native_lane_id':lane,
            'speed_mps':pose['speed_mps'],'synthetic_diagnostic':True}
        native.append(motion)
        rider.update(native_frame=frame,time_s=time,ego_body_xy=body,
                     ego_speed_mps=pose['speed_mps'],ego_native_road_id=pose['road_id'])
        xyz=[[x,y,z] for x,y in body for z in (0,1.5)]
        trace.append({'frame':frame,'time_s':time,
            'position':{'x':center[0],'y':center[1],'z':.5},
            'heading_deg':math.degrees(math.atan2(heading[1],heading[0])),
            'speed_mps':pose['speed_mps']})
        evidence.append({'original_frame':frame,'recording_time_s':time,
                         'ego':{'body_vertices_m':xyz}})
        history.append({'frame':frame,'time_s':time,'body_vertices_m':xyz})
        mapping.append({'video_frame':index,'native_frame':frame,
                        'carla_frame':frame,'time_s':time})
    for name,values in (('native_samples.jsonl',native),('rider_native_samples.jsonl',rider_rows),
        ('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
        ('body_history.jsonl',history),('video_frames.jsonl',mapping)):
        write(folder/name,values)
    shutil.copyfile(PROTOTYPE/'geometry.json',folder/'rider_geometry.json')
    rider_manifest=json.loads((source/'rider-source-manifest.json').read_text())
    rider_manifest.update(samples_sha256=sha(folder/'rider_native_samples.jsonl'),
                          geometry_sha256=sha(folder/'rider_geometry.json'))
    (folder/'rider-source-manifest.json').write_text(json.dumps(rider_manifest,indent=2)+'\n')
    (folder/'facility.mkv').rename(folder/'reference_corner.mkv')
    core.enrich(folder)
    (folder/'road.xodr').write_text(open_drive())
    capture=json.loads((folder/'capture/manifest.json').read_text())
    capture['sources']['road.xodr']=sha(folder/'road.xodr')
    (folder/'capture/manifest.json').write_text(json.dumps(capture)+'\n')
    geometry=json.loads((folder/'road_geometry.json').read_text())
    entry=next(e for e in json.loads(MANIFEST.read_text())['cases']
               if e['case_id'].endswith('__rider_'+rider_type+'_'+response))
    exact=json.loads((HERE/entry['construction']).read_text())
    channel_names=[c['name'] for c in exact['recording_description']['channels']]
    for name in channel_names:
        values=[]
        for index,(ego,rider) in enumerate(zip(native,rider_rows)):
            if name in ('st.bicycle_lane_or_path','st.driveway_or_alley_entrance'):value=geometry
            elif name=='rel.occupies':value=ego['native_body_xy_m']
            elif name=='kin.extent':value={'body_xy_m':ego['native_body_xy_m']}
            elif name=='kin.position':value=ego['native_center_xy_m']
            elif name=='ego_speed':value=ego['speed_mps']
            elif name=='drv.standing_or_parked':value={'observed_speed_mps':ego['speed_mps']}
            elif name=='ru.pedestrian':value={'native_actor_id':1,'synthetic_diagnostic':True}
            elif name=='ru.'+rider_type:value={'native_actor_id':rider['rider_actor_id'],
                'native_body_xy_m':rider['rider_body_xy'],'synthetic_diagnostic':True}
            elif name=='exception_context':value={'source':'exception_context.json','observed_exception_status':'unresolved'}
            elif name=='native_body_pose_control':value=ego
            elif name=='camera_frame_join':value=mapping[index]
            else:raise ValueError('Unknown rider channel '+name)
            values.append({'time_s':ego['time_s'],'value':value})
        write(folder/'channels'/(name+'.jsonl'),values)
    (folder/'config.json').unlink()
    return folder


def main():
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    parser=argparse.ArgumentParser()
    parser.add_argument('--rider',choices=('bicycle','electric_bicycle','electric_scooter'),required=True)
    parser.add_argument('--response',choices=('clear','conflict'),required=True)
    parser.add_argument('--candidate',choices=('primary','fallback1','fallback2','fallback3'),required=True)
    args=parser.parse_args()
    root=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c10052-rider-v1-'))
    manifest=prepare(root)
    case=HERE.name+'__rider_'+args.rider+'_'+args.response
    source=fixture(root,args.rider,args.response)
    output=root/'positive'
    receipt=run(manifest,case,source,output,ROOT/'runtime/pipeline/library',
        ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',args.candidate)
    analysis=json.loads((output/'analysis-report.json').read_text())
    metric=analysis['measurements']['rider_conflict_observation']['value']
    assert metric['ego_entered_after_rider_cleared']==(args.response=='clear')
    assert receipt['passed'] and analysis['accepted'] is False
    negative=root/'negative'
    materialize_case(manifest,case,negative,source,args.candidate)
    with (negative/'rider_native_samples.jsonl').open('a') as stream:stream.write(' ')
    command=[sys.executable,str(negative/'finalize_rider.py'),'--attempt',str(negative),
             '--output',str(negative/'analysis-report.json')]
    failure=subprocess.run(command,cwd=negative,env=execution_env(),text=True,
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    log=root/'negative.log';log.write_text(failure.stdout)
    assert failure.returncode!=0 and 'Changed original source bytes' in failure.stdout
    assert not (negative/'result.json').exists()
    summary={'format':'c10052-rider-unselected-exact-v1-probe','passed':True,
        'case_id':case,'candidate_id':args.candidate,'manifest_sha256':sha(MANIFEST),
        'construction_sha256':receipt['construction_sha256'],
        'source_root':source.relative_to(ROOT).as_posix(),
        'output_root':output.relative_to(ROOT).as_posix(),
        'positive_receipt_sha256':sha(output/'compatibility.json'),
        'negative_exit_code':failure.returncode,'negative_log_sha256':sha(log),
        'first_ego_frame':metric['first_ego_frame'],
        'last_rider_frame':metric['last_rider_frame'],
        'simultaneous_conflict_frames':metric['simultaneous_conflict_frames'],
        'selected':False,'accepted':False,'original_native_capture_executed':False}
    path=HERE/('rider-package-'+args.rider+'-'+args.response+'-'+args.candidate+'.json')
    path.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
