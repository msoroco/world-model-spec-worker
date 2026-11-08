"""Exercise raw-to-saved one-way preparation with source-bound controls."""
import json
from pathlib import Path
import shutil
import tempfile

from prepare_one_way import prepare, sha

HERE = Path(__file__).resolve().parent


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, values):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in values))


def build(case):
    base = HERE/'preparation-fixtures'/case
    raw = base/'raw'
    raw.mkdir(parents=True, exist_ok=True)
    saved = HERE/'saved-fixtures'/case
    source_rows = rows(saved/'native-observed.jsonl')
    signs = rows(saved/'sign-frames.jsonl')
    raw_rows, frames, review_rows = [], [], []
    for item, sign in zip(source_rows, signs):
        x, y = item['ego_x_m'], -item['ego_y_m']
        body = [[x+dx, y+dy, 0.5] for dx,dy in
                ((-2,-.9),(-2,.9),(2,.9),(2,-.9))]
        raw_rows.append({'frame':item['frame'], 'native_frame':item['native_frame'],
            'time_s':item['time_s'], 'source_kind':'synthetic_cpu',
            'native_lane_id':item['lane_id'],
            'ego':{'actor_id':42, 'blueprint':'vehicle.tesla.model3',
                   'center_native_xyz_m':[x,y,0.5],
                   'velocity_native_xyz_mps':[item['ego_velocity_x_mps'],0,0],
                   'yaw_deg':item['ego_heading_deg'],
                   'speed_mps':item['ego_speed_mps'],
                   'body_native_xyz_m':body}})
        frames.append({'video_frame':item['frame'],
                       'native_frame':item['native_frame'],'time_s':item['time_s']})
        review_rows.append({'frame':item['frame'],
            'native_frame':item['native_frame'],'camera_frame':item['native_frame'],
            'time_s':item['time_s'],'visible_sign_ids':sign['visible_sign_ids']})
    write_rows(raw/'native-raw-ego.jsonl',raw_rows)
    write_rows(raw/'video_frames.jsonl',frames)
    config = HERE/'drafts'/case/'primary'/'config.json'
    config_data = json.loads(config.read_text())
    (raw/'native-map-readback.json').write_text(json.dumps({
        'road_sha256':config_data['road_sha256'],
        'driving_lane_ids':{'-1':-1,'-2':-2},
        'authored_sign_request_ids':[101,102],
        'native_map_sha256':'1'*64,
        'physical_sign_verified':False,
        'designation_authority_verified':False},indent=2)+'\n')
    (raw/'forward-video-stub.txt').write_text('synthetic CPU video placeholder; no pixels\n')
    hashes={name:sha(raw/name) for name in
        ('native-raw-ego.jsonl','native-map-readback.json','video_frames.jsonl')}
    hashes['forward_video']=sha(raw/'forward-video-stub.txt')
    (base/'sign-review.json').write_text(json.dumps({
        'format':'c150916-sign-frame-review-v1',
        'source_kind':'synthetic_cpu','review_provenance':'synthetic_cpu',
        'source_hashes':hashes,'rows':review_rows},indent=2)+'\n')
    (base/'designation-source.json').write_text(json.dumps({
        'format':'c150916-designation-source-v1',
        'source_provenance':'synthetic_cpu',
        'road_sha256':config_data['road_sha256'],
        'designated_direction_x':1,
        'record_reference':None},indent=2)+'\n')
    return base, config


def prove():
    positives=[]
    for case in ('designated','opposite'):
        base, config=build(case)
        output=base/'prepared'
        if output.exists():shutil.rmtree(output)
        receipt=prepare(base/'raw',base/'sign-review.json',
                        base/'designation-source.json',config,output)
        if (receipt['source_kind']!='synthetic_cpu' or
                receipt['measurement']['direction_matches_designation']!=(case=='designated') or
                receipt['delivery_ready']):
            raise AssertionError('Prepared synthetic one-way case differs')
        positives.append({'case':case,'raw_source_hashes':receipt['raw_source_hashes'],
                          'saved_hashes':receipt['saved_hashes'],
                          'measurement':receipt['measurement']})
    base, config=build('designated')
    negatives=[]
    for mutation in ('changed_video','missing_review_frame','wrong_camera_frame',
                     'wrong_actor_id','wrong_lane','changed_designation_source'):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            folder=Path(temporary)
            shutil.copytree(base/'raw',folder/'raw')
            shutil.copy2(base/'sign-review.json',folder/'sign-review.json')
            shutil.copy2(base/'designation-source.json',folder/'designation-source.json')
            if mutation=='changed_video':
                path=folder/'raw'/'forward-video-stub.txt';path.write_bytes(path.read_bytes()+b'changed')
            elif mutation in ('missing_review_frame','wrong_camera_frame'):
                path=folder/'sign-review.json';data=json.loads(path.read_text())
                if mutation=='missing_review_frame':data['rows'].pop()
                else:data['rows'][60]['camera_frame']=-1
                path.write_text(json.dumps(data)+'\n')
            elif mutation in ('wrong_actor_id','wrong_lane'):
                path=folder/'raw'/'native-raw-ego.jsonl';data=rows(path)
                if mutation=='wrong_actor_id':data[60]['ego']['actor_id']=-1
                else:data[60]['native_lane_id']=3
                write_rows(path,data)
                review_path=folder/'sign-review.json';review=json.loads(review_path.read_text())
                review['source_hashes']['native-raw-ego.jsonl']=sha(path)
                review_path.write_text(json.dumps(review)+'\n')
            else:
                path=folder/'designation-source.json';data=json.loads(path.read_text())
                data['designated_direction_x']=-1;path.write_text(json.dumps(data)+'\n')
            try:
                prepare(folder/'raw',folder/'sign-review.json',
                        folder/'designation-source.json',config,folder/'prepared')
            except (ValueError,TypeError,KeyError):
                negatives.append({'mutation':mutation,'rejected':True})
            else:raise AssertionError('Raw one-way mutation accepted: '+mutation)
    proof={'format':'c150916-raw-preparation-proof-v1',
           'assignment_id':HERE.parent.name,
           'processor_sha256':sha(HERE/'prepare_one_way.py'),
           'positives':positives,'negative_controls':negatives,
           'original_native_observed':False,'delivery_ready':False}
    (HERE/'preparation-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    result=prove()
    print(json.dumps({'positives':len(result['positives']),
                      'negatives':len(result['negative_controls'])}))
