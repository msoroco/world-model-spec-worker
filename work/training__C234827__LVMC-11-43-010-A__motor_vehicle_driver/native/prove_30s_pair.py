"""Audit 600-frame request isolation and reject changed source rows."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]


def prove():
    a=HERE/'30s/witness_1';b=HERE/'30s/witness_2'
    ra=rows(a/'requested-tracks.jsonl')
    rb=rows(b/'requested-tracks.jsonl')
    assert len(ra)==len(rb)==600
    assert ra[0]['island_center_xy_m']==rb[0]['island_center_xy_m']==[0,0]
    assert all(x['ego_speed_mps']==y['ego_speed_mps']==8 for x,y in zip(ra,rb))
    assert all(x['requested_radius_m']==y['requested_radius_m']==23.75 for x,y in zip(ra,rb))
    assert all(x['time_s']==y['time_s']==(i+1)/20 for i,(x,y) in enumerate(zip(ra,rb)))
    assert all(x['requested_rotation_sign']==1 and y['requested_rotation_sign']==-1 for x,y in zip(ra,rb))
    assert abs(ra[0]['ego_x_m']+rb[0]['ego_x_m'])<1e-5
    assert abs(ra[0]['ego_y_m']-rb[0]['ego_y_m'])<1e-5
    assert ra[0]['requested_unwrapped_angle_rad']<ra[-1]['requested_unwrapped_angle_rad']
    assert rb[0]['requested_unwrapped_angle_rad']>rb[-1]['requested_unwrapped_angle_rad']
    assert abs(ra[-1]['requested_unwrapped_angle_rad']-ra[0]['requested_unwrapped_angle_rad'])>2*math.pi
    assert abs(rb[-1]['requested_unwrapped_angle_rad']-rb[0]['requested_unwrapped_angle_rad'])>2*math.pi
    scratch=ROOT/'.runtime-work/c234827-30s'
    scratch.mkdir(parents=True,exist_ok=True)
    negatives=[]
    with tempfile.TemporaryDirectory(dir=scratch) as tmp:
        for name in ('removed_frame','wrong_rotation','changed_assignment'):
            dest=Path(tmp)/name;dest.mkdir()
            for filename in ('capture.py','config.json','assignment-source.json','case-plan.json','requested-tracks.jsonl'):
                shutil.copy2(ROOT/'.runtime-work/c234827-30s/pinned-w1-001'/filename,dest/filename)
            if name=='removed_frame':
                path=dest/'requested-tracks.jsonl';path.write_text('\n'.join(path.read_text().splitlines()[:-1])+'\n')
            elif name=='wrong_rotation':
                path=dest/'requested-tracks.jsonl';data=rows(path);data[90]['requested_rotation_sign']=-1
                path.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in data))
            else:
                path=dest/'assignment-source.json';path.write_bytes(path.read_bytes()+b' ')
            result=subprocess.run([sys.executable,str(dest/'capture.py'),'--check'],
                                  cwd=dest,capture_output=True,text=True,timeout=30)
            if result.returncode==0:raise AssertionError('Altered 30-second source accepted: '+name)
            negatives.append({'mutation':name,'rejected':True})
    manifest=CASE/'draft-30s-execution-manifest.json'
    receipt={'format':'c234827-30-second-controlled-pair-proof-v1',
             'assignment_sha256':sha(ROOT/'inputs'/CASE.name/'assignment.json'),
             'manifest_sha256':sha(manifest),'track_sha256':{
                 'witness_1':sha(a/'requested-tracks.jsonl'),
                 'witness_2':sha(b/'requested-tracks.jsonl')},
             'requested_frames_each':600,'duration_s_each':30,'rate_hz':20,
             'fixed_start_speed_radius_and_clock':True,
             'opposite_continuous_rotation_requests':True,
             'negative_controls':negatives,'passed':True,
             'original_native_observed':False,'delivery_ready':False}
    path=CASE/'offline/30s-pair-proof.json';path.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'passed':True,'negative_controls':len(negatives),'receipt_sha256':sha(path)}))


if __name__=='__main__':prove()
