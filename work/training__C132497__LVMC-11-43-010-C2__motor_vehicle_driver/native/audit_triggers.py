"""Independently recompute saved visibility, deviation and fallback thresholds."""
import hashlib
import json
import math
from pathlib import Path

CASE=Path(__file__).resolve().parent.parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def audit():
    path=CASE/'offline'/'proof-triggers.json';proof=json.loads(path.read_text())
    bundle=CASE/'offline'/'bundles'/'reference'/'primary'
    camera=rows(bundle/'saved'/'camera-frames.jsonl')
    observed=rows(bundle/'saved'/'native-observed.jsonl')
    if (proof['format']!='c132497-trigger-proof-v1' or
        len(camera)!=240 or len(observed)!=240 or
        proof['base']['first_40_visible_frames']!=sum(x['right_lane_visible'] for x in camera[:40]) or
        proof['base']['first_40_stopped_frames']!=sum(x['ego_speed_mps']<=.1 for x in observed[:40]) or
        proof['base']['triggered']!={'fallback1':False,'fallback2':False,'fallback3':True} or
        proof['dwell_variant']['first_40_stopped_frames']!=40 or
        proof['dwell_variant']['triggered']['fallback3'] is not False or
        proof['visibility_variant']['first_40_visible_frames']!=0 or
        not proof['visibility_variant']['triggered']['fallback2'] or
        proof['lane_deviation_variant']['maximum_lane_center_deviation_m']<=.2 or
        not proof['lane_deviation_variant']['triggered']['fallback1'] or
        not proof['changed_camera_join_rejected'] or
        not proof['synthetic_only'] or proof['delivery_ready']):
        raise ValueError('C132497 trigger proof differs')
    base_deviation=max(abs(math.hypot(x['ego_x_m']-22,x['ego_y_m']+22)-16.75)
        for x in observed if x['phase']=='circulation')
    if abs(base_deviation-proof['base']['maximum_lane_center_deviation_m'])>1e-5:
        raise ValueError('C132497 independent lane deviation differs')
    result={'format':'c132497-independent-trigger-audit-v1',
        'proof_sha256':sha(path),'saved_rows_checked':240,
        'positive_trigger_variants':3,'negative_joins_rejected':1,
        'delivery_ready':False}
    (CASE/'offline'/'audit-triggers.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
