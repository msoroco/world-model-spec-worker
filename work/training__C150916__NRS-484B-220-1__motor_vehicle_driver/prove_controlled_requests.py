"""Pair exact requested trajectories across designated and opposite cases."""
import hashlib
import json
from pathlib import Path
import tempfile

CASE=Path(__file__).resolve().parent
NATIVE=CASE/'native'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in path.read_text().splitlines()]


def compare(first,second):
    forward=rows(first);reverse=rows(second)
    if len(forward)!=240 or len(reverse)!=240:
        raise ValueError('One-way paired request row count differs')
    for i,(a,b) in enumerate(zip(forward,reverse)):
        if (a['frame']!=i or b['frame']!=i or a['time_s']!=b['time_s'] or
                a['ego_y_m']!=b['ego_y_m'] or a['ego_speed_mps']!=b['ego_speed_mps'] or
                a['lane_id']!=b['lane_id'] or a['requested_direction']!='designated' or
                b['requested_direction']!='opposite' or
                a['ego_heading_deg']!=0 or b['ego_heading_deg']!=180 or
                abs(a['ego_x_m']+b['ego_x_m']-200)>1e-4):
            raise ValueError('One-way paired request fixed or deliberate variable differs')
    return {'frames':240,'longitudinal_mirror_center_x_m':100,
            'forward_signed_displacement_m':round(forward[-1]['ego_x_m']-forward[0]['ego_x_m'],3),
            'reverse_signed_displacement_m':round(reverse[-1]['ego_x_m']-reverse[0]['ego_x_m'],3)}


def prove():
    pairs=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        first=NATIVE/'drafts'/'designated'/candidate/'requested-tracks.jsonl'
        second=NATIVE/'drafts'/'opposite'/candidate/'requested-tracks.jsonl'
        metric=compare(first,second)
        pairs.append({'candidate_id':candidate,'designated_sha256':sha(first),
                      'opposite_sha256':sha(second),'metric':metric})
    negatives=[]
    first=NATIVE/'drafts'/'designated'/'primary'/'requested-tracks.jsonl'
    second=NATIVE/'drafts'/'opposite'/'primary'/'requested-tracks.jsonl'
    for mutation in ('ego_speed','lane','heading','mirror_position'):
        with tempfile.TemporaryDirectory(dir=CASE) as temporary:
            changed=Path(temporary)/'changed.jsonl';data=rows(second)
            key={'ego_speed':'ego_speed_mps','lane':'lane_id','heading':'ego_heading_deg',
                 'mirror_position':'ego_x_m'}[mutation]
            data[60][key]+=1
            changed.write_text(''.join(json.dumps(row)+'\n' for row in data))
            try:compare(first,changed)
            except ValueError:negatives.append({'mutation':mutation,'rejected':True})
            else:raise AssertionError('Changed one-way request pair accepted')
    proof={'format':'c150916-controlled-request-comparison-v1',
           'assignment_id':CASE.name,'road_sha256':sha(NATIVE/'road.xodr'),
           'construction_manifest_sha256':sha(NATIVE/'drafts'/'manifest.json'),
           'pairs':pairs,'negative_controls':negatives,
           'original_native_observed':False,'accepted_comparison':False,
           'legal_verdict':None,'delivery_ready':False}
    (CASE/'controlled-request-comparison.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    proof=prove();print(json.dumps({'pairs':len(proof['pairs']),
                                    'negatives':len(proof['negative_controls'])}))
