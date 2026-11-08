"""Independently recompute C135709 stationary pair occupancy and controls."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def audit():
    proof_path=CASE/'native/comparison-proof.json'
    proof=json.loads(proof_path.read_text())
    if (proof['format']!='c135709-controlled-saved-comparison-v1' or
        len(proof['comparisons'])!=4 or len(proof['negatives'])!=4 or
        proof['delivery_ready'] or proof['legal_verdict'] is not None):
        raise ValueError('C135709 comparison proof coverage differs')
    total=0
    for item in proof['comparisons']:
        candidate=item['candidate_id']
        if candidate not in ('primary','fallback1','fallback2','fallback3'):
            raise ValueError('C135709 candidate absent')
        ref=CASE/'offline/bundles/reference'/candidate/'saved/native-observed.jsonl'
        con=CASE/'offline/bundles/contrast'/candidate/'saved/native-observed.jsonl'
        if item['source_hashes']!={'reference':sha(ref),'contrast':sha(con)}:
            raise ValueError('C135709 comparison sources differ')
        a,b=rows(ref),rows(con)
        if not (len(a)==len(b)==240):raise ValueError('C135709 pair count differs')
        actual=[0,0]
        for i in range(210,240):
            if (a[i]['frame']!=b[i]['frame'] or
                a[i]['ego_x_m']!=b[i]['ego_x_m'] or
                a[i]['ego_speed_mps']!=b[i]['ego_speed_mps'] or
                a[i]['ego_speed_mps']>.1):
                raise ValueError('C135709 pair speed/time differs')
            for j,row in enumerate((a[i],b[i])):
                actual[j]+=all(50<=p[0]<=75 and -8.25<=p[1]<=-3.5
                               for p in row['ego_body_xy_m'])
            total+=1
        if (actual!=[item['reference_stand_frames'],item['contrast_stand_frames']] or
            actual!=[0,0 if candidate=='fallback3' else 30]):
            raise ValueError('C135709 pair occupancy differs')
    receipt={'format':'c135709-independent-comparison-audit-v1',
        'proof_sha256':sha(proof_path),'paired_frames_recomputed':total,
        'changed_speed_controls':len(proof['negatives']),
        'original_native_observed':False,'delivery_ready':False}
    (CASE/'native/comparison-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':print(json.dumps(audit()))
