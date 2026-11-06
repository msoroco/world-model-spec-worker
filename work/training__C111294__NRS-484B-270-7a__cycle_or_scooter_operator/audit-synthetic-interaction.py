"""Independent raw-source comparison of C111294 unselected CPU interaction pair."""
import hashlib
import json
import math
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
SOURCE=ROOT/'.runtime-work/c111294-interaction-proof'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(case):
    road=SOURCE/case/'road.xodr';path=SOURCE/case/'interaction.json'
    data=json.loads(path.read_text())
    if data['map_sha256']!=sha(road) or data['case']!=case or len(data['frames'])!=480:
        raise ValueError('Source, case or frame count differs')
    if data['intent_physically_verified'] or data['legal_interference_claimed'] or data['source_kind']!='synthetic_cpu':
        raise ValueError('Synthetic source has an unsupported intent or legal claim')
    for index,row in enumerate(data['frames']):
        if (row['frame'],row['video_frame'],row['native_frame'])!=(index,index,index) or row['time_s']!=index/20:
            raise ValueError('Frame/time identity differs')
        bike=row['bicycle'];motor=row['motor_vehicle']
        if bike['class']!='human_powered_bicycle' or motor['class']!='motor_vehicle' or bike['actor_id']==motor['actor_id']:
            raise ValueError('Frozen actor or separate motorist source differs')
        if len(bike['body_xy_m'])!=4 or len(motor['body_xy_m'])!=4:
            raise ValueError('Original bodies absent')
        for actor in (bike,motor):
            if not all(math.isfinite(v) for p in actor['body_xy_m'] for v in p):
                raise ValueError('Nonfinite body')
    return data,sha(path),sha(road)

def main():
    reference=read('witness_1');intervention=read('witness_2')
    a,b=reference[0],intervention[0]
    if reference[2]!=intervention[2] or (a['law_id'],a['cell_id'],a['actor'])!=(b['law_id'],b['cell_id'],b['actor']):
        raise ValueError('Controlled law/cell/map differs')
    for index in range(75):
        if a['frames'][index]['bicycle']!=b['frames'][index]['bicycle'] or a['frames'][index]['motor_vehicle']!=b['frames'][index]['motor_vehicle']:
            raise ValueError('Pre-intervention original actor traces differ')
    if any(row['motor_vehicle']['brake_applied'] for row in a['frames']):
        raise ValueError('Reference motorist brakes')
    braking=[row['frame'] for row in b['frames'] if row['motor_vehicle']['brake_applied']]
    if braking!=list(range(75,250)):
        raise ValueError('Intervention motorist response differs')
    first_bike={case:next(row['frame'] for row in record['frames']
        if max(p[1] for p in row['bicycle']['body_xy_m'])>-7)
        for case,record in (('witness_1',a),('witness_2',b))}
    if not first_bike['witness_2']<first_bike['witness_1'] or first_bike['witness_2'] not in braking:
        raise ValueError('Controlled bicycle entry does not precede reference')
    print(json.dumps({'passed':True,'frames_per_case':480,'same_map_and_frozen_identity':True,
        'identical_actor_sources_before_frame':75,'motor_braking_frames':len(braking),
        'bicycle_entry_frames':first_bike,'source_sha256':{'witness_1':reference[1],'witness_2':intervention[1]},
        'intent_or_legal_claim':False},sort_keys=True))

if __name__=='__main__':main()
