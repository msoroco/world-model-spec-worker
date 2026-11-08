"""Run exact copied C131364 positives and altered-source negatives."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CASE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(folder):
    return subprocess.run([sys.executable,str(folder/'runner.py'),'--check',
                           '--bundle',str(folder)],capture_output=True,text=True,timeout=20)

def saved_run(folder,script,witness=None):
    cmd=[sys.executable,str(folder/script)]
    if witness:cmd.append(str(folder/'saved-fixtures'/witness))
    return subprocess.run(cmd,capture_output=True,text=True,timeout=20)

def prepared_run(folder,raw,output):
    return subprocess.run([sys.executable,str(folder/'prepare_connected_raw.py'),
        '--bundle',str(folder),'--raw-folder',str(raw),
        '--output-dir',str(output),'--synthetic-cpu'],
        capture_output=True,text=True,timeout=20)

def prove():
    manifest_path=CASE/'offline'/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    positives=[];negatives=[];saved_positives=[];saved_negatives=[]
    for entry in manifest['entries']:
        folder=CASE/entry['bundle']
        if entry['sha256']!={name:sha(folder/name) for name in entry['sha256']}:
            raise ValueError('C131364 copied bytes differ')
        result=run(folder)
        if result.returncode!=0:raise AssertionError(result.stderr)
        checked=json.loads(result.stdout)
        if checked['requested_frames']!=240 or checked['delivery_ready'] or checked['actual_exit_observed']:
            raise AssertionError('C131364 copied checker overclaims')
        positives.append({'case_id':entry['case_id'],'candidate_id':entry['candidate_id'],
                          'config_sha256':sha(folder/'config.json'),'passed':True})
        witness=entry['case_id'].removeprefix(CASE.name+'__')
        for script in ('measure_saved.py','triggers.py','compare_saved.py'):
            receipt=saved_run(folder,script,witness if script!='compare_saved.py' else None)
            if receipt.returncode!=0 or json.loads(receipt.stdout)['delivery_ready']:
                raise AssertionError('C131364 copied saved CPU check failed')
            saved_positives.append({'case_id':entry['case_id'],
                                    'candidate_id':entry['candidate_id'],
                                    'script':script,'passed':True})
        connected=subprocess.run([sys.executable,str(folder/'measure_exit_saved.py'),str(folder)],
                                 capture_output=True,text=True,timeout=20)
        if connected.returncode!=0 or json.loads(connected.stdout)['delivery_ready']:
            raise AssertionError('C131364 connected saved CPU check failed: '+connected.stderr)
        saved_positives.append({'case_id':entry['case_id'],'candidate_id':entry['candidate_id'],
                                'script':'measure_exit_saved.py','passed':True})
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            base=Path(temporary);raw=base/'raw'
            generated=subprocess.run([sys.executable,str(folder/'fixture_connected_raw.py'),
                '--bundle',str(folder),'--output-dir',str(raw)],
                capture_output=True,text=True,timeout=20)
            if generated.returncode:raise AssertionError(generated.stderr)
            prepared=prepared_run(folder,raw,base/'saved')
            if prepared.returncode:raise AssertionError(prepared.stderr)
            receipt=json.loads(prepared.stdout)
            if receipt['source_kind']!='synthetic_cpu' or receipt['delivery_ready']:
                raise AssertionError('C131364 raw-to-saved positive differs')
            saved_positives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],
                'script':'prepare_connected_raw.py','passed':True})
            path=raw/'video_frames.jsonl';lines=path.read_text().splitlines()
            changed=json.loads(lines[51]);changed['native_frame']+=1
            lines[51]=json.dumps(changed);path.write_text('\n'.join(lines)+'\n')
            if prepared_run(folder,raw,base/'rejected').returncode==0:
                raise AssertionError('C131364 altered raw frame map accepted')
            saved_negatives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],
                'mutation':'changed_raw_frame_map','rejected':True})
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
            path=altered/'saved-fixtures'/witness/'lane-readback.json'
            changed=json.loads(path.read_text());changed['left_lane_id']=-2
            path.write_text(json.dumps(changed)+'\n')
            for script in ('measure_saved.py','triggers.py','compare_saved.py'):
                if saved_run(altered,script,witness if script!='compare_saved.py' else None).returncode==0:
                    raise AssertionError('C131364 changed lane readback accepted')
            saved_negatives.append({'case_id':entry['case_id'],
                                    'candidate_id':entry['candidate_id'],
                                    'mutation':'changed_lane_readback','rejected':True})
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
            path=altered/'connected-saved'/'camera-frames.jsonl'
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            rows[80]['camera_frame']+=1
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            receipt=subprocess.run([sys.executable,str(altered/'measure_exit_saved.py'),str(altered)],
                                   capture_output=True,text=True,timeout=20)
            if receipt.returncode==0:raise AssertionError('C131364 changed connected camera join accepted')
            saved_negatives.append({'case_id':entry['case_id'],'candidate_id':entry['candidate_id'],
                                    'mutation':'changed_connected_camera_join','rejected':True})
        for mutation,name in (('track_bytes','requested-tracks.jsonl'),
                              ('assignment_bytes','assignment-source.json'),
                              ('road_bytes','road.xodr'),
                              ('connected_track_bytes','connected-requested-tracks.jsonl'),
                              ('connected_road_bytes','connected-road.xodr')):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
                path=altered/name;path.write_bytes(path.read_bytes()+b' ')
                if run(altered).returncode==0:
                    raise AssertionError(f'C131364 changed {name} accepted')
                negatives.append({'case_id':entry['case_id'],
                                  'candidate_id':entry['candidate_id'],
                                  'mutation':mutation,'rejected':True})
    proof={'format':'c131364-compatibility-proof-v1','assignment_id':CASE.name,
           'manifest_sha256':sha(manifest_path),'positives':positives,
           'negatives':negatives,'saved_positives':saved_positives,
           'saved_negatives':saved_negatives,'original_native_observed':False,
           'delivery_ready':False}
    (CASE/'offline'/'proof-compatibility.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof

if __name__=='__main__':
    result=prove();print(json.dumps({'positives':len(result['positives']),
                                     'negatives':len(result['negatives'])}))
