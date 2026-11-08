"""Independent exact-byte and copied CPU replay audit for rotary bundles."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]
NATIVE=CASE/'native'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run(folder):
    return subprocess.run([sys.executable,str(folder/'runner.py'),'--check','--bundle',str(folder)],
                          text=True,capture_output=True,timeout=20)


def audit():
    manifest_path=CASE/'offline'/'manifest.json'
    proof_path=CASE/'offline'/'proof-compatibility.json'
    manifest=json.loads(manifest_path.read_text())
    proof=json.loads(proof_path.read_text())
    expected={(case,candidate) for case in ('reference','contrast')
              for candidate in ('primary','fallback1','fallback2','fallback3')}
    if (manifest['format']!='c234827-exact-offline-bundles-v1' or
            manifest['assignment_id']!=CASE.name or
            manifest['construction_manifest_sha256']!=sha(NATIVE/'drafts'/'manifest.json') or
            proof['format']!='c234827-exact-compatibility-proof-v1' or
            proof['manifest_sha256']!=sha(manifest_path) or
            len(proof['positives'])!=8 or len(proof['negatives'])!=24 or
            any(not item['rejected'] for item in proof['negatives']) or
            manifest['accepted_originals_replayed']!=0 or
            proof['accepted_originals_replayed']!=0 or
            manifest['delivery_ready'] or proof['delivery_ready']):
        raise ValueError('Rotary package proof coverage differs')
    seen=set();checks=0;rejections=0
    for entry in manifest['entries']:
        case=entry['case_id'].removeprefix(CASE.name+'__')
        candidate=entry['candidate_id']
        if (case,candidate) not in expected or (case,candidate) in seen:
            raise ValueError('Rotary package candidate coverage differs')
        seen.add((case,candidate))
        source=NATIVE/'drafts'/case/candidate
        folder=CASE/entry['bundle']
        mapping={'config.json':source/'config.json',
            'requested-tracks.jsonl':source/'requested-tracks.jsonl',
            'road.xodr':NATIVE/'road.xodr',
            'island-geometry.json':NATIVE/'island-geometry.json',
            'measurement-contract.json':NATIVE/'measurement-contract.json',
            'runner.py':NATIVE/'runner.py',
            'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
            'case-plan.json':CASE/'case-plan.json'}
        if (entry['sha256']!={name:sha(folder/name) for name in mapping} or
                entry['sha256']!={name:sha(path) for name,path in mapping.items()} or
                entry['status']!='unselected_native_request'):
            raise ValueError('Rotary copied source bytes differ')
        result=run(folder)
        if result.returncode!=0 or json.loads(result.stdout)['requested_frames']!=240:
            raise ValueError('Rotary copied CPU check differs')
        checks+=1
        for name in ('requested-tracks.jsonl','assignment-source.json','road.xodr'):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
                path=altered/name;path.write_bytes(path.read_bytes()+b' ')
                if run(altered).returncode==0:
                    raise ValueError('Rotary changed copied source accepted')
                rejections+=1
    if seen!=expected:raise ValueError('Rotary package incomplete')
    receipt={'format':'c234827-independent-package-audit-v1',
        'manifest_sha256':sha(manifest_path),'proof_sha256':sha(proof_path),
        'bundles_checked':checks,'negative_rejections_replayed':rejections,
        'accepted_originals_replayed':0,
        'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'package-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':print(json.dumps(audit()))
