"""Independent 1,440-row controlled-distance audit."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent;NATIVE=CASE/'native';DISTANCES=(70,120,170)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    path=CASE/'controlled-sweep.json';proof=json.loads(path.read_text())
    if (proof['format']!='c102951-controlled-synthetic-sweep-v1' or
            proof['pass_proof_sha256']!=sha(NATIVE/'pass-proof.json') or
            proof['original_native_observed'] or proof['accepted_comparison'] or
            proof['delivery_ready'] or proof['safe_distance_judgment'] is not None or
            {row['mutation'] for row in proof['negatives']}!={'ego_x','overtaken_speed','oncoming_speed','clear_distance'} or
            not all(row['rejected'] is True for row in proof['negatives'])):
        raise ValueError('Controlled sweep proof scope differs')
    paths=[NATIVE/'saved-fixtures'/str(d)/'native-observed.jsonl' for d in DISTANCES]
    if proof['source_sha256']!={str(d):sha(p) for d,p in zip(DISTANCES,paths)}:
        raise ValueError('Controlled sweep source hash differs')
    groups=[[json.loads(line) for line in p.read_text().splitlines()] for p in paths]
    if any(len(group)!=480 for group in groups):raise ValueError('Controlled sweep row count differs')
    for i,triplet in enumerate(zip(*groups)):
        if any(r['frame']!=i or r['native_frame']!=1000+i for r in triplet):
            raise ValueError('Controlled sweep frame identity differs')
        for key in ('time_s','ego_blueprint','ego_x_m','ego_y_m','ego_speed_mps',
                    'overtaken_x_m','overtaken_y_m','overtaken_speed_mps',
                    'oncoming_y_m','oncoming_speed_mps','sightline_visible'):
            if len({r[key] for r in triplet})!=1:
                raise ValueError('Controlled sweep fixed field differs: '+key)
        if [r['driver_eye_clear_m'] for r in triplet]!=list(DISTANCES) or [round(r['oncoming_x_m']-triplet[0]['oncoming_x_m'],3) for r in triplet]!=[0,50,100]:
            raise ValueError('Controlled sweep varied field differs')
    entries=[]
    for group in groups:
        entry=next(i for i,r in enumerate(group) if r['ego_y_m']+.9>0)
        passed=False;returned=None;nonpositive=None
        for i in range(entry,480):
            r=group[i]
            if r['ego_x_m']-2.2>r['overtaken_x_m']+2.2:passed=True
            if nonpositive is None and round(r['oncoming_x_m']-r['ego_x_m']-4.4,3)<=0:nonpositive=i
            if passed and r['ego_y_m']+.9<=0:returned=i;break
        entries.append((nonpositive,returned))
    metric={'probe_distances_m':list(DISTANCES),
            'first_nonpositive_pre_return_gap_frames':[pair[0] for pair in entries],
            'common_return_frame':entries[0][1]}
    if proof['metric']!=metric or len({pair[1] for pair in entries})!=1 or metric['first_nonpositive_pre_return_gap_frames'][2] is not None:
        raise ValueError('Controlled sweep event metric differs')
    result={'format':'c102951-independent-controlled-sweep-audit-v1',
            'saved_rows_checked':1440,'negative_count':4,
            'proof_sha256':sha(path),'accepted_comparison':False,'delivery_ready':False}
    (CASE/'controlled-sweep-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
