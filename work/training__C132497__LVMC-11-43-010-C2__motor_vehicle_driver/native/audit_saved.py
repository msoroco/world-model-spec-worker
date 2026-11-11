"""Independently recompute all retained C132497 synthetic saved body/phase rows."""
import hashlib
import json
import math
from pathlib import Path

CASE=Path(__file__).resolve().parent.parent
NATIVE=CASE/'native'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def audit():
    manifest=json.loads((NATIVE/'saved-manifest.json').read_text())
    if manifest['format']!='c132497-synthetic-saved-v1' or len(manifest['entries'])!=8:
        raise ValueError('C132497 synthetic fixture inventory differs')
    checked=0;contained=0;exits=0
    for entry in manifest['entries']:
        w,c=entry['witness'],entry['candidate_id']
        bundle=CASE/'offline'/'bundles'/w/c
        saved=bundle/'saved';cfg=json.loads((bundle/'config.json').read_text())
        if entry['sha256']!={name:sha(saved/name) for name in entry['sha256']}:
            raise ValueError('C132497 saved copied source differs')
        observed=rows(saved/'native-observed.jsonl')
        frames=rows(saved/'camera-frames.jsonl')
        if len(observed)!=240 or len(frames)!=240:
            raise ValueError('C132497 saved frame count differs')
        phases=[]
        for i,(row,frame) in enumerate(zip(observed,frames)):
            if (row['frame']!=i or frame['frame']!=i or
                row['native_frame']!=frame['camera_frame'] or
                row['lane_id']!=cfg['requested_lane_id'] or
                row['source_kind']!='synthetic_cpu' or
                row['actual_exit_observed']):
                raise ValueError('C132497 saved independent join differs')
            phases.append(row['phase']);checked+=1
            if row['phase']=='circulation':
                radius=math.hypot(row['ego_x_m']-22,row['ego_y_m']+22)
                if abs(radius-cfg['requested_arc_radius_m'])>.5:
                    raise ValueError('C132497 saved lane center differs')
                lower,upper=(15,18.5) if w=='reference' else (18.5,22)
                if not all(lower<=math.hypot(p[0]-22,p[1]+22)<=upper
                    for p in row['ego_body_xy_m']):
                    raise ValueError('C132497 saved body outside authored lane')
                contained+=1
        if set(phases)!={'entry','circulation','exit'}:
            raise ValueError('C132497 saved exit phases differ')
        if c=='fallback3' and (any(row['ego_speed_mps']!=0 for row in observed[:40]) or
            observed[40]['ego_speed_mps']<=0):
            raise ValueError('C132497 saved dwell differs')
        exits+=phases.count('exit')
    result={'format':'c132497-independent-saved-audit-v1',
        'saved_manifest_sha256':sha(NATIVE/'saved-manifest.json'),
        'rows_recomputed':checked,'circulating_body_rows':contained,
        'authored_exit_phase_rows':exits,'original_native_observed':False,
        'delivery_ready':False}
    (CASE/'offline'/'audit-saved.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
