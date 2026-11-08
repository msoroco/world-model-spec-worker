"""Measured heavy-vehicle fallback decisions from source-bound saved rows."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate(case, candidate, observed, expected_sha, camera=None):
    if case not in ('reference', 'contrast') or candidate not in ('fallback1','fallback2','fallback3'):
        raise ValueError('Unknown heavy-vehicle trigger identity')
    observed = Path(observed)
    if sha(observed) != expected_sha:
        raise ValueError('Observed body source hash differs')
    rows = [json.loads(line) for line in observed.read_text().splitlines()]
    if len(rows) != 480:
        raise ValueError('Observed body frame count differs')
    kinds = {r.get('source_kind') for r in rows}
    if len(kinds) != 1 or not kinds <= {'synthetic_cpu', 'original_native'}:
        raise ValueError('Observed body provenance differs')
    first_time = rows[0].get('time_s')
    if not isinstance(first_time, (int,float)) or not math.isfinite(first_time):
        raise ValueError('Observed initial time invalid')
    overlap, inside, offcenter = [], [], []
    first_native = rows[0].get('native_frame')
    if not isinstance(first_native, int):
        raise ValueError('Observed initial Native frame invalid')
    for i, row in enumerate(rows):
        if row.get('frame') != i or row.get('native_frame') != first_native+i or \
                not isinstance(row.get('time_s'),(int,float)) or \
                abs(row['time_s']-first_time-i/20)>1e-4:
            raise ValueError('Observed frame/time join differs')
        if row.get('source_kind') not in kinds or row.get('vehicle_blueprint') != 'vehicle.carlamotors.carlacola':
            raise ValueError('Observed actor identity differs')
        body = row.get('body_native_xy_m')
        speed = row.get('speed_mps')
        if not isinstance(body,list) or len(body)!=4 or not isinstance(speed,(int,float)) or not math.isfinite(speed):
            raise ValueError('Observed body or speed invalid')
        if any(not isinstance(p,list) or len(p)!=2 or
               any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in p)
               for p in body):
            raise ValueError('Observed body vertex invalid')
        ymin, ymax = min(p[1] for p in body), max(p[1] for p in body)
        center = sum(p[1] for p in body)/4
        if speed>.1:
            if ymax>3.5 and ymin<7.5: overlap.append(i)
            if ymin>=3.5 and ymax<=7.5: inside.append(i)
            if abs(center-1.75)>.25: offcenter.append(i)
    if candidate == 'fallback1':
        value = len(overlap)>0 if case=='reference' else not overlap or overlap[0]>65
        metric = {'first_moving_overlap_frame': overlap[0] if overlap else None,
                  'threshold_frame': 65 if case=='contrast' else None,
                  'reference_unsafe_overlap': case=='reference'}
    elif candidate == 'fallback2':
        value = len(offcenter)>0 if case=='reference' else len(inside)<400
        metric = {'moving_full_body_inside_frames': len(inside),
                  'moving_offcenter_frames': len(offcenter),
                  'threshold_frames': 400 if case=='contrast' else 0}
    else:
        if not isinstance(camera,dict) or not isinstance(camera.get('source'),str) or \
                not isinstance(camera.get('sha256'),str):
            raise ValueError('Camera source packet absent')
        if sha(camera['source']) != camera['sha256']:
            raise ValueError('Camera source hash differs')
        if camera.get('source_kind') not in kinds or camera.get('frames')!=480 or \
                not isinstance(camera.get('visible_frames'),int) or not 0<=camera['visible_frames']<=480:
            raise ValueError('Camera visibility packet differs')
        fraction = camera['visible_frames']/480
        value = fraction<.75
        metric = {'visible_fraction':fraction, 'threshold_fraction':.75,
                  'camera_source_sha256':camera['sha256']}
    return {'case':case,'candidate':candidate,'source_kind':kinds.pop(),
            'observed_sha256':expected_sha,'triggered':value,'metric':metric,
            'physical_acceptance_claimed':False}
