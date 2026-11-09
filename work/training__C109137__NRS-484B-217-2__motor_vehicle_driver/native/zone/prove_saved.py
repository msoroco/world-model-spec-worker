"""Eight raw-shaped CPU fixtures and material positive/negative saved checks."""
import copy
import json
import math
import tempfile
from pathlib import Path
from build import CASES, POLICIES, FRAMES, RATE
from saved import process, sha

HERE = Path(__file__).resolve().parent

def put(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False)+'\n')

def actor(identity, center, velocity, light=0):
    x,y = center
    vx,vy = velocity
    speed = math.hypot(vx,vy)
    return {'actor_id':identity,'blueprint':'vehicle.tesla.model3',
        'center_native_xyz_m':[x,y,0.5], 'yaw_deg':0,
        'velocity_native_xyz_mps':[vx,vy,0], 'speed_mps':speed,
        'body_native_xyz_m':[[x+dx,y+dy,0.5+dz]
            for dx in (-1,1) for dy in (-.8,.8) for dz in (-.5,.5)],
        'light_state':light}

def fixture(bundle, folder):
    bundle, folder = Path(bundle),Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((bundle/'config.json').read_text())
    req=[json.loads(x) for x in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    raws=[]; videos=[]; prev=None
    for i,q in enumerate(req):
        center=q['requested_ego_xy_m']
        velocity=[0,0] if prev is None else [(center[j]-prev[j])*RATE for j in (0,1)]
        prev=center
        oncoming=q['requested_oncoming_xy_m']; following=q['requested_following_xy_m']
        indicator=q['requested_left_indicator']
        row={'frame':i,'native_frame':1000+i,'time_s':(i+1)/RATE,
            'source_kind':'synthetic_fixture',
            'requested_ego_xy_m':center,'requested_speed_mps':q['requested_speed_mps'],
            'requested_left_indicator':indicator,'observed_left_indicator':indicator,
            'ego':actor(1,center,velocity,32 if indicator else 0),
            'oncoming':actor(2,oncoming,[-4,0]),
            'following':actor(3,following,[2,0]),
            'observed_road_id':218 if center[1]>=4 else 217,
            'observed_lane_id':-1,
            'zone_legally_designated':False,
            'traffic_impediment_reviewed':False,'legal_verdict':None}
        raws.append(row)
        videos.append({'video_frame':i,'native_frame':1000+i,'time_s':(i+1)/RATE})
    raw,video,review=folder/'native-raw-actors.jsonl',folder/'video_frames.jsonl',folder/'review.json'
    raw.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in raws))
    video.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in videos))
    put(review,{'source_kind':'synthetic_fixture','case_id':cfg['case_id'],
        'candidate_id':cfg['candidate_id'],'raw_sha256':sha(raw),
        'video_frames_sha256':sha(video),
        'stripe_visible_frames':list(range(FRAMES)),
        'adjoining_visible_frames':list(range(FRAMES)),
        'signal_visible_frames':list(range(FRAMES)),
        'oncoming_visible_frames':list(range(FRAMES)),
        'following_visible_frames':list(range(FRAMES))})
    return raw,video,review

def prove():
    positives=[]; negatives=[]
    with tempfile.TemporaryDirectory() as root:
        root=Path(root)
        for suffix in CASES:
            for name in POLICIES:
                bundle=HERE/'drafts'/suffix/name
                raw,video,review=fixture(bundle,root/suffix/name)
                m=process(bundle,raw,video,review,synthetic=True)
                assert m['frames']==FRAMES and m['delivery_ready'] is False
                assert m['physical_legal_verdict'] is None
                positives.append({'case':suffix,'candidate':name,'measurement':m})
                base=[json.loads(x) for x in raw.read_text().splitlines()]
                visual=json.loads(review.read_text())
                mutations={
                    'request_identity':lambda a:a[10].__setitem__('requested_speed_mps',99),
                    'native_join':lambda a:a[10].__setitem__('native_frame',9999),
                    'light_state':lambda a:a[100]['ego'].__setitem__('light_state',0 if a[100]['observed_left_indicator'] else 32),
                    'actor_identity':lambda a:a[10]['following'].__setitem__('actor_id',2),
                    'actor_speed':lambda a:a[10]['oncoming'].__setitem__('speed_mps',99),
                    'body_geometry':lambda a:a[10]['ego']['body_native_xyz_m'].pop(),
                    'legal_verdict':lambda a:a[10].__setitem__('legal_verdict','permitted'),
                    'road_status':lambda a:a[10].__setitem__('zone_legally_designated',True),
                    'time_join':lambda a:a[10].__setitem__('time_s',9),
                }
                for label,mutation in mutations.items():
                    changed=copy.deepcopy(base);mutation(changed)
                    raw.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in changed))
                    current=copy.deepcopy(visual);current['raw_sha256']=sha(raw);put(review,current)
                    try:process(bundle,raw,video,review,synthetic=True)
                    except (ValueError,KeyError):negatives.append({'case':suffix,'candidate':name,'mutation':label})
                    else:raise AssertionError('Saved mutation accepted: '+label)
                raw.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in base))
                put(review,visual)
                try:process(bundle,raw,video,review,synthetic=False)
                except (ValueError,FileNotFoundError):negatives.append({'case':suffix,'candidate':name,'mutation':'missing_original_media'})
                else:raise AssertionError('Synthetic raw accepted as original')
        assert len(positives)==8 and len(negatives)==80
        put(HERE/'saved-proof.json',{'format':'c109137-zone-saved-proof-v1',
            'positive_count':len(positives),'negative_count':len(negatives),
            'positives':positives,'negatives':negatives,
            'scope':'synthetic_cpu; no physical, designation, impediment, or legal proof'})
    return {'positive_count':len(positives),'negative_count':len(negatives)}

if __name__=='__main__':
    print(json.dumps(prove()))
