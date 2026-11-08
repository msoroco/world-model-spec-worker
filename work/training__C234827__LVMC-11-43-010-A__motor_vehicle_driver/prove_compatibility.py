"""Execute copied LVMC roundabout CPU checks and altered-source controls."""
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
        '--bundle',str(folder)],text=True,capture_output=True,timeout=20)


def prove():
    manifest_path=CASE/'offline'/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    positives=[];negatives=[]
    for entry in manifest['entries']:
        folder=CASE/entry['bundle']
        if entry['sha256']!={name:sha(folder/name) for name in entry['sha256']}:
            raise ValueError('LVMC copied bundle bytes differ')
        result=run(folder)
        if result.returncode!=0:raise AssertionError(result.stderr)
        checked=json.loads(result.stdout)
        if checked['requested_frames']!=240 or checked['delivery_ready']:
            raise AssertionError('Copied LVMC runner overclaims readiness')
        positives.append({'case_id':entry['case_id'],
            'candidate_id':entry['candidate_id'],
            'config_sha256':sha(folder/'config.json'),'passed':True})
        for mutation,name in (('track_bytes','requested-tracks.jsonl'),
                              ('assignment_bytes','assignment-source.json'),
                              ('road_bytes','road.xodr')):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
                path=altered/name;path.write_bytes(path.read_bytes()+b' ')
                if run(altered).returncode==0:
                    raise AssertionError('Copied LVMC altered source accepted')
                negatives.append({'case_id':entry['case_id'],
                    'candidate_id':entry['candidate_id'],
                    'mutation':mutation,'rejected':True})
    proof={'format':'c234827-lvmc-compatibility-proof-v1',
        'assignment_id':CASE.name,'manifest_sha256':sha(manifest_path),
        'positives':positives,'negatives':negatives,
        'accepted_originals_replayed':0,'original_native_observed':False,
        'delivery_ready':False}
    (CASE/'offline'/'proof-compatibility.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    result=prove();print(json.dumps({'positives':len(result['positives']),
        'negatives':len(result['negatives'])}))
