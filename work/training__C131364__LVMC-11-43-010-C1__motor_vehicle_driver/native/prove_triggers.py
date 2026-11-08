"""Retain visibility and lane-ambiguity variants for measured routing."""
import hashlib
import json
import math
from pathlib import Path
import shutil

from measure_saved import rows
from triggers import route

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def variants():
    source=HERE/'saved-fixtures'/'witness_1'
    for variant in ('entry-occluded','lane-deviation'):
        target=HERE/'trigger-fixtures'/variant
        if target.exists():shutil.rmtree(target)
        shutil.copytree(source,target)
        if variant=='entry-occluded':
            path=target/'camera-frames.jsonl';data=rows(path)
            for row in data[:40]:row['left_lane_visible']=False
        else:
            path=target/'native-observed.jsonl';data=rows(path)
            for row in data:
                x,y=row['ego_x_m'],row['ego_y_m'];r=math.hypot(x,y)
                dx,dy=.3*x/r,.3*y/r
                row['ego_x_m']=round(x+dx,6);row['ego_y_m']=round(y+dy,6)
                row['ego_body_xy_m']=[[round(px+dx,6),round(py+dy,6)]
                                      for px,py in row['ego_body_xy_m']]
        path.write_text(''.join(json.dumps(row)+'\n' for row in data))

def prove():
    variants()
    positives=[]
    for name in ('witness_1','witness_2','entry-occluded','lane-deviation'):
        folder=(HERE/'saved-fixtures'/name if name.startswith('witness')
                else HERE/'trigger-fixtures'/name)
        result=route(folder)
        flags=result['triggered']
        if (flags['fallback1_slow_for_visibility']!=(name=='entry-occluded') or
            flags['fallback2_elevated_overview_for_lane_ambiguity']!=(name=='lane-deviation') or
            not flags['fallback3_stop_for_unverified_exit_or_roundabout'] or
            result['selected_candidate'] is not None):
            raise ValueError('C131364 measured fallback route differs')
        positives.append({'variant':name,'routing':result})
    folder=HERE/'saved-fixtures'/'witness_1'
    hashes={name:sha(folder/name) for name in ('native-observed.jsonl','lane-readback.json','camera-frames.jsonl')}
    hashes['camera-frames.jsonl']='0'*64
    try:route(folder,hashes)
    except ValueError:pass
    else:raise ValueError('C131364 stale saved hash accepted')
    result={'format':'c131364-trigger-proof-v1','positives':positives,
            'negative_controls':[{'mutation':'wrong_camera_hash','rejected':True}],
            'actual_left_exit_observed':False,'delivery_ready':False}
    (HERE/'trigger-proof.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps({'variants':len(prove()['positives'])}))
