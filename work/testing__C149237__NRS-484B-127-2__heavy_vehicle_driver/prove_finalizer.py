"""Positive and missing-source saved finalizer checks; no media decode claim."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
ROOT = REPO/'.runtime-work/c149237-finalizer-proof-v2'


def body(front):
    return [[front,1.1],[front,-1.1],[front-10,1.1],[front-10,-1.1]]


def fixture(root):
    root.mkdir(parents=True)
    (root/'capture').mkdir()
    (root/'config.json').write_bytes((FOLDER/'config.json').read_bytes())
    (root/'road_context.json').write_text(json.dumps({
        'native_map_id':'CPU-authored-one-way','road_id':149237,'lane_id':-1,
        'same_direction_lane_count':1,'lane_forward_xy':[1,0],
        'lane_count_source':'authored OpenDRIVE and diagnostic lane readback'})+'\n')
    rows=[]; frames=[]; trace=[]
    for i in range(3):
        frame=100+i; time=5+i*.05; x=100+i
        actor=lambda aid,front:{'actor_id':aid,'blueprint_id':'vehicle.carlamotors.european_hgv',
                                 'road_id':149237,'lane_id':-1,'overall_width_m':2.2,
                                 'is_truck_or_combination':True,'body_vertices_xy_m':body(front),
                                 'velocity_mps':[10,0,0]}
        rows.append({'frame':frame,'time_s':time,'ego':actor(1,x+10),
                     'lead':actor(2,x+170)})
        frames.append({'video_frame':i,'carla_frame':frame,'time_s':time})
        trace.append({'frame':frame,'time_s':time,'position_m':[x,0,0]})
    for name,items in (('truck_history.jsonl',rows),('video_frames.jsonl',frames),('trace.jsonl',trace)):
        (root/name).write_text(''.join(json.dumps(item)+'\n' for item in items))
    (root/'capture/evidence.jsonl').write_text('{}\n')
    for name in ('overview','approach','reference_corner','driver_reference'):
        (root/(name+'.mkv')).write_bytes(b'placeholder: finalizer checks source retention only')


def run(root):
    env=dict(os.environ)
    env['PYTHONPATH']=os.pathsep.join((str(FOLDER),str(REPO/'runtime/scenario_pipeline'),
                                     str(REPO/'runtime/python'),env.get('PYTHONPATH','')))
    return subprocess.run([sys.executable,str(FOLDER/'finalizer.py'),'--attempt',str(root),
                           '--output',str(root/'analysis-report.json')],cwd=REPO,env=env,
                          text=True,capture_output=True)


def main():
    if ROOT.exists():
        raise ValueError('Retain prior finalizer proof; select a fresh proof version')
    positive=ROOT/'positive'; negative=ROOT/'negative'
    fixture(positive); fixture(negative)
    passed=run(positive)
    if passed.returncode:
        raise ValueError('Positive saved finalizer failed: '+passed.stderr)
    report=json.loads((positive/'analysis-report.json').read_text())
    result=json.loads((positive/'result.json').read_text())
    if report['measurements']['minimum_sampled_body_gap_m']['value'] != 150:
        raise ValueError('Wrong source-bound truck gap')
    if result.get('legal_verdict') is not None or result.get('physical_acceptance_claimed') is True:
        raise ValueError('Fixture must not claim legal or physical acceptance')
    channel=positive/'channels/longitudinal_body_gap.jsonl'
    if [json.loads(line)['value'] for line in channel.read_text().splitlines()] != [150]*3:
        raise ValueError('Derived gap channel did not preserve original frames')
    (negative/'truck_history.jsonl').unlink()
    failed=run(negative)
    if failed.returncode == 0 or 'Missing required source: truck_history.jsonl' not in failed.stderr:
        raise ValueError('Missing original truck history was not rejected: '+failed.stderr)
    print(json.dumps({'format':'worker-truck-finalizer-cpu-proof',
                      'positive_report_sha256':hashlib.sha256((positive/'analysis-report.json').read_bytes()).hexdigest(),
                      'negative_error':'Missing required source: truck_history.jsonl',
                      'positive_exit_code':passed.returncode,'negative_exit_code':failed.returncode,
                      'source_camera_decode':'not tested here','physical_acceptance':False},indent=2))


if __name__=='__main__':
    main()
