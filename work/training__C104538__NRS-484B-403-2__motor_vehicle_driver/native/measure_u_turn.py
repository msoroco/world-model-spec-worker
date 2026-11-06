"""Measure a signed U-turn from joined saved Native body and sign-review sources.

The sign review is a source-bound input. Synthetic reviews prove the measurement
path only; a real review must use original pixels and map/device readback.
"""
import hashlib
import json
import math
from pathlib import Path
from pixel_review import verify as verify_pixel_review


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value, name):
    if not isinstance(value, list) or len(value)!=2:
        raise ValueError('Missing '+name)
    result=tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in result):
        raise ValueError('Nonfinite '+name)
    return result


def measure(samples_path, frame_map_path, sign_review_path, video_path):
    paths=[Path(p) for p in (samples_path,frame_map_path,sign_review_path,video_path)]
    if not all(p.is_file() for p in paths):
        raise ValueError('Missing original Native, frame-map, sign-review or video source')
    samples=[json.loads(line) for line in paths[0].read_text().splitlines() if line.strip()]
    mapping=[json.loads(line) for line in paths[1].read_text().splitlines() if line.strip()]
    review=json.loads(paths[2].read_text())
    if len(samples)!=480 or len(mapping)!=480:
        raise ValueError('Expected 480 joined original frames')
    if (review.get('source_kind')!='original_camera_sign_review'
        or review.get('native_samples_sha256')!=sha(paths[0])
        or review.get('frame_map_sha256')!=sha(paths[1])
        or review.get('video_sha256')!=sha(paths[3])):
        raise ValueError('Sign review source hash or provenance mismatch')
    if review.get('sign_code')!='no_u_turn' or review.get('governs_approach') is not True:
        raise ValueError('Applicable official no-U-turn device unverified')
    pixels=verify_pixel_review(paths[0],paths[1],paths[2],paths[3],paths[2].parent/'pixel_review.jsonl')
    region=review.get('governed_native_xy_bounds_m')
    if not isinstance(region,list) or len(region)!=4 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in region) or region[0]>=region[2] or region[1]>=region[3]:
        raise ValueError('Invalid sign-governed Native region')
    lane=review.get('governed_approach_lane_id')
    opposing=review.get('opposing_lane_id')
    if type(lane)!=int or type(opposing)!=int or opposing==lane:
        raise ValueError('Missing governed approach lane')
    first=point(samples[0].get('native_forward_xy'),'initial Native heading')
    if abs(math.hypot(*first)-1)>.01:
        raise ValueError('Initial heading is not unit length')
    last_frame=-1;last_time=-math.inf;angles=[];inside=[];frames=[]
    prior=None;unwrapped=0.0
    for index,(sample,frame_map) in enumerate(zip(samples,mapping)):
        frame=sample.get('native_frame');time=sample.get('time_s')
        if type(frame)!=int or frame<=last_frame or isinstance(time,bool) or not isinstance(time,(int,float)) or not math.isfinite(time) or time<=last_time:
            raise ValueError('Native frame/time order invalid')
        if (frame_map.get('native_frame')!=frame or frame_map.get('carla_frame')!=frame
            or frame_map.get('video_frame')!=index or abs(frame_map.get('time_s',-1)-time)>1e-6):
            raise ValueError('Original video/Native frame join mismatch')
        last_frame=frame;last_time=time
        center=point(sample.get('native_center_xy_m'),'Native body center')
        body=[point(p,'Native body corner') for p in sample.get('native_body_xy_m',[])]
        if len(body)!=4:
            raise ValueError('Original four-corner body missing')
        if math.dist(center,(sum(p[0] for p in body)/4,sum(p[1] for p in body)/4))>.1:
            raise ValueError('Native center/body source mismatch')
        heading=point(sample.get('native_forward_xy'),'Native heading')
        if abs(math.hypot(*heading)-1)>.01:
            raise ValueError('Native heading is not unit length')
        angle=math.atan2(heading[1],heading[0])
        if prior is not None:
            delta=(angle-prior+math.pi)%(2*math.pi)-math.pi
            if abs(delta)>math.radians(20):
                raise ValueError('Implausible between-frame heading change')
            unwrapped+=delta
        prior=angle;angles.append(unwrapped)
        inside.append(all(region[0]<=p[0]<=region[2] and region[1]<=p[1]<=region[3] for p in body))
        frames.append(frame)
    if samples[0].get('native_lane_id')!=lane:
        raise ValueError('Initial vehicle not in sign-governed approach lane')
    reversal=next((i for i,a in enumerate(angles) if abs(a)>=math.radians(160)),None)
    observed=bool(reversal is not None and
                  all(inside[i] for i in range(reversal+1) if abs(angles[i])>=math.radians(20)) and
                  samples[-1].get('native_lane_id')==opposing)
    return {'format':'signed-u-turn-original-frame-measurement-v1',
            'samples':480,'applicable_no_u_turn_device_reviewed':True,
            'u_turn_within_governed_region_observed':observed,
            'reversal_native_frame':frames[reversal] if reversal is not None else None,
            'maximum_heading_change_deg':max(abs(math.degrees(a)) for a in angles),
            'complete_body_inside_governed_region_at_reversal':inside[reversal] if reversal is not None else False,
            'opposing_lane_exit_observed':samples[-1].get('native_lane_id')==opposing,
            'pixel_review':{'visible_frames':pixels['visible_frames'],
                            'approach_frames':pixels['approach_frames'],
                            'visible_fraction':pixels['visible_fraction']},
            'source_hashes':{p.name:sha(p) for p in paths+[paths[2].parent/'pixel_review.jsonl']},
            'physical_success_claimed':False,
            'legal_verdict_claimed':False}
