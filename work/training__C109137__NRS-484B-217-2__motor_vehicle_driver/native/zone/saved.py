"""Source-bound C109137 saved diagnostics; physical and legal findings remain unset."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
from check import check
from build import FRAMES, RATE

CAMERAS = ('overview', 'forward', 'stripe_side')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines()]

def finite(x):
    return type(x) in (int, float) and math.isfinite(x)

def media_hash(path):
    if not path.is_file():
        raise ValueError('Original FFV1 absent')
    p = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_name,nb_read_frames', '-of', 'json', str(path)],
        capture_output=True, text=True, timeout=120)
    if p.returncode:
        raise ValueError('Original FFV1 unreadable')
    streams = json.loads(p.stdout).get('streams', [])
    if len(streams) != 1 or streams[0].get('codec_name') != 'ffv1' or \
            streams[0].get('nb_read_frames') != str(FRAMES):
        raise ValueError('Original FFV1 frame contract')
    return sha(path)

def actor(row, blueprint):
    if row.get('blueprint') != blueprint or type(row.get('actor_id')) is not int:
        raise ValueError('Actor identity or blueprint')
    center, velocity, body = (row.get(k) for k in ('center_native_xyz_m',
        'velocity_native_xyz_mps', 'body_native_xyz_m'))
    if (not isinstance(center, list) or len(center) != 3 or not all(map(finite, center)) or
        not isinstance(velocity, list) or len(velocity) != 3 or not all(map(finite, velocity)) or
        not isinstance(body, list) or len(body) != 8 or
        not all(isinstance(p, list) and len(p) == 3 and all(map(finite, p)) for p in body) or
        not finite(row.get('speed_mps')) or
        abs(row['speed_mps'] - math.sqrt(sum(x*x for x in velocity))) > .02):
        raise ValueError('Actor body or velocity')
    return center, velocity, body

def process(bundle, raw, video, review, *, synthetic=False):
    bundle, raw, video, review = map(Path, (bundle, raw, video, review))
    checked = check(bundle)
    cfg = json.loads((bundle/'config.json').read_text())
    req, actors, frames = rows(bundle/'requested-tracks.jsonl'), rows(raw), rows(video)
    visual = json.loads(review.read_text())
    if len(req) != FRAMES or len(actors) != FRAMES or len(frames) != FRAMES:
        raise ValueError('400 source frames required')
    kind = 'synthetic_fixture' if synthetic else 'original_native_review'
    if visual.get('source_kind') != kind or visual.get('case_id') != cfg['case_id'] or \
            visual.get('candidate_id') != cfg['candidate_id']:
        raise ValueError('Visual review source identity')
    if visual.get('raw_sha256') != sha(raw) or visual.get('video_frames_sha256') != sha(video):
        raise ValueError('Visual review raw/video hashes')
    if not synthetic:
        if raw.parent != video.parent:
            raise ValueError('Original actor/video source directory')
        media = {name+'.mkv': media_hash(raw.parent/(name+'.mkv')) for name in CAMERAS}
        mapping_path, report_path = raw.parent/'native-map-readback.json', raw.parent/'native-capture-report.json'
        mapping, report = json.loads(mapping_path.read_text()), json.loads(report_path.read_text())
        required_lanes = {'ego_approach': (217,-1), 'stripe_region': (217,-1),
                          'oncoming': (219,1), 'adjoining': (218,-1),
                          'straight_connector': (220,-1), 'turn_connector': (221,-1)}
        if (mapping.get('source_kind') != 'original_native' or
            mapping.get('road_sha256') != sha(bundle/'zone-adjoining.xodr') or
            mapping.get('adjoining_connection_readback') is not True or
            any(mapping.get('lane_readback',{}).get(k) !=
                {'road_id': rid, 'lane_id': lid, 'lane_type': 'driving'}
                for k,(rid,lid) in required_lanes.items()) or
            mapping.get('zone_legally_designated') is not False or
            mapping.get('legal_verdict') is not None):
            raise ValueError('Original generated map readback')
        if (report.get('case_id') != cfg['case_id'] or
            report.get('candidate_id') != cfg['candidate_id'] or
            report.get('config_sha256') != sha(bundle/'config.json') or
            report.get('requested_frames') != FRAMES or report.get('observed_frames') != FRAMES or
            report.get('error') is not None or report.get('accepted') is not False or
            report.get('delivery_ready') is not False):
            raise ValueError('Original capture receipt')
        if (visual.get('media_sha256') != media or
            visual.get('map_sha256') != sha(mapping_path) or
            visual.get('capture_report_sha256') != sha(report_path)):
            raise ValueError('Original visual review provenance')
    for field in ('stripe_visible_frames', 'adjoining_visible_frames', 'signal_visible_frames',
                  'oncoming_visible_frames', 'following_visible_frames'):
        ids = visual.get(field)
        if not isinstance(ids, list) or len(set(ids)) != len(ids) or \
                any(type(i) is not int or i < 0 or i >= FRAMES for i in ids):
            raise ValueError('Visual reviewed frame index: '+field)
    first_native = actors[0].get('native_frame')
    if type(first_native) is not int:
        raise ValueError('Native frame origin')
    identities = {key: set() for key in ('ego','oncoming','following')}
    previous = {}
    stripe, adjoining, signal = [], [], []
    oncoming_speeds, following_speeds = [], []
    for i,(r,v,q) in enumerate(zip(actors,frames,req)):
        if (r.get('frame') != i or v.get('video_frame') != i or
            r.get('native_frame') != first_native+i or v.get('native_frame') != first_native+i or
            not finite(r.get('time_s')) or not finite(v.get('time_s')) or
            abs(r['time_s']-(i+1)/RATE) > .005 or abs(v['time_s']-r['time_s']) > 1e-6 or
            r.get('source_kind') != ('synthetic_fixture' if synthetic else 'original_native')):
            raise ValueError('Native actor/video frame join')
        if (r.get('requested_ego_xy_m') != q['requested_ego_xy_m'] or
            r.get('requested_speed_mps') != q['requested_speed_mps'] or
            r.get('requested_left_indicator') != q['requested_left_indicator']):
            raise ValueError('Observed/request row identity')
        if (r.get('zone_legally_designated') is not False or
            r.get('traffic_impediment_reviewed') is not False or r.get('legal_verdict') is not None):
            raise ValueError('Unverified legal state changed')
        for key in identities:
            center, velocity, body = actor(r.get(key, {}), cfg['ego_blueprint'])
            identities[key].add(r[key]['actor_id'])
            if key in previous and math.dist(center, previous[key]) > r[key]['speed_mps']/RATE + .5:
                raise ValueError('Actor speed/displacement continuity')
            previous[key] = center
        ego_body = r['ego']['body_native_xyz_m']
        stripe.append(min(p[1] for p in ego_body) <= 0 <= max(p[1] for p in ego_body)
                      and max(p[0] for p in ego_body) >= 0
                      and min(p[0] for p in ego_body) <= 55)
        adjoining.append(r.get('observed_road_id') == 218 and r.get('observed_lane_id') == -1)
        if type(r.get('observed_left_indicator')) is not bool or \
                bool(r['ego'].get('light_state',0) & 32) != r['observed_left_indicator']:
            raise ValueError('Observed indicator/light-state join')
        signal.append(r['observed_left_indicator'])
        oncoming_speeds.append(r['oncoming']['speed_mps'])
        following_speeds.append(r['following']['speed_mps'])
    if any(len(ids) != 1 for ids in identities.values()) or \
            len(set(next(iter(ids)) for ids in identities.values())) != 3:
        raise ValueError('Native actor identity continuity')
    if not synthetic and any(mapping.get(key + '_actor_id') not in identities[key]
                             for key in identities):
        raise ValueError('Original actor/map identity mismatch')
    first_stripe = next((i for i,v in enumerate(stripe) if v), None)
    first_adjoining = next((i for i,v in enumerate(adjoining) if v), None)
    first_signal = next((i for i,v in enumerate(signal) if v), None)
    signal_lead = None if first_signal is None or first_stripe is None else (first_stripe-first_signal)/RATE
    reviewed_coverage = len(visual['stripe_visible_frames'])/FRAMES
    min_traffic_speed = min(oncoming_speeds+following_speeds)
    metrics = {
        'format':'c109137-zone-saved-measurement-v1', 'case_id':checked['case_id'],
        'candidate_id':checked['candidate_id'], 'source_kind':'synthetic_cpu' if synthetic else 'original_native',
        'frames':FRAMES, 'observed_stripe_body_frames':sum(stripe),
        'first_observed_stripe_frame':first_stripe, 'first_adjoining_lane_frame':first_adjoining,
        'first_observed_signal_frame':first_signal, 'observed_signal_lead_s':signal_lead,
        'stripe_review_fraction':reviewed_coverage,
        'minimum_other_traffic_speed_mps':min_traffic_speed,
        'fallback_triggers': {
            'fallback1':first_stripe is not None and signal_lead is not None and signal_lead < 2,
            'fallback2':reviewed_coverage < .90,
            'fallback3':first_adjoining is None or signal_lead is None or min_traffic_speed < 1},
        'adjoining_highway_legally_established':False,
        'no_passing_zone_legally_established':False,
        'no_impediment_established':False,
        'physical_legal_verdict':None, 'delivery_ready':False}
    return metrics
