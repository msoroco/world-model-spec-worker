"""Measure three distinct straight-route fallback triggers from saved sources."""
import hashlib
import json
import math
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def evaluate(folder):
    folder=Path(folder)
    source_path=folder/'no-entry-trigger-sources.json'
    if not source_path.is_file():raise ValueError('Missing required source: no-entry-trigger-sources.json')
    source=json.loads(source_path.read_text())
    if source.get('format')!='c10052-no-entry-trigger-sources-v1' or source.get('source_kind') not in ('synthetic_cpu_fixture','original_native'):
        raise ValueError('Unknown no-entry trigger provenance')
    expected=source.get('sha256',{})
    if set(expected)!={'native_samples.jsonl','road_geometry.json','camera_visibility.jsonl'}:
        raise ValueError('Incomplete no-entry trigger source hashes')
    for name,digest in expected.items():
        if not (folder/name).is_file() or sha(folder/name)!=digest:
            raise ValueError('No-entry trigger source hash differs: '+name)
    geometry=json.loads((folder/'road_geometry.json').read_text())
    alley=geometry['alley_entrance_native_xy_bounds_m']
    samples=[json.loads(line) for line in (folder/'native_samples.jsonl').read_text().splitlines() if line.strip()]
    visibility=[json.loads(line) for line in (folder/'camera_visibility.jsonl').read_text().splitlines() if line.strip()]
    if len(samples)!=480 or len(visibility)!=480:raise ValueError('No-entry trigger duration differs')
    speeds=[];visible=0;sampled=0;first_frame=None;previous_time=None
    for index,(sample,view) in enumerate(zip(samples,visibility)):
        frame,time=sample.get('native_frame'),sample.get('time_s')
        if first_frame is None:first_frame=frame
        if (type(frame) is not int or type(time) not in (int,float) or
            not math.isfinite(time) or
            type(first_frame) is not int or first_frame<0 or
            frame!=first_frame+index or
            (previous_time is None and abs(time-.05)>.002) or
            (previous_time is not None and abs(time-previous_time-.05)>.002) or
            view.get('native_frame')!=frame or view.get('time_s')!=time or
            type(view.get('body_visible')) is not bool or
            sample.get('native_road_id')!=geometry['road_id'] or
            sample.get('native_lane_id')!=geometry['driving_lane_id']):
            raise ValueError('No-entry trigger original frame/time/road join differs')
        previous_time=time
        if source['source_kind']=='original_native' and (sample.get('synthetic_diagnostic') or view.get('synthetic_diagnostic')):
            raise ValueError('Synthetic trigger samples cannot be original Native')
        x,y=sample['native_center_xy_m'];speed=sample['speed_mps']
        if not all(type(v) in (int,float) and math.isfinite(v) for v in (x,y,speed)) or speed<0:
            raise ValueError('Invalid no-entry trigger pose or speed')
        if -20<=x<=0:speeds.append(speed)
        if -20<=x<=10:
            sampled+=1;visible+=view['body_visible']
    first_x=samples[0]['native_center_xy_m'][0]
    runway=round(alley[0]-first_x,6)
    if runway<=0 or not speeds or sampled<20:raise ValueError('No-entry trigger geometry lacks sampled approach')
    peak=round(max(speeds),6)
    fraction=round(visible/sampled,6)
    return {'format':'c10052-no-entry-trigger-measurement-v1',
        'source_kind':source['source_kind'],'source_sha256':expected,
        'approach_runway_to_alley_m':runway,
        'peak_approach_speed_mps':peak,
        'reference_body_visibility_fraction':fraction,
        'reference_body_visible_frames':visible,'reference_sampled_frames':sampled,
        'fallback1_trigger_measured':runway<45,
        'fallback2_trigger_measured':peak>2.2,
        'fallback3_trigger_measured':fraction<.95,
        'physical_behavior_confirmed':False,'accepted':False}
