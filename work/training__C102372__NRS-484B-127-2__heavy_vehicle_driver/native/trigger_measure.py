"""Source-hashed truck gap, gap-control and camera-projection fallback metrics."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from engineering import TARGET_GAP_M,TRIGGERS
from measure_gap import measure,road_distance

SOURCES=('native_samples.jsonl','following_context.json','road.xodr',
         'video_frames.jsonl','camera_context.json','overview.mkv')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def decoded_video(path):
    result=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=width,height,nb_read_frames','-of','json',str(path)],
        capture_output=True,text=True,timeout=120)
    if result.returncode:raise ValueError('Original overview decode failed')
    stream=json.loads(result.stdout)['streams'][0]
    return int(stream['width']),int(stream['height']),int(stream['nb_read_frames'])


def margin(point,pose,camera):
    x,y,z=pose['xyz_m'];yaw=math.radians(pose['yaw_deg']);pitch=math.radians(pose['pitch_deg'])
    dx,dy,dz=point[0]-x,point[1]-y,point[2]-z
    forward=dx*math.cos(pitch)*math.cos(yaw)+dy*math.cos(pitch)*math.sin(yaw)+dz*math.sin(pitch)
    width,height=camera['width'],camera['height']
    if forward<=.01:return -float(max(width,height))
    right=-dx*math.sin(yaw)+dy*math.cos(yaw)
    up=-dx*math.sin(pitch)*math.cos(yaw)-dy*math.sin(pitch)*math.sin(yaw)+dz*math.cos(pitch)
    focal=width/(2*math.tan(math.radians(camera['fov_deg'])/2))
    u=width/2+focal*right/forward;v=height/2-focal*up/forward
    return min(u,width-u,v,height-v)


def extract(root,case):
    root=Path(root).resolve()
    if case not in TARGET_GAP_M and case!='two_lane_exception':
        raise ValueError('Unknown exact truck case')
    manifest_path=root/'trigger-source-manifest.json'
    if not manifest_path.is_file():raise ValueError('Missing trigger source manifest')
    declared=json.loads(manifest_path.read_text())
    if declared.get('format')!='c102372-truck-trigger-sources-v1' or set(
            declared.get('sha256',{}))!=set(SOURCES):
        raise ValueError('Incomplete original trigger source hashes')
    for name in SOURCES:
        path=root/name
        if not path.is_file() or sha(path)!=declared['sha256'][name]:
            raise ValueError('Trigger source missing or changed: '+name)
    if case=='two_lane_exception':
        from two_lane_exception import measure as measure_two_lane
        measurement=measure_two_lane(root)
        target_gap=140.
    else:
        measurement=measure(root)
        target_gap=TARGET_GAP_M[case]
    native=rows(root/'native_samples.jsonl');mapping=rows(root/'video_frames.jsonl')
    if len(native)!=480 or len(mapping)!=480:raise ValueError('Full 480-frame trigger join required')
    camera=json.loads((root/'camera_context.json').read_text())
    if camera.get('name')!='overview' or camera.get('source_kind') not in (
            'synthetic_cpu_camera_emulation','original_native_camera_readback'):
        raise ValueError('Overview camera readback absent')
    for key in ('width','height','fov_deg'):
        if type(camera.get(key)) not in (int,float):raise ValueError('Overview calibration absent')
    if decoded_video(root/'overview.mkv')!=(camera['width'],camera['height'],480):
        raise ValueError('Original overview dimensions or frame count differ')
    road=ET.parse(root/'road.xodr').getroot().find('road')
    profile=road.findall('elevationProfile/elevation')
    deficits=[];margins=[];prior=None
    for index,(row,join) in enumerate(zip(native,mapping)):
        frame=row.get('carla_frame')
        if (row.get('native_frame'),join.get('native_frame'),join.get('video_frame'),
                join.get('carla_frame'))!=(index,index,index,frame) or type(frame) is not int or \
                (prior is not None and frame<=prior):
            raise ValueError('Original truck/camera frame identity differs')
        prior=frame
        ego=row['ego'];lead=row['lead']
        front=max(p[0] for p in ego['body_xy_m'])
        rear=min(p[0] for p in lead['body_xy_m'])
        deficits.append(max(0.,target_gap-road_distance(front,rear,profile)))
        pose=row.get('overview_camera_pose')
        if not isinstance(pose,dict) or not all(key in pose for key in ('xyz_m','yaw_deg','pitch_deg')):
            raise ValueError('Original per-frame camera pose absent')
        for actor in (ego,lead):
            vertices=actor.get('body_vertices_m')
            if not isinstance(vertices,list) or len(vertices)<8:
                raise ValueError('Original full truck 3D body absent')
            expected={(round(p[0],4),round(p[1],4)) for p in actor['body_xy_m']}
            observed={(round(p[0],4),round(p[1],4)) for p in vertices}
            if expected!=observed:raise ValueError('Original 2D/3D truck body differs')
            margins.extend(margin(point,pose,camera) for point in vertices)
    metrics={'format':'c102372-source-bound-fallback-metrics-v1',
        'source_kind':json.loads((root/'following_context.json').read_text())['source_kind'],
        'case':case,'min_surface_gap_m':measurement['min_surface_gap_m'],
        'max_gap_shortfall_m':round(max(deficits),5),
        'min_projected_truck_frame_margin_px':round(min(margins),5),
        'sources':declared['sha256'],
        'limitations':['projection is not pixel visibility',
                       'synthetic conditions and body geometry do not establish a legal verdict']}
    if not all(math.isfinite(metrics[trigger['metric']]) for trigger in TRIGGERS.values()):
        raise ValueError('Nonfinite truck fallback metric')
    return metrics


def evaluate(candidate,metrics,path,expected_sha256,diagnostic=False):
    if candidate not in TRIGGERS:raise ValueError('Only fallbacks have triggers')
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:
        raise ValueError('Fallback metric source hash differs')
    record=json.loads(raw)
    permitted=('native_observation','synthetic_cpu_fixture') if diagnostic else ('native_observation',)
    if record!=metrics or record.get('source_kind') not in permitted:
        raise ValueError('Fallback metrics are not bound to original Native source')
    trigger=TRIGGERS[candidate];value=record.get(trigger['metric'])
    if type(value) not in (int,float):raise ValueError('Measured trigger value absent')
    return value<trigger['threshold'] if trigger['op']=='<' else value>trigger['threshold']
