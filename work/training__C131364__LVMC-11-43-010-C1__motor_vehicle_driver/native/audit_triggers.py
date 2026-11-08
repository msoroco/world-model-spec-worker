"""Independently recompute four C131364 measured fallback decisions."""
import hashlib
import json
import math
from pathlib import Path

from measure_saved import rows, sha
from triggers import route

HERE=Path(__file__).resolve().parent

def audit():
    path=HERE/'trigger-proof.json'
    proof=json.loads(path.read_text())
    if (len(proof['positives'])!=4 or len(proof['negative_controls'])!=1 or
        proof['delivery_ready'] or proof['actual_left_exit_observed']):
        raise ValueError('C131364 trigger coverage differs')
    total=0
    for item in proof['positives']:
        name=item['variant']
        folder=(HERE/'saved-fixtures'/name if name.startswith('witness')
                else HERE/'trigger-fixtures'/name)
        actual=route(folder,item['routing']['source_hashes'])
        if actual!=item['routing']:raise ValueError('C131364 routed receipt differs')
        observed=rows(folder/'native-observed.jsonl')
        frames=rows(folder/'camera-frames.jsonl')
        entry=sum(row['left_lane_visible'] for row in frames[:40])
        lane=-1 if observed[0]['witness']=='witness_1' else -2
        radius=23.75 if lane==-1 else 27.25
        deviation=max(abs(math.hypot(row['ego_x_m'],row['ego_y_m'])-radius)
                      for row in observed)
        flags=actual['triggered']
        if (flags['fallback1_slow_for_visibility']!=(entry<20) or
            flags['fallback2_elevated_overview_for_lane_ambiguity']!=(deviation>.2) or
            not flags['fallback3_stop_for_unverified_exit_or_roundabout'] or
            actual['selected_candidate'] is not None):
            raise ValueError('C131364 independent trigger decision differs')
        total+=len(observed)
    folder=HERE/'saved-fixtures'/'witness_1'
    hashes={name:sha(folder/name) for name in ('native-observed.jsonl','lane-readback.json','camera-frames.jsonl')}
    hashes['camera-frames.jsonl']='0'*64
    try:route(folder,hashes)
    except ValueError:pass
    else:raise ValueError('C131364 changed camera hash accepted')
    result={'format':'c131364-independent-trigger-audit-v1',
            'proof_sha256':sha(path),'saved_rows_recomputed':total,
            'negative_controls_replayed':1,'delivery_ready':False}
    (HERE/'trigger-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
