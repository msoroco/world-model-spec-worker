"""Independently recompute saved LVMC roundabout motion and negatives."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(s) for s in Path(path).read_text().splitlines()]


def audit():
    proof_path=HERE/'saved-proof.json'
    proof=json.loads(proof_path.read_text())
    if (proof['format']!='c234827-lvmc-saved-proof-v1' or
            proof['processor_sha256']!=sha(HERE/'measure_saved.py') or
            len(proof['positives'])!=2 or
            [row['mutation'] for row in proof['negative_controls']]!=
            ['wrong_hash','missing_actor','reverse_heading','body_inside',
             'wrong_speed','missing_camera'] or
            any(not row['rejected'] for row in proof['negative_controls']) or
            proof['original_native_observed'] or proof['roundabout_verified'] or
            proof['delivery_ready']):
        raise ValueError('LVMC saved proof coverage differs')
    total=0
    for positive in proof['positives']:
        witness=positive['witness'];folder=HERE/'saved-fixtures'/witness
        hashes={name:sha(folder/name) for name in
            ('native-observed.jsonl','roundabout-readback.json','roundabout-frames.jsonl')}
        if hashes!=positive['source_hashes']:
            raise ValueError('LVMC saved source hashes differ')
        observed=rows(folder/'native-observed.jsonl')
        frames=rows(folder/'roundabout-frames.jsonl')
        if len(observed)!=240 or len(frames)!=240:
            raise ValueError('LVMC saved frame count differs')
        ccw=cw=occupied=visible=0;progress=0.0;previous=None
        first=observed[0]['native_frame']
        for i,(row,frame) in enumerate(zip(observed,frames)):
            x,y=row['ego_x_m'],row['ego_y_m'];radius=math.hypot(x,y)
            heading=math.radians(row['ego_heading_deg'])
            cross=x*math.sin(heading)-y*math.cos(heading)
            if cross>1:ccw+=1
            elif cross< -1:cw+=1
            else:raise ValueError('LVMC ambiguous synthetic heading')
            theta=math.atan2(y,x)
            if previous is not None:
                step=math.atan2(math.sin(theta-previous),math.cos(theta-previous))
                progress+=step
                if abs(abs(step)*radius*20-row['ego_speed_mps'])>.35:
                    raise ValueError('LVMC independent speed/motion differs')
            previous=theta
            clearance=min(math.hypot(*point)-15 for point in row['ego_body_xy_m'])
            if clearance>0 and 20<=radius<=29:occupied+=1
            if (row['frame']!=i or frame['frame']!=i or
                    row['native_frame']!=first+i or frame['native_frame']!=first+i or
                    frame['camera_frame']!=first+i or
                    row['witness']!=witness or
                    abs(row['time_s']-(i+1)/20)>1e-6 or
                    abs(frame['time_s']-(i+1)/20)>1e-6 or
                    abs(radius-(27.25 if row['lane_id']==-2 else 23.75))>.5):
                raise ValueError('LVMC independent saved join differs')
            if frame['roundabout_visible']:visible+=1
            total+=1
        measured=positive['measurement']
        if (measured['rotation_frame_counts']['counterclockwise']!=ccw or
                measured['rotation_frame_counts']['clockwise']!=cw or
                measured['occupied_authored_ring_frames']!=occupied or
                measured['roundabout_visible_frames']!=visible or
                abs(measured['signed_angular_progress_rad']-progress)>1e-4 or
                measured['source_hashes']!=hashes or measured['delivery_ready']):
            raise ValueError('LVMC independent saved metrics differ')
    from prove_saved import reject
    for item in proof['negative_controls']:
        if not reject(item['mutation'])['rejected']:
            raise ValueError('LVMC saved negative no longer rejected')
    result={'format':'c234827-lvmc-independent-saved-audit-v1',
        'proof_sha256':sha(proof_path),'saved_rows_recomputed':total,
        'negative_controls_replayed':6,'original_native_observed':False,
        'delivery_ready':False}
    (HERE/'saved-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit(),indent=2))
