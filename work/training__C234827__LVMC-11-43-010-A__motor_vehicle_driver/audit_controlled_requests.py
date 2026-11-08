"""Independently recompute LVMC paired request controls."""
import copy
import hashlib
import json
import math
from pathlib import Path

CASE=Path(__file__).resolve().parent
NATIVE=CASE/'native'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(s) for s in path.read_text().splitlines()]


def audit():
    proof_path=CASE/'controlled-requests-proof.json'
    proof=json.loads(proof_path.read_text())
    if (proof.get('format')!='c234827-lvmc-controlled-requests-proof-v1' or
            proof.get('assignment_id')!=CASE.name or
            len(proof.get('positives',[]))!=4 or
            [item['mutation'] for item in proof.get('negative_controls',[])]!=
            ['speed','lane','position','heading'] or
            any(not item['rejected'] for item in proof['negative_controls']) or
            proof['original_native_observed'] or proof['accepted_comparison']):
        raise ValueError('LVMC comparison proof coverage differs')
    total=0
    for item in proof['positives']:
        candidate=item['candidate_id']
        a_path=NATIVE/'drafts'/'witness_1'/candidate/'requested-tracks.jsonl'
        b_path=NATIVE/'drafts'/'witness_2'/candidate/'requested-tracks.jsonl'
        if (sha(a_path)!=item['witness_1_sha256'] or
                sha(b_path)!=item['witness_2_sha256'] or
                item['result']['accepted_comparison'] or
                item['result']['paired_frames']!=240):
            raise ValueError('LVMC controlled source hash differs')
        a=rows(a_path);b=rows(b_path)
        if len(a)!=240 or len(b)!=240:
            raise ValueError('LVMC paired frame count differs')
        for i,(first,second) in enumerate(zip(a,b)):
            if (first['frame']!=i or second['frame']!=i or
                    first['time_s']!=second['time_s'] or
                    first['ego_speed_mps']!=second['ego_speed_mps'] or
                    first['lane_id']!=second['lane_id'] or
                    first['requested_radius_m']!=second['requested_radius_m'] or
                    abs(first['ego_x_m']-second['ego_x_m'])>1e-5 or
                    abs(first['ego_y_m']+second['ego_y_m'])>1e-5 or
                    abs(math.sin(math.radians(first['ego_heading_deg']+
                                              second['ego_heading_deg'])))>1e-6):
                raise ValueError('LVMC independently paired row differs')
            total+=2
    if total!=1920:raise ValueError('LVMC independent comparison coverage differs')
    # Run the four mutations through the production comparison after the
    # independent row recomputation, guarding against stale negative receipts.
    from prove_controlled_requests import compare
    a=rows(NATIVE/'drafts'/'witness_1'/'primary'/'requested-tracks.jsonl')
    b=rows(NATIVE/'drafts'/'witness_2'/'primary'/'requested-tracks.jsonl')
    for mutation in ('speed','lane','position','heading'):
        altered=copy.deepcopy(b)
        if mutation=='speed':altered[80]['ego_speed_mps']+=1
        elif mutation=='lane':altered[80]['lane_id']=-2
        elif mutation=='position':altered[80]['ego_y_m']+=.2
        else:altered[80]['ego_heading_deg']+=2
        try:compare(a,altered)
        except ValueError:pass
        else:raise ValueError('LVMC negative comparison no longer rejected')
    result={'format':'c234827-lvmc-independent-controlled-audit-v1',
        'proof_sha256':sha(proof_path),'paired_rows_recomputed':total,
        'negative_controls_replayed':4,'accepted_comparison':False}
    (CASE/'controlled-requests-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit()))
