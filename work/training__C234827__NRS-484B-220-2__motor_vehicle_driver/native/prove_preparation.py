"""Retain synthetic raw-to-saved rotary positives and semantic negatives."""
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile

from prepare_rotary import prepare, sha

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
OUT = HERE/'preparation-fixtures'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))


def source_hashes(raw):
    return {name:sha(raw/name) for name in
        ('native-raw-ego.jsonl','native-map-readback.json','video_frames.jsonl','forward_video')}


def build(case):
    folder = OUT/case
    raw = folder/'raw'
    raw.mkdir(parents=True)
    config = HERE/'drafts'/case/'primary'/'config.json'
    cfg = json.loads(config.read_text())
    saved = HERE/'saved-fixtures'/case
    observed = [json.loads(line) for line in (saved/'native-observed.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in (saved/'island-frames.jsonl').read_text().splitlines()]
    rows, video, reviews = [], [], []
    for item, frame in zip(observed, frames):
        i = item['frame']
        heading = math.radians(item['ego_heading_deg'])
        speed = item['ego_speed_mps']
        ego = {'actor_id': 73, 'blueprint': 'vehicle.tesla.model3',
               'center_native_xyz_m': [item['ego_x_m'], -item['ego_y_m'], 1.0],
               'yaw_deg': (-item['ego_heading_deg'])%360,
               'velocity_native_xyz_mps': [speed*math.cos(heading), -speed*math.sin(heading), 0],
               'speed_mps': speed,
               'body_native_xyz_m': [[point[0], -point[1], 1.0] for point in item['ego_body_xy_m']]}
        rows.append({'frame': i, 'native_frame': item['native_frame'],
            'time_s': item['time_s'], 'source_kind': 'synthetic_cpu',
            'case': case, 'native_lane_id': item['lane_id'], 'ego': ego})
        video.append({'video_frame': i, 'native_frame': item['native_frame'],
            'time_s': item['time_s']})
        reviews.append({'frame': i, 'native_frame': item['native_frame'],
            'camera_frame': item['native_frame'], 'time_s': item['time_s'],
            'island_visible': frame['island_visible']})
    write_rows(raw/'native-raw-ego.jsonl', rows)
    write_rows(raw/'video_frames.jsonl', video)
    write_json(raw/'native-map-readback.json', {
        'road_sha256': cfg['road_sha256'],
        'island_geometry_sha256': cfg['island_geometry_sha256'],
        'native_map_sha256': '1'*64, 'center_xy_m': [0,0],
        'island_radius_m': 15, 'driving_lane_ids': [-2,-1],
        'physical_island_verified': False, 'traffic_control_verified': False})
    (raw/'forward-video-stub.txt').write_text('synthetic frame-map fixture only\n')
    review = {'format': 'c234827-island-frame-review-v1',
        'source_kind': 'synthetic_cpu', 'review_provenance': 'synthetic_cpu',
        'source_hashes': {
            'native-raw-ego.jsonl':sha(raw/'native-raw-ego.jsonl'),
            'native-map-readback.json':sha(raw/'native-map-readback.json'),
            'video_frames.jsonl':sha(raw/'video_frames.jsonl'),
            'forward_video':sha(raw/'forward-video-stub.txt')}, 'rows': reviews}
    write_json(folder/'review.json', review)
    receipt = prepare(raw, folder/'review.json', config, folder/'saved')
    if (receipt['measurement']['source_kind'] != 'synthetic_cpu' or
            not receipt['measurement']['half_circle_passage_observed'] or
            not receipt['measurement']['continuous_requested_side'] or
            receipt['delivery_ready']):
        raise ValueError('Synthetic rotary raw preparation positive differs')
    return {'case':case, 'raw_source_hashes':receipt['raw_source_hashes'],
            'saved_hashes':receipt['saved_hashes'], 'measurement':receipt['measurement']}


def negative(case, mutation):
    source=OUT/case
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        shutil.copytree(source/'raw',root/'raw')
        shutil.copy2(source/'review.json',root/'review.json')
        raw=root/'raw'; review=json.loads((root/'review.json').read_text())
        if mutation=='missing_video_frame':
            p=raw/'video_frames.jsonl'; p.write_text('\n'.join(p.read_text().splitlines()[:-1])+'\n')
        elif mutation=='wrong_actor':
            p=raw/'native-raw-ego.jsonl'; rows=[json.loads(s) for s in p.read_text().splitlines()]
            rows[75]['ego']['actor_id']=74;write_rows(p,rows)
        elif mutation=='body_inside_island':
            p=raw/'native-raw-ego.jsonl';rows=[json.loads(s) for s in p.read_text().splitlines()]
            rows[75]['ego']['body_native_xyz_m'][0][0]=0;write_rows(p,rows)
        elif mutation=='wrong_camera_frame':
            review['rows'][75]['camera_frame']+=1
        elif mutation=='wrong_road':
            p=raw/'native-map-readback.json';value=json.loads(p.read_text())
            value['road_sha256']='0'*64;write_json(p,value)
        elif mutation=='wrong_velocity':
            p=raw/'native-raw-ego.jsonl';rows=[json.loads(s) for s in p.read_text().splitlines()]
            rows[75]['ego']['velocity_native_xyz_mps']=[0,0,0];write_rows(p,rows)
        else:raise ValueError('Unknown mutation')
        if mutation!='missing_video_frame':
            review['source_hashes']={
                'native-raw-ego.jsonl':sha(raw/'native-raw-ego.jsonl'),
                'native-map-readback.json':sha(raw/'native-map-readback.json'),
                'video_frames.jsonl':sha(raw/'video_frames.jsonl'),
                'forward_video':sha(raw/'forward-video-stub.txt')}
        write_json(root/'review.json',review)
        try:
            prepare(raw,root/'review.json',HERE/'drafts'/case/'primary'/'config.json',root/'saved')
        except ValueError:
            return {'mutation':mutation,'rejected':True}
        raise AssertionError('Rotary raw preparation accepted '+mutation)


def main():
    if OUT.exists():shutil.rmtree(OUT)
    positives=[build(case) for case in ('reference','contrast')]
    controls=[negative('reference',mutation) for mutation in
        ('missing_video_frame','wrong_actor','body_inside_island',
         'wrong_camera_frame','wrong_road','wrong_velocity')]
    result={'format':'c234827-rotary-preparation-proof-v1',
        'processor_sha256':sha(HERE/'prepare_rotary.py'),
        'positives':positives,'negative_controls':controls,
        'original_native_observed':False,'delivery_ready':False}
    write_json(HERE/'preparation-proof.json',result)
    return result


if __name__=='__main__':
    result=main();print(json.dumps({'positives':len(result['positives']),
        'negatives':len(result['negative_controls'])}))
