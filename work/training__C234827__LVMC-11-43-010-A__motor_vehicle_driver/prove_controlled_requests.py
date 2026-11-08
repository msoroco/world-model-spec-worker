"""Prove authored clockwise/counterclockwise request pairing."""
import copy
import hashlib
import json
import math
from pathlib import Path

CASE=Path(__file__).resolve().parent
NATIVE=CASE/'native'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(s) for s in path.read_text().splitlines()]


def compare(first,second):
    if len(first)!=240 or len(second)!=240:
        raise ValueError('LVMC paired frame coverage differs')
    for i,(a,b) in enumerate(zip(first,second)):
        if (a['frame']!=i or b['frame']!=i or
                a['time_s']!=b['time_s'] or
                a['candidate_id']!=b['candidate_id'] or
                a['ego_speed_mps']!=b['ego_speed_mps'] or
                a['lane_id']!=b['lane_id'] or
                a['requested_radius_m']!=b['requested_radius_m'] or
                a['island_center_xy_m']!=b['island_center_xy_m'] or
                abs(a['ego_x_m']-b['ego_x_m'])>1e-5 or
                abs(a['ego_y_m']+b['ego_y_m'])>1e-5 or
                abs(((a['ego_heading_deg']+b['ego_heading_deg'])%360)-360)>1e-5 and
                abs((a['ego_heading_deg']+b['ego_heading_deg'])%360)>1e-5):
            raise ValueError('LVMC paired request context differs')
    return {'paired_frames':240,'controlled_variable':'roundabout_rotation',
        'same_source_context':True,'original_native_observed':False,
        'accepted_comparison':False}


def prove():
    positives=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        first_path=NATIVE/'drafts'/'witness_1'/candidate/'requested-tracks.jsonl'
        second_path=NATIVE/'drafts'/'witness_2'/candidate/'requested-tracks.jsonl'
        result=compare(rows(first_path),rows(second_path))
        positives.append({'candidate_id':candidate,
            'witness_1_sha256':sha(first_path),'witness_2_sha256':sha(second_path),
            'result':result})
    a=rows(NATIVE/'drafts'/'witness_1'/'primary'/'requested-tracks.jsonl')
    b=rows(NATIVE/'drafts'/'witness_2'/'primary'/'requested-tracks.jsonl')
    negatives=[]
    for mutation in ('speed','lane','position','heading'):
        altered=copy.deepcopy(b)
        if mutation=='speed':altered[80]['ego_speed_mps']+=1
        elif mutation=='lane':altered[80]['lane_id']=-2
        elif mutation=='position':altered[80]['ego_y_m']+=.2
        else:altered[80]['ego_heading_deg']+=2
        try:compare(a,altered)
        except ValueError:negatives.append({'mutation':mutation,'rejected':True})
        else:raise AssertionError('LVMC pairing accepted '+mutation)
    proof={'format':'c234827-lvmc-controlled-requests-proof-v1',
        'assignment_id':CASE.name,'positives':positives,'negative_controls':negatives,
        'original_native_observed':False,'accepted_comparison':False}
    (CASE/'controlled-requests-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    value=prove();print(json.dumps({'positives':len(value['positives']),
        'negatives':len(value['negative_controls'])}))
