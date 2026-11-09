"""Independent exact-request and raw-to-saved CPU audit for C109137."""
import json
import math
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET
from build import CASES, POLICIES, FRAMES, RATE, request_rows, road
from check import check
from prove_saved import fixture, put
from saved import process, sha

HERE=Path(__file__).resolve().parent

def geometry_audit(path):
    root=ET.parse(path).getroot()
    roads={r.get('id'):r for r in root.findall('./road')}
    assert set(roads)=={'217','218','219','220','221'}
    geom={rid:r.find('./planView/geometry') for rid,r in roads.items()}
    def origin(rid):
        return float(geom[rid].get('x')),float(geom[rid].get('y'))
    west_end=(origin('217')[0]+float(roads['217'].get('length')),origin('217')[1])
    straight_start=origin('220')
    straight_end=(straight_start[0]+float(roads['220'].get('length')),straight_start[1])
    east_start=origin('219')
    assert west_end==straight_start==(50,0)
    assert straight_end==east_start==(55,0)
    radius=1/float(geom['221'].find('./arc').get('curvature'))
    sweep=float(geom['221'].get('length'))/radius
    turn_end=(origin('221')[0]+radius*math.sin(sweep),
              origin('221')[1]+radius*(1-math.cos(sweep)))
    assert math.dist(turn_end,origin('218'))<1e-8
    assert abs(sweep-float(geom['218'].get('hdg')))<1e-8
    assert math.dist((west_end[0],west_end[1]-1.75),
                     (origin('221')[0],origin('221')[1]-1.75))<1e-8
    assert math.dist((turn_end[0]+1.75,turn_end[1]),
                     (origin('218')[0]+1.75,origin('218')[1]))<1e-8
    assert roads['220'].find('./lanes/laneSection/center/lane/roadMark').get('type')=='solid solid'
    return {'west_end_xy_m':list(west_end),'straight_end_xy_m':list(straight_end),
            'turn_end_xy_m':list(turn_end),'turn_end_heading_rad':sweep,
            'turn_lane_center_xy_m':[turn_end[0]+1.75,turn_end[1]]}

def run():
    compared=[]; joined=0
    geometry=geometry_audit(HERE/'zone-adjoining.xodr')
    with tempfile.TemporaryDirectory() as temp:
        for suffix in CASES:
            pair=[]
            for name in POLICIES:
                bundle=HERE/'drafts'/suffix/name
                c=check(bundle)
                q=[json.loads(x) for x in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
                assert q==request_rows(suffix,name)
                assert (bundle/'zone-adjoining.xodr').read_text()==road()
                raw,video,review=fixture(bundle,Path(temp)/suffix/name)
                a=[json.loads(x) for x in raw.read_text().splitlines()]
                v=[json.loads(x) for x in video.read_text().splitlines()]
                for i,(r,f) in enumerate(zip(a,v)):
                    assert r['frame']==f['video_frame']==i
                    assert r['native_frame']==f['native_frame']==1000+i
                    assert abs(r['time_s']-(i+1)/RATE)<1e-8
                    assert r['requested_ego_xy_m']==q[i]['requested_ego_xy_m']
                m=process(bundle,raw,video,review,synthetic=True)
                stripe=next((i for i,r in enumerate(a) if
                    min(p[1] for p in r['ego']['body_native_xyz_m'])<=0<=max(p[1] for p in r['ego']['body_native_xyz_m'])
                    and max(p[0] for p in r['ego']['body_native_xyz_m'])>=0
                    and min(p[0] for p in r['ego']['body_native_xyz_m'])<=55),None)
                spur=next((i for i,r in enumerate(a) if r['observed_road_id']==218 and r['observed_lane_id']==-1),None)
                signal=next((i for i,r in enumerate(a) if r['observed_left_indicator']),None)
                assert (m['first_observed_stripe_frame'],m['first_adjoining_lane_frame'],m['first_observed_signal_frame'])==(stripe,spur,signal)
                assert m['physical_legal_verdict'] is None and not m['delivery_ready']
                joined+=FRAMES
                pair.append({'candidate':name,'request_sha256':sha(bundle/'requested-tracks.jsonl'),
                             'stripe_frame':stripe,'adjoining_frame':spur,'signal_frame':signal,
                             'fallback_triggers':m['fallback_triggers']})
            assert pair[0]['request_sha256']!=pair[1]['request_sha256']
            assert pair[0]['request_sha256']!=pair[3]['request_sha256']
            assert pair[0]['stripe_frame'] is not None and pair[3]['stripe_frame'] is None
            compared.append({'case':suffix,'candidates':pair})
        for name in POLICIES:
            p=HERE/'drafts'/'probe_1'/name/'requested-tracks.jsonl'
            n=HERE/'drafts'/'probe_2'/name/'requested-tracks.jsonl'
            a=[json.loads(x) for x in p.read_text().splitlines()]
            b=[json.loads(x) for x in n.read_text().splitlines()]
            for x,y in zip(a,b):
                assert x['requested_ego_xy_m']==y['requested_ego_xy_m']
                assert x['requested_speed_mps']==y['requested_speed_mps']
                assert x['requested_oncoming_xy_m']==y['requested_oncoming_xy_m']
                assert x['requested_following_xy_m']==y['requested_following_xy_m']
                assert x['requested_left_indicator']!=y['requested_left_indicator'] or x['frame']<60
        bundle=HERE/'drafts'/'probe_1'/'primary'
        raw,video,review=fixture(bundle,Path(temp)/'triggers')
        base=[json.loads(x) for x in raw.read_text().splitlines()]
        visual=json.loads(review.read_text())
        for row in base[:150]:
            row['observed_left_indicator']=False
            row['ego']['light_state']=0
        raw.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in base))
        visual['raw_sha256']=sha(raw);put(review,visual)
        slow=process(bundle,raw,video,review,synthetic=True)
        assert slow['observed_signal_lead_s']<2 and slow['fallback_triggers']['fallback1']
        visual['stripe_visible_frames']=list(range(300));put(review,visual)
        obscured=process(bundle,raw,video,review,synthetic=True)
        assert obscured['stripe_review_fraction']==.75 and obscured['fallback_triggers']['fallback2']
        stop=next(x for x in compared if x['case']=='probe_2')['candidates'][0]
        assert stop['signal_frame'] is None and stop['fallback_triggers']['fallback3']
        broken=Path(temp)/'broken-junction.xodr'
        original=(HERE/'zone-adjoining.xodr').read_text()
        broken.write_text(original.replace('curvature="0.2857142857142857"',
                                           'curvature="0.25"',1))
        try:
            geometry_audit(broken)
        except AssertionError:
            pass
        else:
            raise AssertionError('Changed turn curvature passed independent geometry audit')
    result={'format':'c109137-zone-independent-audit-v1','request_and_saved_joins':joined,
        'authored_junction_geometry':geometry,
        'changed_turn_curvature_rejected':True,
        'controlled_pairs':4,'comparisons':compared,'measured_trigger_probes':3,
        'synthetic_cpu_only':True,'original_native_observed':False,'delivery_ready':False}
    put(HERE/'independent-audit.json',result)
    return {'joins':joined,'controlled_pairs':4,'trigger_probes':3}

if __name__=='__main__':
    print(json.dumps(run()))
