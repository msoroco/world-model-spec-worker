"""Independently audit paragraph (a) source copies and controlled signal pairs."""
import hashlib
import json
from pathlib import Path

BRANCH=Path(__file__).resolve().parent
NATIVE=BRANCH.parent
CASE=NATIVE.parent
ROOT=CASE.parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def require(ok,message):
    if not ok:raise ValueError(message)

def audit():
    manifest_path=BRANCH/'offline/manifest.json'
    manifest=read(manifest_path);proof=read(BRANCH/'offline/proof-compatibility.json')
    require(len(manifest['entries'])==8 and
        manifest['construction_sha256']==sha(BRANCH/'manifest.json') and
        manifest['measurement_contract_sha256']==sha(BRANCH/'measurement-contract.json') and
        proof['manifest_sha256']==sha(manifest_path) and
        len(proof['positives'])==16 and len(proof['negatives'])==32 and
        proof['strict_v2_compatibility'] is False and
        proof['delivery_ready'] is False,'paragraph (a) manifest/proof')
    tracks={};requested_pass={}
    for entry in manifest['entries']:
        witness=entry['case_id'].split('__')[-1];candidate=entry['candidate_id']
        bundle=BRANCH/entry['bundle'];source=BRANCH/'drafts'/witness/candidate
        originals={'config.json':source/'config.json',
            'requested-tracks.jsonl':source/'requested-tracks.jsonl',
            'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
            'case-plan.json':CASE/'case-plan.json',
            'one-way-pass.xodr':NATIVE/'one-way-pass.xodr',
            'measurement-contract.json':BRANCH/'measurement-contract.json',
            'check.py':BRANCH/'check.py','capture.py':NATIVE/'capture.py'}
        require(entry['sha256']=={name:sha(bundle/name) for name in originals} and
                all(sha(bundle/name)==sha(path) for name,path in originals.items()),
                'paragraph (a) copy/source hash')
        cfg=read(bundle/'config.json');track=rows(bundle/'requested-tracks.jsonl')
        require(cfg['lead_left_signal_requested']==(witness=='exception_1_2') and
                len(track)==240 and all(row['lead_left_signal_requested']==
                    cfg['lead_left_signal_requested'] for row in track),
                'paragraph (a) requested signal coverage')
        tracks[witness,candidate]=track
        requested_pass[witness,candidate]=sum(
            row['ego_x_m']>row['lead_x_m'] and row['ego_lane_id']==-2
            for row in track)
        require(sum(x['bundle']==entry['bundle'] for x in proof['positives'])==2 and
                sum(x['bundle']==entry['bundle'] for x in proof['negatives'])==4,
                'paragraph (a) control coverage')
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        a=tracks['exception_1_1',candidate]
        b=tracks['exception_1_2',candidate]
        for x,y in zip(a,b):
            for key in ('frame','time_s','road_id','ego_x_m','ego_y_m',
                        'ego_lane_id','lead_x_m','lead_y_m','lead_lane_id',
                        'right_lane_obstruction_requested','obstruction_x_m'):
                require(x[key]==y[key],'paragraph (a) controlled pair differs')
            require(x['lead_left_signal_requested'] is False and
                    y['lead_left_signal_requested'] is True,
                    'paragraph (a) signal contrast')
        require(requested_pass['exception_1_1',candidate]==
                requested_pass['exception_1_2',candidate] and
                (requested_pass['exception_1_1',candidate]==0)==
                    (candidate=='fallback3'),
                'paragraph (a) requested pass split')
    result={'format':'c146314-independent-paragraph-a-audit-v1',
        'bundles':8,'controlled_pairs':4,'rows_recomputed':1920,
        'copied_positives':16,'rejected_negatives':32,
        'observed_lead_signal':False,'original_native_observed':False,
        'delivery_ready':False}
    (BRANCH/'offline/package-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
