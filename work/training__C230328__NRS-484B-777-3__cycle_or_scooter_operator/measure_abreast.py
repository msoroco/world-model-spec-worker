"""Report original rider intervals and bearings without imposing an abreast cutoff."""
import hashlib
import json
import math
import subprocess
from pathlib import Path

AID = 'training__C230328__NRS-484B-777-3__cycle_or_scooter_operator'
COUNT = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(root):
    root = Path(root)
    source = {name: root/name for name in ('video_frames.jsonl', 'rider_poses.jsonl', 'road_context.json')}
    if any(not p.is_file() for p in source.values()):
        raise ValueError('Original frame, rider, and road sources required')
    frames, poses = rows(source['video_frames.jsonl']), rows(source['rider_poses.jsonl'])
    ctx = json.loads(source['road_context.json'].read_text())
    if len(frames) != COUNT or len(poses) != COUNT or ctx.get('assignment_id') != AID:
        raise ValueError('Exact assignment and 600 joined frames required')
    kind = ctx.get('review_kind')
    if kind not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Unreviewed source kind')
    for key in ('reviewer', 'public_dedication_source', 'public_vehicle_access_source',
                'roadway_boundary_source', 'shoulder_boundary_source',
                'exclusive_use_source', 'exclusive_use_review_source', 'rider_device_source'):
        if not ctx.get(key):
            raise ValueError('Missing road or rider source: '+key)
    if ctx.get('exclusive_use_reviewed') is not True:
        raise ValueError('Exclusive-use exception requires reviewed source')
    ids = ctx.get('rider_ids')
    if not isinstance(ids, list) or len(ids) not in (2,3) or len(set(ids)) != len(ids) or any(type(x) is not int for x in ids):
        raise ValueError('Two or three distinct source riders required')
    devices = ctx.get('device_subtypes')
    if not isinstance(devices, dict) or set(devices) != {str(i) for i in ids} or any(x not in ('bicycle', 'electric_bicycle', 'electric_scooter') for x in devices.values()):
        raise ValueError('Source rider classifications missing')
    if any(x == 'bicycle' for x in devices.values()):
        for key in ('bicycle_wheel_source', 'bicycle_diameter_source', 'bicycle_moped_exclusion_source'):
            if not ctx.get(key):
                raise ValueError('Qualifying bicycle source missing: '+key)
    cam_hashes = {}
    if kind == 'original_source_review':
        for name in CAMERAS:
            path = root / (name+'.mkv')
            if not path.is_file():
                raise ValueError('Original camera missing: '+name)
            probe = subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                '-show_entries','stream=nb_read_frames,r_frame_rate','-of','json',str(path)], capture_output=True, text=True)
            if probe.returncode:
                raise ValueError('Camera decode failed: '+name)
            stream = json.loads(probe.stdout).get('streams', [])
            if len(stream) != 1 or stream[0].get('nb_read_frames') != str(COUNT) or stream[0].get('r_frame_rate') != '20/1':
                raise ValueError('Camera duration/rate differs: '+name)
            cam_hashes[path.name] = sha(path)
        if ctx.get('camera_sha256') != cam_hashes:
            raise ValueError('Camera review hash binding differs')
    prev_frame, prev_time = -1, -1.0
    samples = []
    for i, (f, p) in enumerate(zip(frames, poses)):
        n, t = f.get('native_frame'), f.get('time_s')
        if f.get('video_frame') != i or type(n) is not int or n <= prev_frame or not finite(t) or t <= prev_time or (i and abs(t-prev_time-.05) > .005):
            raise ValueError('Original frame/time identity differs')
        if p.get('video_frame') != i or p.get('native_frame') != n or p.get('source_kind') != ('synthetic_native_sample' if kind == 'synthetic_diagnostic' else 'original_native_pose'):
            raise ValueError('Rider pose source join differs')
        riders = p.get('riders')
        if not isinstance(riders, list) or {r.get('rider_id') for r in riders if isinstance(r,dict)} != set(ids) or len(riders) != len(ids):
            raise ValueError('Rider identity/count differs')
        by_id = {}
        for r in riders:
            if any(not finite(r.get(k)) for k in ('longitudinal_m','lateral_m','half_length_m','speed_mps')) or r['half_length_m'] <= 0 or r['speed_mps'] < 0:
                raise ValueError('Original rider pose/extent absent')
            if r.get('roadway_occupied') is not True or r.get('shoulder_occupied') is not False or r.get('exclusive_use_occupied') is not False:
                raise ValueError('Roadway/shoulder/exception occupancy unproved')
            by_id[r['rider_id']] = r
        pairwise = []
        for j, aid in enumerate(ids):
            for bid in ids[j+1:]:
                a,b = by_id[aid],by_id[bid]
                alo,ahi = a['longitudinal_m']-a['half_length_m'],a['longitudinal_m']+a['half_length_m']
                blo,bhi = b['longitudinal_m']-b['half_length_m'],b['longitudinal_m']+b['half_length_m']
                dx,dy = b['longitudinal_m']-a['longitudinal_m'],b['lateral_m']-a['lateral_m']
                pairwise.append({'rider_ids':[aid,bid], 'longitudinal_interval_a_m':[alo,ahi],
                    'longitudinal_interval_b_m':[blo,bhi], 'overlap_length_m':max(0,min(ahi,bhi)-max(alo,blo)),
                    'longitudinal_delta_m':dx, 'lateral_delta_m':dy, 'bearing_rad':math.atan2(dy,dx)})
        samples.append({'video_frame':i, 'native_frame':n, 'time_s':t, 'pairwise':pairwise})
        prev_frame,prev_time=n,t
    if frames[-1]['time_s']-frames[0]['time_s'] < 29.9:
        raise ValueError('Thirty-second original capture required')
    return {'format':'source-bound-abreast-geometry-v1','assignment_id':AID,
        'source_sha256':{**{k:sha(v) for k,v in source.items()},**cam_hashes},
        'sample_count':COUNT,'rider_count':len(ids),'per_frame_geometry':samples,
        'abreast_classification':None,'legal_result':None,'physical_acceptance_claimed':False}
