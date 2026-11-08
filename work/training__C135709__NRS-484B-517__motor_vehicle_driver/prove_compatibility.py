"""Replay copied C135709 request positives and changed-source negatives."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CASE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(folder,script='check.py'):
    args=['--bundle',str(folder)] if script=='check.py' else [str(folder)]
    return subprocess.run([sys.executable,str(folder/script),*args],
        capture_output=True,text=True,timeout=20)
def run_args(folder,script,args):
    return subprocess.run([sys.executable,str(folder/script),*map(str,args)],
        capture_output=True,text=True,timeout=20)

def prove():
    manifest_path=CASE/'offline'/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    positives=[];negatives=[];saved_positives=[];saved_negatives=[]
    for entry in manifest['entries']:
        folder=CASE/entry['bundle']
        if entry['sha256']!={name:sha(folder/name) for name in entry['sha256']}:
            raise ValueError('C135709 copied bytes differ')
        result=run(folder)
        if result.returncode or json.loads(result.stdout)['delivery_ready']:
            raise AssertionError('C135709 copied request rejected or overclaimed: '+result.stderr)
        positives.append({'case_id':entry['case_id'],'candidate_id':entry['candidate_id'],
            'config_sha256':sha(folder/'config.json'),'passed':True})
        saved=run(folder,'measure_saved.py')
        if saved.returncode or json.loads(saved.stdout)['delivery_ready']:
            raise AssertionError('C135709 copied saved rejected or overclaimed: '+saved.stderr)
        saved_positives.append({'case_id':entry['case_id'],
            'candidate_id':entry['candidate_id'],'passed':True})
        routed=run(folder,'triggers.py')
        if routed.returncode or json.loads(routed.stdout)['delivery_ready']:
            raise AssertionError('C135709 copied trigger rejected or overclaimed: '+routed.stderr)
        saved_positives.append({'case_id':entry['case_id'],
            'candidate_id':entry['candidate_id'],'script':'triggers.py','passed':True})
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            raw=Path(temporary)/'raw';prepared=Path(temporary)/'prepared'
            fixture=run_args(folder,'fixture_raw.py',
                ['--bundle',folder,'--output-dir',raw])
            converted=run_args(folder,'prepare_raw.py',
                ['--bundle',folder,'--raw-folder',raw,
                 '--output-dir',prepared,'--synthetic-cpu']) if fixture.returncode==0 else fixture
            measured_raw=run_args(folder,'measure_prepared.py',
                ['--bundle',folder,'--saved-dir',prepared]) if converted.returncode==0 else converted
            if (fixture.returncode or converted.returncode or measured_raw.returncode or
                json.loads(converted.stdout)['delivery_ready'] or
                json.loads(measured_raw.stdout)['delivery_ready']):
                raise AssertionError('C135709 raw-to-saved proof failed: '+
                    fixture.stderr+converted.stderr+measured_raw.stderr)
            saved_positives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],
                'script':'prepare_raw.py + measure_prepared.py','passed':True})
            video=raw/'video_frames.jsonl';lines=video.read_text().splitlines()
            row=json.loads(lines[71]);row['native_frame']+=1
            lines[71]=json.dumps(row);video.write_text('\n'.join(lines)+'\n')
            if run_args(folder,'prepare_raw.py',
                ['--bundle',folder,'--raw-folder',raw,'--output-dir',
                 Path(temporary)/'altered','--synthetic-cpu']).returncode==0:
                raise AssertionError('C135709 changed raw video frame accepted')
            saved_negatives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],
                'mutation':'raw_video_frame','rejected':True})
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            raw=Path(temporary)/'raw'
            if run_args(folder,'fixture_raw.py',
                ['--bundle',folder,'--output-dir',raw]).returncode:
                raise AssertionError('C135709 raw fixture failed')
            if run_args(folder,'prepare_raw.py',
                ['--bundle',folder,'--raw-folder',raw,
                 '--output-dir',Path(temporary)/'original']).returncode==0:
                raise AssertionError('C135709 missing original FFV1 accepted')
            saved_negatives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],
                'mutation':'missing_original_media','rejected':True})
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
            path=altered/'saved'/'camera-frames.jsonl'
            lines=path.read_text().splitlines();row=json.loads(lines[71])
            row['camera_frame']+=1;lines[71]=json.dumps(row)
            path.write_text('\n'.join(lines)+'\n')
            if run(altered,'measure_saved.py').returncode==0:
                raise AssertionError('C135709 changed saved camera join accepted')
            saved_negatives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],
                'mutation':'camera_frame','rejected':True})
            if run(altered,'triggers.py').returncode==0:
                raise AssertionError('C135709 changed trigger camera join accepted')
            saved_negatives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],
                'mutation':'trigger_camera_frame','rejected':True})
        for name in ('requested-tracks.jsonl','assignment-source.json',
                     'stand-road.xodr','case-plan.json'):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
                path=altered/name;path.write_bytes(path.read_bytes()+b' ')
                if run(altered).returncode==0:
                    raise AssertionError('C135709 changed source accepted: '+name)
                negatives.append({'case_id':entry['case_id'],
                    'candidate_id':entry['candidate_id'],'mutation':name,'rejected':True})
    proof={'format':'c135709-compatibility-proof-v1',
        'manifest_sha256':sha(manifest_path),'positives':positives,
        'negatives':negatives,'saved_positives':saved_positives,
        'saved_negatives':saved_negatives,
        'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'proof-compatibility.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof

if __name__=='__main__':
    result=prove();print(json.dumps({'positives':len(result['positives']),
        'negatives':len(result['negatives']),
        'saved_positives':len(result['saved_positives']),
        'saved_negatives':len(result['saved_negatives'])}))
