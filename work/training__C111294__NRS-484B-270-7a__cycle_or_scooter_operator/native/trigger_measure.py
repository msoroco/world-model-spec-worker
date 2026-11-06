"""Source-hashed measurements for three C111294 fallback decisions.

Pixel margin is a projection of original body vertices through the surveyed
camera, with video decode proving frame count. It does not claim visibility.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

COUNT=480
SOURCES=('road.xodr','interaction.json','native_samples.jsonl',
         'video_frames.jsonl','camera_context.json','overview.mkv')


def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path:Path)->list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def bounds(body:list[list[float]])->tuple[float,float,float,float]:
    return (min(p[0] for p in body),min(p[1] for p in body),
            max(p[0] for p in body),max(p[1] for p in body))


def clearance(a:tuple,b:tuple)->float:
    dx=max(0.,a[0]-b[2],b[0]-a[2]);dy=max(0.,a[1]-b[3],b[1]-a[3])
    return math.hypot(dx,dy)


def projected_margin(point:list[float],camera:dict)->float:
    pose=camera['pose'];x,y,z=pose['xyz_m'];yaw=math.radians(pose['yaw_deg']);pitch=math.radians(pose['pitch_deg'])
    dx,dy,dz=point[0]-x,point[1]-y,point[2]-z
    forward=dx*math.cos(pitch)*math.cos(yaw)+dy*math.cos(pitch)*math.sin(yaw)+dz*math.sin(pitch)
    width,height=camera['width'],camera['height']
    if forward<=.01:return -float(max(width,height))
    right=-dx*math.sin(yaw)+dy*math.cos(yaw)
    up=-dx*math.sin(pitch)*math.cos(yaw)-dy*math.sin(pitch)*math.sin(yaw)+dz*math.cos(pitch)
    focal=width/(2*math.tan(math.radians(camera['fov_deg'])/2))
    u=width/2+focal*right/forward;v=height/2-focal*up/forward
    return min(u,width-u,v,height-v)


def video_shape(path:Path)->tuple[int,int,int]:
    result=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=width,height,nb_read_frames','-of','json',str(path)],
        text=True,capture_output=True,timeout=120)
    if result.returncode:raise ValueError('Original overview decode failed')
    stream=json.loads(result.stdout)['streams'][0]
    return int(stream['width']),int(stream['height']),int(stream['nb_read_frames'])


def measure(attempt:Path)->dict:
    attempt=attempt.resolve()
    manifest_path=attempt/'capture/manifest.json'
    if not manifest_path.is_file():raise ValueError('Missing original capture manifest')
    manifest=json.loads(manifest_path.read_text())
    declared=manifest.get('sources',{})
    for name in SOURCES:
        path=attempt/name
        if not path.is_file():raise ValueError('Missing trigger source: '+name)
        if declared.get(name)!=sha(path):raise ValueError('Trigger source hash absent or changed: '+name)
    interaction=json.loads((attempt/'interaction.json').read_text())
    source_kind=interaction.get('source_kind')
    if source_kind not in ('synthetic_original_shape_emulation','original_native_and_video'):
        raise ValueError('Original-shaped interaction source required')
    from measure import measure as measure_interaction
    measure_interaction(attempt/'interaction.json',declared['interaction.json'],attempt/'road.xodr')
    native=rows(attempt/'native_samples.jsonl');mapping=rows(attempt/'video_frames.jsonl')
    if len(native)!=COUNT or len(mapping)!=COUNT or len(interaction.get('frames',[]))!=COUNT:
        raise ValueError('Full 480-frame trigger join required')
    camera=json.loads((attempt/'camera_context.json').read_text())
    if camera.get('name')!='overview' or any(type(camera.get(key)) not in (int,float) for key in ('width','height','fov_deg')):
        raise ValueError('Overview calibration absent')
    if video_shape(attempt/'overview.mkv')!=(camera['width'],camera['height'],COUNT):
        raise ValueError('Original overview dimensions or frames differ')
    errors=[];seconds=[];margins=[];prior=None
    for index,(sample,mapped,source) in enumerate(zip(native,mapping,interaction['frames'])):
        frame=mapped.get('native_frame')
        if (mapped.get('video_frame'),mapped.get('carla_frame'),sample.get('native_frame'),source.get('native_frame'))!=(index,frame,frame,frame):
            raise ValueError('Original trigger frame identity differs')
        if type(frame) is not int or (prior is not None and frame<=prior):
            raise ValueError('Original trigger frame order differs')
        prior=frame
        if sample.get('bicycle')!=source.get('bicycle') or sample.get('motor_vehicle')!=source.get('motor_vehicle'):
            raise ValueError('Original trigger actor source differs')
        bicycle=sample['bicycle'];motor=sample['motor_vehicle']
        if bicycle.get('blueprint_id')!='vehicle.bh.crossbike' or not motor.get('blueprint_id','').startswith('vehicle.'):
            raise ValueError('Original trigger actor class differs')
        bike_body=bicycle['body_xy_m'];motor_body=motor['body_xy_m']
        if any(len(body)!=4 for body in (bike_body,motor_body)):
            raise ValueError('Full actor bodies required')
        errors.append(abs(bicycle['center_xy_m'][0]-1.75))
        gap=clearance(bounds(bike_body),bounds(motor_body))
        seconds.append(gap/max(.1,bicycle['speed_mps']+motor['speed_mps']))
        for key,body in (('bicycle_body_vertices_m',bike_body),('motor_vehicle_body_vertices_m',motor_body)):
            vertices=sample.get(key)
            if not isinstance(vertices,list) or len(vertices)<8 or any(len(p)!=3 for p in vertices):
                raise ValueError('Original 3D actor vertices absent: '+key)
            observed={(round(p[0],4),round(p[1],4)) for p in vertices}
            expected={(round(p[0],4),round(p[1],4)) for p in body}
            if observed!=expected:raise ValueError('Original 2D/3D actor body differs: '+key)
            margins.extend(projected_margin(p,camera) for p in vertices)
    if not margins or not all(math.isfinite(value) for value in errors+seconds+margins):
        raise ValueError('Nonfinite fallback measurement')
    return {'format':'c111294-source-bound-fallback-metrics-v1','source_kind':source_kind,
        'max_bicycle_route_cross_track_error_m':round(max(errors),5),
        'min_motorist_conflict_clearance_s':round(min(seconds),5),
        'min_projected_body_frame_margin_px':round(min(margins),5),
        'sources':{name:declared[name] for name in SOURCES},
        'method':'original body/pose/control, camera readback and decoded video frame join',
        'limitations':['projection is not pixel visibility','braking and clearance do not establish rider intent or legal interference']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    value=measure(args.attempt)
    with args.output.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(value,sort_keys=True))
