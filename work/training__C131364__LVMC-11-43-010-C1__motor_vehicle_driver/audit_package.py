"""Independently check copied source bytes and replay C131364 CPU controls."""
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
    return subprocess.run([sys.executable,str(folder/'runner.py'),'--check',
                           '--bundle',str(folder)],capture_output=True,text=True,timeout=20)

def saved_run(folder,script,witness=None):
    cmd=[sys.executable,str(folder/script)]
    if witness:cmd.append(str(folder/'saved-fixtures'/witness))
    return subprocess.run(cmd,capture_output=True,text=True,timeout=20)

def audit():
    manifest_path=CASE/'offline'/'manifest.json'
    proof_path=CASE/'offline'/'proof-compatibility.json'
    manifest=json.loads(manifest_path.read_text())
    proof=json.loads(proof_path.read_text())
    expected={(w,c) for w in ('witness_1','witness_2')
              for c in ('primary','fallback1','fallback2','fallback3')}
    if (manifest['format']!='c131364-exact-offline-v1' or
        manifest['construction_manifest_sha256']!=sha(NATIVE/'drafts'/'manifest.json') or
        manifest['connected_manifest_sha256']!=sha(NATIVE/'exit-network-drafts'/'manifest.json') or
        proof['format']!='c131364-compatibility-proof-v1' or
        proof['manifest_sha256']!=sha(manifest_path) or
        len(proof['positives'])!=8 or len(proof['negatives'])!=40 or
        len(proof['saved_positives'])!=32 or len(proof['saved_negatives'])!=16 or
        manifest['delivery_ready'] or proof['delivery_ready']):
        raise ValueError('C131364 exact package coverage differs')
    seen=set();checks=0;negatives=0;saved_checks=0;saved_negatives=0
    for entry in manifest['entries']:
        witness=entry['case_id'].removeprefix(CASE.name+'__')
        candidate=entry['candidate_id']
        if (witness,candidate) not in expected or (witness,candidate) in seen:
            raise ValueError('C131364 package candidate differs')
        seen.add((witness,candidate))
        folder=CASE/entry['bundle'];source=NATIVE/'drafts'/witness/candidate
        mapping={'config.json':source/'config.json',
                 'requested-tracks.jsonl':source/'requested-tracks.jsonl',
                 'road.xodr':NATIVE/'road.xodr',
                 'connected-config.json':NATIVE/'exit-network-drafts'/witness/candidate/'config.json',
                 'connected-requested-tracks.jsonl':NATIVE/'exit-network-drafts'/witness/candidate/'requested-tracks.jsonl',
                 'connected-road.xodr':NATIVE/'left-exit-road.xodr',
                 'measurement-contract.json':NATIVE/'measurement-contract.json',
                 'runner.py':NATIVE/'runner.py',
                 'measure_saved.py':NATIVE/'measure_saved.py',
                 'measure_exit_saved.py':NATIVE/'measure_exit_saved.py',
                 'triggers.py':NATIVE/'triggers.py',
                 'compare_saved.py':NATIVE/'compare_saved.py',
                 'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
                 'case-plan.json':CASE/'case-plan.json'}
        for name in ('native-observed.jsonl','camera-frames.jsonl','lane-readback.json'):
            mapping[f'connected-saved/{name}']=NATIVE/'exit-saved-fixtures'/witness/candidate/name
        for saved_witness in ('witness_1','witness_2'):
            for name in ('native-observed.jsonl','lane-readback.json','camera-frames.jsonl'):
                relative=f'saved-fixtures/{saved_witness}/{name}'
                mapping[relative]=NATIVE/relative
        if (entry['sha256']!={name:sha(path) for name,path in mapping.items()} or
            entry['sha256']!={name:sha(folder/name) for name in mapping}):
            raise ValueError('C131364 copied source mismatch')
        receipt=run(folder)
        if receipt.returncode!=0 or json.loads(receipt.stdout)['requested_frames']!=240:
            raise ValueError('C131364 copied check differs')
        checks+=1
        for script in ('measure_saved.py','triggers.py','compare_saved.py'):
            receipt=saved_run(folder,script,witness if script!='compare_saved.py' else None)
            if receipt.returncode!=0 or json.loads(receipt.stdout)['delivery_ready']:
                raise ValueError('C131364 copied saved CPU check differs')
            saved_checks+=1
        receipt=subprocess.run(
            [sys.executable,str(folder/'measure_exit_saved.py'),str(folder)],
            capture_output=True,text=True,timeout=20)
        if receipt.returncode!=0 or json.loads(receipt.stdout)['delivery_ready']:
            raise ValueError('C131364 copied connected saved check differs')
        saved_checks+=1
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
            path=altered/'saved-fixtures'/witness/'lane-readback.json'
            changed=json.loads(path.read_text());changed['left_lane_id']=-2
            path.write_text(json.dumps(changed)+'\n')
            for script in ('measure_saved.py','triggers.py','compare_saved.py'):
                if saved_run(altered,script,witness if script!='compare_saved.py' else None).returncode==0:
                    raise ValueError('C131364 changed saved lane readback accepted')
            saved_negatives+=1
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
            path=altered/'connected-saved'/'camera-frames.jsonl'
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            rows[80]['camera_frame']+=1
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            receipt=subprocess.run([sys.executable,str(altered/'measure_exit_saved.py'),str(altered)],
                                   capture_output=True,text=True,timeout=20)
            if receipt.returncode==0:raise ValueError('C131364 changed connected camera join accepted')
            saved_negatives+=1
        for name in ('requested-tracks.jsonl','assignment-source.json','road.xodr',
                     'connected-requested-tracks.jsonl','connected-road.xodr'):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(folder,altered)
                path=altered/name;path.write_bytes(path.read_bytes()+b' ')
                if run(altered).returncode==0:
                    raise ValueError('C131364 altered source accepted')
                negatives+=1
    if seen!=expected:raise ValueError('C131364 package incomplete')
    result={'format':'c131364-independent-package-audit-v1',
            'manifest_sha256':sha(manifest_path),'proof_sha256':sha(proof_path),
            'bundles_checked':checks,'negative_rejections_replayed':negatives,
            'saved_checks_replayed':saved_checks,
            'saved_negative_sources_replayed':saved_negatives,
            'actual_left_exit_observed':False,'delivery_ready':False}
    (CASE/'offline'/'package-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
