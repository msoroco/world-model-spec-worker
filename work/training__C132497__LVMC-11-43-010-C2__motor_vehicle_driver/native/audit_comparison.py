"""Independently recompute C132497 paired saved frame, speed and lane evidence."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent.parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def audit():
    path=CASE/'offline'/'proof-comparison.json';proof=json.loads(path.read_text())
    if (proof['format']!='c132497-controlled-comparison-proof-v1' or
        len(proof['positives'])!=len(proof['negatives'])!=4 or
        proof['original_native_observed'] or proof['delivery_ready'] or
        any(not x['rejected'] for x in proof['negatives'])):
        raise ValueError('C132497 comparison proof coverage differs')
    checked=0
    for item in proof['positives']:
        c=item['candidate_id'];paths={w:CASE/'offline'/'bundles'/w/c
            for w in ('reference','contrast')}
        a=rows(paths['reference']/'saved'/'native-observed.jsonl')
        b=rows(paths['contrast']/'saved'/'native-observed.jsonl')
        if len(a)!=240 or len(b)!=240:raise ValueError('C132497 comparison frame coverage differs')
        for i,(left,right) in enumerate(zip(a,b)):
            if (left['frame']!=right['frame'] or left['time_s']!=right['time_s'] or
                left['ego_speed_mps']!=right['ego_speed_mps'] or
                left['lane_id']!=-2 or right['lane_id']!=-1):
                raise ValueError('C132497 paired saved row differs')
            checked+=1
        if (item['reference_circulation_frames']!=sum(x['phase']=='circulation' for x in a) or
            item['contrast_circulation_frames']!=sum(x['phase']=='circulation' for x in b)):
            raise ValueError('C132497 paired phase count differs')
    result={'format':'c132497-independent-comparison-audit-v1',
        'proof_sha256':sha(path),'paired_frames_recomputed':checked,
        'changed_speed_controls':4,'original_native_observed':False,
        'delivery_ready':False}
    (CASE/'offline'/'audit-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
