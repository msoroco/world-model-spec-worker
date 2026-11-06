"""Evaluate three source-bound exception-A turn fallback thresholds."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate(folder):
    folder=Path(folder)
    manifest=json.loads((folder/'alley-trigger-sources.json').read_text())
    if manifest.get('format')!='c10052-alley-trigger-sources-v1':
        raise ValueError('Unknown alley trigger source manifest')
    if manifest.get('source_kind') not in ('synthetic_cpu_fixture','original_native'):
        raise ValueError('Unknown alley trigger provenance')
    expected=manifest.get('sha256',{})
    if set(expected)!={'turn_samples.jsonl','turn_geometry.json','turn_visibility.jsonl'}:
        raise ValueError('Incomplete alley trigger sources')
    for name,digest in expected.items():
        if sha(folder/name)!=digest:raise ValueError('Alley trigger source hash differs: '+name)
    geometry=json.loads((folder/'turn_geometry.json').read_text())
    radius=geometry.get('turn_radius_m');station=geometry.get('turn_start_x_m')
    if not all(type(v) in (int,float) and math.isfinite(v) for v in (radius,station)) or radius<=0:
        raise ValueError('Invalid authored turn geometry')
    poses=[json.loads(x) for x in (folder/'turn_samples.jsonl').read_text().splitlines() if x.strip()]
    views=[json.loads(x) for x in (folder/'turn_visibility.jsonl').read_text().splitlines() if x.strip()]
    if len(poses)!=480 or len(views)!=480:raise ValueError('Alley trigger duration differs')
    turn=[]
    for i,(pose,view) in enumerate(zip(poses,views)):
        if pose.get('native_frame')!=100+i or view.get('native_frame')!=100+i:
            raise ValueError('Alley trigger frame join differs')
        if abs(pose.get('time_s',-1)-(i+1)/20)>1e-6 or abs(view.get('time_s',-1)-(i+1)/20)>1e-6:
            raise ValueError('Alley trigger time join differs')
        if manifest['source_kind']=='original_native' and (pose.get('synthetic_diagnostic') or view.get('synthetic_diagnostic')):
            raise ValueError('Synthetic alley trigger data cannot be original Native')
        if type(view.get('visible')) is not bool:
            raise ValueError('Invalid alley visibility observation')
        if pose.get('phase')=='turn':
            speed=pose.get('speed_mps')
            if type(speed) not in (int,float) or not math.isfinite(speed) or speed<0:
                raise ValueError('Invalid alley turn speed')
            turn.append((speed,view['visible']))
    if len(turn)<40:raise ValueError('Too few turn observations')
    start=poses[0].get('native_center_xy_m')
    if not isinstance(start,list) or len(start)!=2 or not all(
            type(v) in (int,float) and math.isfinite(v) for v in start):
        raise ValueError('Invalid approach start')
    runway=round(station-start[0],6)
    peak=round(max(speed*speed/radius for speed,_ in turn),6)
    visible=sum(flag for _,flag in turn)
    fraction=round(visible/len(turn),6)
    return {'format':'c10052-alley-trigger-measurement-v1',
        'source_kind':manifest['source_kind'],'source_sha256':expected,
        'approach_runway_m':runway,'peak_lateral_accel_proxy_mps2':peak,
        'visible_turn_frames':visible,'turn_frames':len(turn),
        'turn_visibility_fraction':fraction,
        'fallback1_trigger_measured':runway<35,
        'fallback2_trigger_measured':peak>1.5,
        'fallback3_trigger_measured':fraction<.95,
        'physical_behavior_confirmed':False,'accepted':False}
