"""Independent c2 saved and routing audit from fixture rows and hashes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    copied = read(HERE/'offline/manifest.json')
    saved = read(HERE/'offline/saved-proof.json')
    proof = read(HERE/'offline/saved-compatibility.json')
    if saved['copied_manifest_sha256'] != sha(HERE/'offline/manifest.json') or \
       proof['positive'] != 8 or proof['tamper_negative'] != 96 or \
       len(copied['entries']) != len(saved['entries']) != 8:
        raise ValueError('source and proof')
    total = 0
    for entry, result in zip(copied['entries'], saved['entries']):
        bundle = HERE/entry['bundle']
        raw = HERE/'offline/raw-fixtures'/bundle.parent.name/bundle.name
        prepared = HERE/'offline/saved-fixtures'/bundle.parent.name/bundle.name
        cfg = read(bundle/'config.json')
        mapping = read(raw/'native-map-readback.json')
        survey = mapping['private_way_full_window_survey']
        receipt = read(prepared/'preparation-receipt.json')
        actors, videos, reviews = (rows(raw/name) for name in
            ('native-raw-actors.jsonl','video_frames.jsonl','frame-review.jsonl'))
        obs, cams, saved_reviews = (rows(prepared/name) for name in
            ('native-observed.jsonl','camera-frames.jsonl','frame-review.jsonl'))
        if any(sha(raw/name) != digest for name,digest in result['raw_hashes'].items()) or \
           any(sha(prepared/name) != digest for name,digest in result['saved_hashes'].items()) or \
           receipt['raw_hashes']['native-map-readback.json'] != sha(raw/'native-map-readback.json') or \
           mapping['private_way_verified'] != cfg['private_way_requested'] or \
           mapping['generated_junction_connection_verified'] != cfg['private_way_requested'] or \
           len(survey) != 131 or \
           any(point['x_m'] != 10+i*.5 for i,point in enumerate(survey)) or \
           (214 in [point['road_id'] for point in survey]) != cfg['private_way_requested'] or \
           len(actors) != len(videos) != len(reviews) != len(obs) != len(cams) != len(saved_reviews) != 240:
            raise ValueError('fixture binding')
        plane = cfg['private_way_x_m']
        full = []
        spur_frames = []
        right_pass = reviewed = visible = 0
        for i,(a,v,r,o,c,s) in enumerate(zip(actors,videos,reviews,obs,cams,saved_reviews)):
            if a['frame'] != v['video_frame'] or a['frame'] != r['frame'] or \
               a['native_frame'] != v['native_frame'] or \
               a['native_frame'] != r['native_frame'] or \
               o['ego'] != a['ego'] or o['lead'] != a['lead'] or \
               c['video_frame'] != i or s != r or \
               o['private_way_verified'] != cfg['private_way_requested']:
                raise ValueError('raw-to-saved join')
            ego,lead = o['ego']['body_native_xyz_m'],o['lead']['body_native_xyz_m']
            ex,ey=[p[0] for p in ego],[p[1] for p in ego]
            lx,ly=[p[0] for p in lead],[p[1] for p in lead]
            occupied=o['observed_ego_lane_id']==-2 and min(ey)>=-7 and max(ey)<=-3.5
            full.append(occupied)
            if occupied and min(ex)<=plane<=max(ex): spur_frames.append(i)
            right_pass+=int(min(ex)>max(lx) and max(ey)<min(ly))
            reviewed+=int(r['private_way_pixel_reviewed'] and r['pavement_pixel_reviewed'])
            visible+=int(r['private_way_pixel_reviewed'] and r['private_way_visible'] is True)
            total+=1
        crossed=bool(spur_frames) and any(
            obs[i-1]['ego']['center_native_xyz_m'][0]<plane<=obs[i]['ego']['center_native_xyz_m'][0]
            for i in range(1,240) if full[i-1] and full[i])
        m=result['measurement'];t=result['routing']['triggers']
        if m['full_body_unmarked_frames']!=sum(full) or \
           m['body_at_spur_plane_frames']!=spur_frames or \
           m['body_crossed_spur_plane']!=crossed or \
           m['right_pass_frames']!=right_pass or \
           m['reviewed_private_way_pavement_frames']!=reviewed or \
           m['reviewed_private_way_visible_frames']!=visible or \
           t['fallback1']['eligible']!=(right_pass<1 or (cfg['private_way_requested'] and not crossed)) or \
           t['fallback2']['eligible']!=(reviewed<240) or \
           not t['fallback3']['eligible'] or m['delivery_ready']:
            raise ValueError('independent measurement/routing')
    return {'format':'c146314-paragraph-c2-independent-saved-audit-v1',
            'frames_audited':total,'cases':8,'delivery_ready':False}


if __name__=='__main__': print(json.dumps(audit()))
