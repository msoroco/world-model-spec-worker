"""Copied paragraph (a) preflight positives and source/semantic negatives."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BRANCH=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(folder,script,args):
    return subprocess.run([sys.executable,str(folder/script),*map(str,args)],
        capture_output=True,text=True,timeout=20)

def prove():
    manifest_path=BRANCH/'offline/manifest.json'
    manifest=json.loads(manifest_path.read_text())
    positives=[];negatives=[]
    for entry in manifest['entries']:
        folder=BRANCH/entry['bundle']
        if entry['sha256']!={name:sha(folder/name) for name in entry['sha256']}:
            raise ValueError('copied source differs')
        for script,args in (('check.py',['--bundle',folder]),
                            ('capture.py',['--check','--bundle',folder])):
            result=run(folder,script,args)
            if result.returncode or json.loads(result.stdout)['delivery_ready']:
                raise AssertionError('paragraph (a) copied positive '+script+result.stderr)
            positives.append({'bundle':entry['bundle'],'script':script})
        for kind in ('changed_assignment','changed_plan','changed_track',
                     'changed_signal_with_rehash'):
            with tempfile.TemporaryDirectory(dir=BRANCH/'offline') as tmp:
                altered=Path(tmp)/'bundle';shutil.copytree(folder,altered)
                if kind in ('changed_assignment','changed_plan'):
                    name='assignment-source.json' if kind=='changed_assignment' else 'case-plan.json'
                    p=altered/name;p.write_bytes(p.read_bytes()+b' ')
                elif kind=='changed_track':
                    p=altered/'requested-tracks.jsonl';p.write_bytes(p.read_bytes()+b' ')
                else:
                    p=altered/'requested-tracks.jsonl'
                    rows=[json.loads(x) for x in p.read_text().splitlines()]
                    rows[100]['lead_left_signal_requested']=not rows[100]['lead_left_signal_requested']
                    p.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in rows))
                    cfg=altered/'config.json';value=json.loads(cfg.read_text())
                    value['tracks_sha256']=sha(p)
                    cfg.write_text(json.dumps(value,indent=2)+'\n')
                result=run(altered,'check.py',['--bundle',altered])
                if result.returncode==0:
                    raise AssertionError('paragraph (a) mutation accepted '+kind)
                negatives.append({'bundle':entry['bundle'],'mutation':kind})
    receipt={'format':'c146314-paragraph-a-copied-proof-v1',
        'manifest_sha256':sha(manifest_path),'positives':positives,
        'negatives':negatives,'original_native_observed':False,
        'strict_v2_compatibility':False,'delivery_ready':False}
    (BRANCH/'offline/proof-compatibility.json').write_text(
        json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    r=prove();print(json.dumps({'positives':len(r['positives']),
                                'negatives':len(r['negatives'])}))
