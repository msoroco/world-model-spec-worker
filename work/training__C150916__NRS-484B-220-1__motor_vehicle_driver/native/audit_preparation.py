"""Independently verify raw one-way joins and replay altered-source controls."""
import json
from pathlib import Path
import shutil
import tempfile

from prepare_one_way import prepare, sha

HERE=Path(__file__).resolve().parent


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path,values):
    path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in values))


def audit():
    path=HERE/'preparation-proof.json'
    proof=json.loads(path.read_text())
    mutations=['changed_video','missing_review_frame','wrong_camera_frame',
               'wrong_actor_id','wrong_lane','changed_designation_source']
    if (proof['format']!='c150916-raw-preparation-proof-v1' or
            proof['assignment_id']!=HERE.parent.name or
            proof['processor_sha256']!=sha(HERE/'prepare_one_way.py') or
            proof['original_native_observed'] or proof['delivery_ready'] or
            len(proof['positives'])!=2 or
            [item['mutation'] for item in proof['negative_controls']]!=mutations or
            not all(item['rejected'] is True for item in proof['negative_controls'])):
        raise ValueError('Raw preparation proof scope differs')
    checked=0
    for item in proof['positives']:
        case=item['case']
        if case not in ('designated','opposite'):
            raise ValueError('Raw preparation case differs')
        base=HERE/'preparation-fixtures'/case
        raw=base/'raw'
        prepared=base/'prepared'
        config=HERE/'drafts'/case/'primary'/'config.json'
        source={name:sha(raw/name) for name in
                ('native-raw-ego.jsonl','native-map-readback.json','video_frames.jsonl')}
        source['forward_video']=sha(raw/'forward-video-stub.txt')
        saved={name:sha(prepared/name) for name in
               ('native-observed.jsonl','road-readback.json',
                'sign-frames.jsonl','designation-record.json')}
        if source!=item['raw_source_hashes'] or saved!=item['saved_hashes']:
            raise ValueError('Raw or saved preparation hashes differ')
        review=json.loads((base/'sign-review.json').read_text())
        original,frames,observed,signs=(rows(file) for file in
            (raw/'native-raw-ego.jsonl',raw/'video_frames.jsonl',
             prepared/'native-observed.jsonl',prepared/'sign-frames.jsonl'))
        if (len(original)!=240 or len(frames)!=240 or len(observed)!=240 or len(signs)!=240 or
                review['source_hashes']!=source or len(review['rows'])!=240):
            raise ValueError('Raw preparation row coverage differs')
        for i,(a,f,o,s,r) in enumerate(zip(original,frames,observed,signs,review['rows'])):
            if (a['frame']!=i or f['video_frame']!=i or o['frame']!=i or s['frame']!=i or
                    a['native_frame']!=f['native_frame'] or
                    a['native_frame']!=o['native_frame'] or
                    a['native_frame']!=s['native_frame'] or
                    a['native_frame']!=r['camera_frame'] or
                    f['time_s']!=a['time_s'] or r['time_s']!=a['time_s'] or
                    abs(o['time_s']-(i+1)/20)>1e-6 or s['time_s']!=o['time_s'] or
                    o['ego_x_m']!=a['ego']['center_native_xyz_m'][0] or
                    o['ego_y_m']!=-a['ego']['center_native_xyz_m'][1] or
                    o['ego_velocity_x_mps']!=a['ego']['velocity_native_xyz_mps'][0] or
                    o['lane_id']!=a['native_lane_id'] or
                    s['visible_sign_ids']!=r['visible_sign_ids']):
                raise ValueError('Independent raw, camera and saved join differs')
            checked+=1
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            target=Path(temporary)/'saved'
            receipt=prepare(raw,base/'sign-review.json',base/'designation-source.json',
                            config,target)
            if (receipt['saved_hashes']!=saved or
                    receipt['measurement']!=item['measurement'] or
                    receipt['delivery_ready']):
                raise ValueError('Raw preparation independent replay differs')
    if {item['case'] for item in proof['positives']}!={'designated','opposite'} or checked!=480:
        raise ValueError('Raw preparation case coverage incomplete')
    base=HERE/'preparation-fixtures'/'designated'
    config=HERE/'drafts'/'designated'/'primary'/'config.json'
    replayed=[]
    for mutation in mutations:
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            folder=Path(temporary)
            shutil.copytree(base/'raw',folder/'raw')
            shutil.copy2(base/'sign-review.json',folder/'sign-review.json')
            shutil.copy2(base/'designation-source.json',folder/'designation-source.json')
            if mutation=='changed_video':
                target=folder/'raw'/'forward-video-stub.txt'
                target.write_bytes(target.read_bytes()+b'changed')
            elif mutation in ('missing_review_frame','wrong_camera_frame'):
                target=folder/'sign-review.json';data=json.loads(target.read_text())
                if mutation=='missing_review_frame':data['rows'].pop()
                else:data['rows'][60]['camera_frame']=-1
                target.write_text(json.dumps(data)+'\n')
            elif mutation in ('wrong_actor_id','wrong_lane'):
                target=folder/'raw'/'native-raw-ego.jsonl';data=rows(target)
                if mutation=='wrong_actor_id':data[60]['ego']['actor_id']=-1
                else:data[60]['native_lane_id']=3
                write_rows(target,data)
                review_path=folder/'sign-review.json';review=json.loads(review_path.read_text())
                review['source_hashes']['native-raw-ego.jsonl']=sha(target)
                review_path.write_text(json.dumps(review)+'\n')
            else:
                target=folder/'designation-source.json';data=json.loads(target.read_text())
                data['designated_direction_x']=-1;target.write_text(json.dumps(data)+'\n')
            try:
                prepare(folder/'raw',folder/'sign-review.json',
                        folder/'designation-source.json',config,folder/'prepared')
            except (ValueError,TypeError,KeyError):replayed.append(mutation)
            else:raise ValueError('Independent raw negative accepted: '+mutation)
    result={'format':'c150916-independent-raw-preparation-audit-v1',
            'proof_sha256':sha(path),'joined_rows_checked':checked,
            'negative_controls_replayed':replayed,
            'original_native_observed':False,'delivery_ready':False}
    (HERE/'preparation-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(audit()))
