"""Run exact copied C146314 diagnostic positives and source/semantic negatives."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CASE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(folder,script,args):
    return subprocess.run([sys.executable,str(folder/script),*map(str,args)],
        capture_output=True,text=True,timeout=20)


def prove():
    manifest_path=CASE/'offline'/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    positives=[];negative=[]
    for entry in manifest['entries']:
        folder=CASE/entry['bundle']
        if any(sha(folder/name)!=digest for name,digest in entry['sha256'].items()):
            raise ValueError('copied bundle bytes differ')
        commands=(('check.py',['--bundle',folder]),
                  ('measure_saved.py',['--bundle',folder,'--saved-dir',folder/'saved']),
                  ('route_fallbacks.py',['--bundle',folder,'--saved-dir',folder/'saved']))
        for script,args in commands:
            result=run(folder,script,args)
            if result.returncode or json.loads(result.stdout)['delivery_ready']:
                raise AssertionError('copied positive failed '+script+result.stderr)
            positives.append({'case_id':entry['case_id'],
                'candidate_id':entry['candidate_id'],'script':script,'passed':True})
        for name in ('assignment-source.json','case-plan.json',
                     'one-way-pass.xodr','requested-tracks.jsonl'):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as tmp:
                altered=Path(tmp)/'bundle';shutil.copytree(folder,altered)
                p=altered/name;p.write_bytes(p.read_bytes()+b' ')
                failed=run(altered,'check.py',['--bundle',altered])
                if failed.returncode==0:
                    raise AssertionError('changed copied request accepted '+name)
                negative.append({'case_id':entry['case_id'],
                    'candidate_id':entry['candidate_id'],'mutation':name,
                    'rejected':True})
        for kind in ('changed_body_corner','missing_camera_frame'):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as tmp:
                altered=Path(tmp)/'bundle';shutil.copytree(folder,altered)
                saved=altered/'saved';back=json.loads((saved/'readback.json').read_text())
                name='native-observed.jsonl' if kind=='changed_body_corner' else 'camera-frames.jsonl'
                path=saved/name
                items=[json.loads(x) for x in path.read_text().splitlines()]
                if kind=='changed_body_corner':
                    items[80]['ego_body_xy_m'][0][1]+=2
                else:items.pop()
                path.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in items))
                back['observed_sha256' if kind=='changed_body_corner' else
                     'camera_sha256']=sha(path)
                (saved/'readback.json').write_text(json.dumps(back,indent=2)+'\n')
                failed=run(altered,'measure_saved.py',
                           ['--bundle',altered,'--saved-dir',saved])
                if failed.returncode==0:
                    raise AssertionError('changed saved evidence accepted '+kind)
                negative.append({'case_id':entry['case_id'],
                    'candidate_id':entry['candidate_id'],'mutation':kind,
                    'rejected':True})
    receipt={'format':'c146314-copied-compatibility-diagnostic-v1',
        'manifest_sha256':sha(manifest_path),'positives':positives,
        'negatives':negative,'original_native_observed':False,
        'strict_v2_compatibility':False,'delivery_ready':False}
    (CASE/'offline'/'proof-compatibility.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    x=prove()
    print(json.dumps({'positives':len(x['positives']),
                      'negatives':len(x['negatives'])}))
