"""Check fixed request inputs for four inner/outer lane pairs."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent
NATIVE=CASE/'native'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in path.read_text().splitlines()]

def compare(a,b):
    if len(a)!=240 or len(b)!=240:raise ValueError('Pair frame coverage differs')
    for i,(x,y) in enumerate(zip(a,b)):
        if (x['frame']!=y['frame'] or x['time_s']!=y['time_s'] or
            x['ego_speed_mps']!=y['ego_speed_mps'] or
            x['intended_exit_kind']!=y['intended_exit_kind'] or
            x['candidate_id']!=y['candidate_id'] or
            x['lane_id']!=-1 or y['lane_id']!=-2 or
            x['actual_exit_observed'] or y['actual_exit_observed']):
            raise ValueError(f'C131364 uncontrolled request pair at {i}')
    return {'frames':240,'lane_ids':[-1,-2],
            'fixed':['frame','time_s','speed','intended_exit_kind','candidate_id'],
            'actual_exit_observed':False}

def prove():
    positives=[];negatives=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        p=NATIVE/'drafts'/'witness_1'/candidate/'requested-tracks.jsonl'
        q=NATIVE/'drafts'/'witness_2'/candidate/'requested-tracks.jsonl'
        a,b=rows(p),rows(q)
        measurement=compare(a,b)
        positives.append({'candidate_id':candidate,'source_hashes':[sha(p),sha(q)],
                          'comparison':measurement})
        changed=[dict(row) for row in b];changed[40]['ego_speed_mps']+=1
        try:compare(a,changed)
        except ValueError:pass
        else:raise ValueError('Changed pair speed accepted')
        negatives.append({'candidate_id':candidate,'mutation':'changed_speed',
                          'rejected':True})
    result={'format':'c131364-controlled-request-proof-v1',
            'positives':positives,'negatives':negatives,
            'actual_exit_observed':False,'delivery_ready':False}
    (CASE/'controlled-requests-proof.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps({'pairs':len(prove()['positives'])}))
