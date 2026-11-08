"""Execute eight copied CPU checks and reject altered exact bundle sources."""
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
    return subprocess.run([sys.executable,str(folder/'runner.py'),'--check','--bundle',str(folder)],
                          text=True,capture_output=True,timeout=20)


def prove():
    manifest_path=CASE/'offline'/'manifest.json'
    manifest=json.loads(manifest_path.read_text())
    positives=[];negatives=[]
    for entry in manifest['entries']:
        folder=CASE/entry['bundle']
        if {name:sha(folder/name) for name in entry['sha256']}!=entry['sha256']:
            raise ValueError('One-way copied source differs from manifest')
        result=run(folder)
        if result.returncode!=0:raise AssertionError(result.stderr)
        receipt=json.loads(result.stdout)
        if receipt['requested_frames']!=240 or receipt['physical_sign_verified'] or receipt['delivery_ready']:
            raise AssertionError('One-way copied CPU check overclaimed')
        positives.append({'case_id':entry['case_id'],'candidate_id':entry['candidate_id'],
                          'config_sha256':sha(folder/'config.json'),'passed':True})
        for mutation,file in (('track_bytes','requested-tracks.jsonl'),
                              ('assignment_bytes','assignment-source.json'),
                              ('road_bytes','road.xodr')):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
                path=altered/file;path.write_bytes(path.read_bytes()+b' ')
                if run(altered).returncode==0:
                    raise AssertionError('One-way copied checker accepted '+mutation)
                negatives.append({'case_id':entry['case_id'],'candidate_id':entry['candidate_id'],
                                  'mutation':mutation,'rejected':True})
    result={'format':'c150916-exact-compatibility-proof-v1',
            'assignment_id':CASE.name,'manifest_sha256':sha(manifest_path),
            'positives':positives,'negatives':negatives,
            'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'proof-compatibility.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    result=prove();print(json.dumps({'positives':len(result['positives']),
                                     'negatives':len(result['negatives'])}))
