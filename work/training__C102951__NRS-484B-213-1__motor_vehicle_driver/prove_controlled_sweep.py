"""Controlled synthetic 70/120/170 m oncoming-distance comparison."""
import hashlib
import json
from pathlib import Path
import tempfile

CASE=Path(__file__).resolve().parent;NATIVE=CASE/'native';DISTANCES=(70,120,170)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def rows(path):return [json.loads(line) for line in path.read_text().splitlines()]

def fixed(row):
    return (row['frame'],row['native_frame'],row['time_s'],row['source_kind'],
            row['ego_blueprint'],row['ego_x_m'],row['ego_y_m'],row['ego_speed_mps'],
            row['overtaken_x_m'],row['overtaken_y_m'],row['overtaken_speed_mps'],
            row['oncoming_y_m'],row['oncoming_speed_mps'],row['sightline_visible'])

def compare(paths):
    all_rows=[rows(path) for path in paths]
    if any(len(group)!=480 for group in all_rows):raise ValueError('Sweep frame count differs')
    for i,group in enumerate(zip(*all_rows)):
        if len({fixed(row) for row in group})!=1 or any(row['frame']!=i for row in group):
            raise ValueError('Sweep fixed actor context differs')
        positions=[row['oncoming_x_m'] for row in group]
        sight=[row['driver_eye_clear_m'] for row in group]
        if sight!=list(DISTANCES) or round(positions[1]-positions[0],3)!=50 or round(positions[2]-positions[1],3)!=50:
            raise ValueError('Sweep deliberate clear-ahead variable differs')
    proof=json.loads((NATIVE/'pass-proof.json').read_text())
    measures={row['requested_clear_oncoming_distance_m']:row['measurement'] for row in proof['positives']}
    events=[measures[d]['first_nonpositive_pre_return_oncoming_gap_frame'] for d in DISTANCES]
    if events[0] is None or events[1] is None or events[2] is not None:
        raise ValueError('Synthetic sweep event order differs')
    return {'probe_distances_m':list(DISTANCES),'first_nonpositive_pre_return_gap_frames':events,
            'common_return_frame':measures[70]['first_return_after_pass_frame']}

def rejected(fn):
    try:fn()
    except ValueError:return True
    raise AssertionError('Changed sweep control accepted')

def prove():
    paths=[NATIVE/'saved-fixtures'/str(d)/'native-observed.jsonl' for d in DISTANCES]
    metric=compare(paths);negatives=[]
    for mutation in ('ego_x','overtaken_speed','oncoming_speed','clear_distance'):
        with tempfile.TemporaryDirectory(dir=CASE) as temporary:
            changed=Path(temporary)/'changed.jsonl';data=rows(paths[1])
            if mutation=='ego_x':data[100]['ego_x_m']+=1
            elif mutation=='overtaken_speed':data[100]['overtaken_speed_mps']+=1
            elif mutation=='oncoming_speed':data[100]['oncoming_speed_mps']+=1
            else:data[100]['driver_eye_clear_m']+=1
            changed.write_text(''.join(json.dumps(row)+'\n' for row in data))
            negatives.append({'mutation':mutation,'rejected':rejected(lambda:compare([paths[0],changed,paths[2]]))})
    proof={'format':'c102951-controlled-synthetic-sweep-v1',
           'pass_proof_sha256':sha(NATIVE/'pass-proof.json'),
           'source_sha256':{str(d):sha(path) for d,path in zip(DISTANCES,paths)},
           'metric':metric,'negatives':negatives,
           'original_native_observed':False,'accepted_comparison':False,
           'safe_distance_judgment':None,'delivery_ready':False}
    (CASE/'controlled-sweep.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof

if __name__=='__main__':print(json.dumps({'negative_count':len(prove()['negatives'])}))
