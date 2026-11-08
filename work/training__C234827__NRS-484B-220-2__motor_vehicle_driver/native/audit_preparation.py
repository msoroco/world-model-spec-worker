"""Independently audit retained rotary raw/video/review/saved joins."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(s) for s in Path(path).read_text().splitlines()]


def audit():
    proof=json.loads((HERE/'preparation-proof.json').read_text())
    if proof.get('processor_sha256')!=sha(HERE/'prepare_rotary.py'):
        raise ValueError('Rotary preparation processor changed')
    total=0
    for positive in proof['positives']:
        case=positive['case']
        base=HERE/'preparation-fixtures'/case
        raw=base/'raw';saved=base/'saved'
        review=json.loads((base/'review.json').read_text())
        receipt=json.loads((saved/'preparation-receipt.json').read_text())
        source_hashes={name:sha(raw/name) for name in
            ('native-raw-ego.jsonl','native-map-readback.json','video_frames.jsonl')}
        source_hashes['forward_video']=sha(raw/'forward-video-stub.txt')
        if (source_hashes!=review['source_hashes'] or
                source_hashes!=positive['raw_source_hashes'] or
                source_hashes!=receipt['raw_source_hashes'] or
                receipt['review_sha256']!=sha(base/'review.json') or
                receipt['config_sha256']!=sha(HERE/'drafts'/case/'primary'/'config.json') or
                receipt['source_kind']!='synthetic_cpu' or receipt['delivery_ready']):
            raise ValueError('Rotary raw/review source binding differs')
        raw_rows=rows(raw/'native-raw-ego.jsonl')
        video_rows=rows(raw/'video_frames.jsonl')
        saved_rows=rows(saved/'native-observed.jsonl')
        frame_rows=rows(saved/'island-frames.jsonl')
        if any(len(part)!=240 for part in
               (raw_rows,video_rows,saved_rows,frame_rows,review['rows'])):
            raise ValueError('Rotary preparation frame coverage differs')
        hashes={name:sha(saved/name) for name in
            ('native-observed.jsonl','island-readback.json','island-frames.jsonl')}
        if hashes!=positive['saved_hashes'] or hashes!=receipt['saved_hashes']:
            raise ValueError('Rotary saved source binding differs')
        island=json.loads((saved/'island-readback.json').read_text())
        mapping=json.loads((raw/'native-map-readback.json').read_text())
        if (island['raw_source_hashes']!=source_hashes or
                island['review_sha256']!=sha(base/'review.json') or
                island['native_map_sha256']!=mapping['native_map_sha256'] or
                island['physical_island_verified'] or island['traffic_control_verified']):
            raise ValueError('Rotary island readback provenance differs')
        first=raw_rows[0]['native_frame']
        actor=raw_rows[0]['ego']['actor_id']
        for i,(raw_row,video,saved_row,frame,sight) in enumerate(zip(
                raw_rows,video_rows,saved_rows,frame_rows,review['rows'])):
            ego=raw_row['ego'];center=ego['center_native_xyz_m']
            velocity=ego['velocity_native_xyz_mps']
            if (raw_row['frame']!=i or raw_row['native_frame']!=first+i or
                    video['video_frame']!=i or video['native_frame']!=first+i or
                    sight['frame']!=i or sight['native_frame']!=first+i or
                    sight['camera_frame']!=first+i or
                    saved_row['frame']!=i or saved_row['native_frame']!=first+i or
                    frame['frame']!=i or frame['native_frame']!=first+i or
                    frame['camera_frame']!=first+i or
                    ego['actor_id']!=actor or
                    abs(raw_row['time_s']-video['time_s'])>1e-4 or
                    abs(raw_row['time_s']-sight['time_s'])>1e-4 or
                    abs(saved_row['time_s']-(i+1)/20)>1e-6 or
                    abs(frame['time_s']-(i+1)/20)>1e-6 or
                    saved_row['ego_x_m']!=center[0] or
                    saved_row['ego_y_m']!=-center[1] or
                    saved_row['ego_heading_deg']!=(-ego['yaw_deg'])%360 or
                    saved_row['ego_speed_mps']!=ego['speed_mps'] or
                    saved_row['lane_id']!=raw_row['native_lane_id'] or
                    frame['island_visible']!=sight['island_visible'] or
                    saved_row['ego_body_xy_m']!=[
                        [point[0],-point[1]] for point in ego['body_native_xyz_m']] or
                    abs(ego['speed_mps']-math.sqrt(sum(v*v for v in velocity)))>.1):
                raise ValueError('Rotary independently joined row differs')
            total+=1
    if [item['mutation'] for item in proof['negative_controls']]!=[
            'missing_video_frame','wrong_actor','body_inside_island',
            'wrong_camera_frame','wrong_road','wrong_velocity'] or not all(
            item['rejected'] for item in proof['negative_controls']):
        raise ValueError('Rotary preparation negative coverage differs')
    # Re-run each altered source against the preparer after the independent row
    # recomputation, so a stale rejection receipt cannot pass this audit.
    from prove_preparation import negative
    for item in proof['negative_controls']:
        if not negative('reference',item['mutation'])['rejected']:
            raise ValueError('Rotary preparation negative no longer rejected')
    result={'format':'c234827-independent-preparation-audit-v1',
        'proof_sha256':sha(HERE/'preparation-proof.json'),
        'raw_video_review_saved_rows_recomputed':total,
        'negative_controls_replayed':len(proof['negative_controls']),
        'original_native_observed':False,'delivery_ready':False}
    (HERE/'preparation-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    print(json.dumps(audit(),indent=2))
