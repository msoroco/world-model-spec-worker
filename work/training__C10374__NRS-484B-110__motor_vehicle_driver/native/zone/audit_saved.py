"""Independent C10374 raw/saved footprint and fallback audit."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]


def audit():
    copied=read(HERE/'offline/manifest.json')
    proof=read(HERE/'offline/saved-proof.json')
    compatibility=read(HERE/'offline/saved-compatibility.json')
    if proof['copied_manifest_sha256']!=sha(HERE/'offline/manifest.json') or \
       compatibility['positive']!=8 or compatibility['tamper_negative']!=72 or \
       len(copied['entries'])!=len(proof['entries'])!=8:
        raise ValueError('saved proof binding')
    total=0;pairs={}
    for entry,result in zip(copied['entries'],proof['entries']):
        bundle=HERE/entry['bundle'];suffix=bundle.parent.name;candidate=bundle.name
        raw=HERE/'offline/raw-fixtures'/suffix/candidate
        saved=HERE/'offline/saved-fixtures'/suffix/candidate
        cfg=read(bundle/'config.json');mapping=read(raw/'native-map-readback.json')
        receipt=read(saved/'preparation-receipt.json')
        actors,videos,reviews=(rows(raw/name) for name in
            ('native-raw-actors.jsonl','video_frames.jsonl','frame-review.jsonl'))
        obs,cams,prepared_reviews=(rows(saved/name) for name in
            ('native-observed.jsonl','camera-frames.jsonl','frame-review.jsonl'))
        if any(sha(raw/name)!=digest for name,digest in result['raw_hashes'].items()) or \
           any(sha(saved/name)!=digest for name,digest in result['saved_hashes'].items()) or \
           receipt['config_sha256']!=sha(bundle/'config.json') or \
           mapping['road_sha256']!=sha(bundle/'alley-zone.xodr') or \
           len(mapping['native_zone_delimiters'])!=4 or \
           len(actors)!=len(videos)!=len(reviews)!=len(obs)!=len(cams)!=len(prepared_reviews)!=240:
            raise ValueError('raw source binding')
        xmin,xmax,ymin,ymax=cfg['zone_rectangle_xy_m']
        overlap=reviewed=visible=0
        for i,(a,v,r,o,c,s) in enumerate(zip(actors,videos,reviews,obs,cams,prepared_reviews)):
            if a['frame']!=i or a['native_frame']!=v['native_frame'] or \
               a['native_frame']!=r['native_frame'] or a['ego']!=o['ego'] or \
               c['video_frame']!=i or s!=r or o['source_kind']!='synthetic_cpu':
                raise ValueError('raw-to-saved frame join')
            body=o['ego']['body_native_xyz_m'];xs=[p[0] for p in body];ys=[p[1] for p in body]
            overlap+=int(max(xs)>=xmin and min(xs)<=xmax and
                         max(ys)>=ymin and min(ys)<=ymax and o['ego']['speed_mps']>.1)
            reviewed+=int(r['zone_boundary_pixel_reviewed'])
            visible+=int(r['zone_boundary_pixel_reviewed'] and r['zone_boundary_visible'] is True)
            total+=1
        m=result['measurement'];t=result['routing']['triggers']
        expected_mismatch=(overlap==0 if cfg['requested_zone_route'] else overlap>0)
        if m['moving_body_rectangle_overlap_frames']!=overlap or \
           m['reviewed_boundary_frames']!=reviewed or \
           m['reviewed_visible_boundary_frames']!=visible or \
           t['fallback1']['eligible']!=expected_mismatch or \
           t['fallback2']['eligible']!=(reviewed<240 or visible<1) or \
           t['fallback3']['eligible'] is not True or m['delivery_ready']:
            raise ValueError('independent overlap or trigger')
        pairs.setdefault(candidate,{})[suffix]=(cfg['requested_ego_speed_mps'],
            cfg['camera_policy'],cfg['stop_x_m'],cfg['zone_rectangle_xy_m'])
    if len(pairs)!=4 or any(len(pair)!=2 or len(set(map(str,pair.values())))!=1
                            for pair in pairs.values()):
        raise ValueError('controlled comparison pair')
    return {'format':'c10374-zone-independent-saved-audit-v1',
            'cases':8,'frames_audited':total,'controlled_pairs':4,
            'physical_zone_designated':False,'delivery_ready':False}


if __name__=='__main__':print(json.dumps(audit()))
