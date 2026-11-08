"""Independently replay every C131364 lane comparison row."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent
NATIVE=CASE/'native'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def audit():
    path=CASE/'controlled-requests-proof.json'
    proof=json.loads(path.read_text())
    if len(proof['positives'])!=4 or len(proof['negatives'])!=4 or proof['delivery_ready']:
        raise ValueError('C131364 controlled proof coverage differs')
    total=0
    for item in proof['positives']:
        candidate=item['candidate_id']
        paths=[NATIVE/'drafts'/w/candidate/'requested-tracks.jsonl'
               for w in ('witness_1','witness_2')]
        if item['source_hashes']!=[sha(p) for p in paths]:
            raise ValueError('C131364 pair source hash differs')
        a,b=[[json.loads(line) for line in p.read_text().splitlines()] for p in paths]
        for i,(x,y) in enumerate(zip(a,b)):
            if (x['frame']!=i or y['frame']!=i or x['time_s']!=y['time_s'] or
                x['ego_speed_mps']!=y['ego_speed_mps'] or
                x['candidate_id']!=y['candidate_id'] or
                x['intended_exit_kind']!='left_turn' or y['intended_exit_kind']!='left_turn' or
                x['lane_id']!=-1 or y['lane_id']!=-2 or
                x['actual_exit_observed'] or y['actual_exit_observed']):
                raise ValueError(f'C131364 independent pair differs at {i}')
            total+=2
        changed=[dict(row) for row in b];changed[40]['ego_speed_mps']+=1
        if all(x['ego_speed_mps']==y['ego_speed_mps'] for x,y in zip(a,changed)):
            raise ValueError('C131364 negative speed mutation ineffective')
    if total!=1920:raise ValueError('C131364 pair rows incomplete')
    result={'format':'c131364-independent-controlled-audit-v1',
            'proof_sha256':sha(path),'requested_rows_recomputed':total,
            'negative_mutations_replayed':4,'actual_exit_observed':False,
            'delivery_ready':False}
    (CASE/'controlled-requests-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
