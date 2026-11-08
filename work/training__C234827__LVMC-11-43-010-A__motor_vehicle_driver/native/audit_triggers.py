"""Independently audit measured LVMC fallback decisions."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(s) for s in Path(path).read_text().splitlines()]


def audit():
    proof_path=HERE/'trigger-proof.json';proof=json.loads(proof_path.read_text())
    if (proof['format']!='c234827-lvmc-trigger-proof-v1' or
            proof['processor_sha256']!=sha(HERE/'triggers.py') or
            proof['saved_processor_sha256']!=sha(HERE/'measure_saved.py') or
            [row['variant'] for row in proof['positives']]!=
            ['witness_1','witness_2','entry-occluded','lane-deviation'] or
            [row['mutation'] for row in proof['negative_controls']]!=
            ['changed_observation','changed_motion','changed_readback'] or
            any(not row['rejected'] for row in proof['negative_controls']) or
            proof['original_native_observed'] or proof['delivery_ready']):
        raise ValueError('LVMC trigger proof coverage differs')
    total=0
    for item in proof['positives']:
        name=item['variant']
        folder=(HERE/'saved-fixtures'/name if name.startswith('witness_')
                else HERE/'trigger-fixtures'/name)
        hashes={key:sha(folder/key) for key in
            ('native-observed.jsonl','roundabout-readback.json','roundabout-frames.jsonl')}
        if hashes!=item['source_hashes']:
            raise ValueError('LVMC trigger source hash differs')
        observed=rows(folder/'native-observed.jsonl')
        frames=rows(folder/'roundabout-frames.jsonl')
        if len(observed)!=240 or len(frames)!=240:
            raise ValueError('LVMC trigger frame count differs')
        visible=0;deviation=0
        for i,(row,frame) in enumerate(zip(observed,frames)):
            if (row['frame']!=i or frame['frame']!=i or
                    row['native_frame']!=frame['native_frame'] or
                    frame['camera_frame']!=row['native_frame']):
                raise ValueError('LVMC trigger row join differs')
            if i<40 and frame['roundabout_visible']:visible+=1
            radius=math.hypot(row['ego_x_m'],row['ego_y_m'])
            deviation=max(deviation,abs(radius-(27.25 if row['lane_id']==-2 else 23.75)))
            total+=1
        route=item['routing'];flags=route['triggered']
        if (route['source_hashes']!=hashes or
                route['measurements']['entry_visible_frames']!=visible or
                abs(route['measurements']['maximum_lane_center_deviation_m']-
                    round(deviation,3))>.001 or
                flags['fallback1_slow_for_entry_visibility']!=(visible<20) or
                flags['fallback2_outer_lane_for_deviation']!=(round(deviation,3)>.2) or
                not flags['fallback3_stop_for_unverified_roundabout_or_control'] or
                route['selected_candidate'] is not None or route['delivery_ready']):
            raise ValueError('LVMC independent fallback decision differs')
    from prove_triggers import reject
    for item in proof['negative_controls']:
        if not reject(item['mutation'])['rejected']:
            raise ValueError('LVMC trigger negative no longer rejected')
    result={'format':'c234827-lvmc-independent-trigger-audit-v1',
        'proof_sha256':sha(proof_path),'saved_rows_recomputed':total,
        'negative_controls_replayed':3,'delivery_ready':False}
    (HERE/'trigger-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit(),indent=2))
