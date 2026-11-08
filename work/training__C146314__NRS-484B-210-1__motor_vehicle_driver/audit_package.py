"""Independently bind copied C146314 diagnostic receipts to current sources."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]
NATIVE=CASE/'native'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def require(ok,message):
    if not ok:raise ValueError(message)


def audit():
    manifest_path=CASE/'offline'/'manifest.json'
    manifest=read(manifest_path);proof=read(CASE/'offline'/'proof-compatibility.json')
    require(len(manifest['entries'])==8 and
            manifest['construction_sha256']==sha(NATIVE/'manifest.json') and
            manifest['measurement_contract_sha256']==
                sha(NATIVE/'measurement-contract.json') and
            proof['manifest_sha256']==sha(manifest_path) and
            len(proof['positives'])==32 and len(proof['negatives'])==48 and
            proof['strict_v2_compatibility'] is False and
            proof['delivery_ready'] is False, 'package manifest/proof')
    saved_audit=read(NATIVE/'saved-audit.json')
    require(saved_audit['rows_recomputed']==1920 and
            saved_audit['positives']==8 and
            saved_audit['semantic_negatives']==16, 'independent saved audit')
    for entry in manifest['entries']:
        witness=entry['case_id'].split('__')[-1];candidate=entry['candidate_id']
        bundle=CASE/entry['bundle']
        source=NATIVE/'drafts'/witness/candidate
        original={'config.json':source/'config.json',
            'requested-tracks.jsonl':source/'requested-tracks.jsonl',
            'one-way-pass.xodr':NATIVE/'one-way-pass.xodr',
            'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
            'case-plan.json':CASE/'case-plan.json',
            'measurement-contract.json':NATIVE/'measurement-contract.json',
            'check.py':NATIVE/'check.py',
            'capture.py':NATIVE/'capture.py',
            'measure_saved.py':NATIVE/'measure_saved.py',
            'route_fallbacks.py':NATIVE/'route_fallbacks.py'}
        for name in ('native-observed.jsonl','camera-frames.jsonl','readback.json'):
            original['saved/'+name]=NATIVE/'saved-fixtures'/witness/candidate/name
        require(entry['sha256']=={name:sha(bundle/name) for name in original} and
                all(sha(bundle/name)==sha(path) for name,path in original.items()),
                'copy/source mismatch')
        require(sum(x['case_id']==entry['case_id'] and
                    x['candidate_id']==candidate for x in proof['positives'])==4 and
                sum(x['case_id']==entry['case_id'] and
                    x['candidate_id']==candidate for x in proof['negatives'])==6,
                'missing copied control')
        command=[sys.executable,str(bundle/'check.py'),'--bundle',str(bundle)]
        result=subprocess.run(command,capture_output=True,text=True,timeout=20)
        require(result.returncode==0 and
                read_from_string(result.stdout)['source_bound'] is True,
                'copied request replay')
        result=subprocess.run([sys.executable,str(bundle/'measure_saved.py'),
            '--bundle',str(bundle),'--saved-dir',str(bundle/'saved')],
            capture_output=True,text=True,timeout=20)
        require(result.returncode==0,'copied saved replay')
        measured=read_from_string(result.stdout)
        source=next(x for x in saved_audit['results'] if x['witness']==witness
                    and x['candidate_id']==candidate)
        require(measured['passing_right_geometry_frames']==
                    source['passing_right_geometry_frames'] and
                measured['min_ego_body_to_obstruction_clearance_m']==
                    source['min_clearance_m'] and
                measured['original_native_observed'] is False and
                measured['delivery_ready'] is False,
                'copied saved measurement differs')
    receipt={'format':'c146314-independent-package-audit-v1',
        'bundles':8,'request_positives':8,'capture_preflight_positives':8,
        'saved_positives':8,
        'router_positives':8,'rejected_negatives':48,
        'strict_v2_compatibility':False,'delivery_ready':False}
    (CASE/'offline'/'package-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def read_from_string(s):return json.loads(s)


if __name__=='__main__':print(json.dumps(audit()))
