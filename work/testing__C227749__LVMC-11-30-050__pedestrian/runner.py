"""Exact C227749 Native crossing runner; --check is CPU only."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from xml.etree import ElementTree

from crossing_geometry import validate_scene
from native_capture import FourVideoRecorder, sample_original_walker
from native_controller import request_next_control, spawn_walker
from native_crosswalk_readback import audit_crosswalk_map
from reviewed_site import audit_reviewed_site

FRAMES=400
CAMERAS=('overview','approach','reference_corner','driver_reference')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def check_scene(scene_path,map_path):
    scene=json.loads(Path(scene_path).read_text());validate_scene(scene)
    if sha(map_path)!=scene.get('map_source_sha256'):
        raise ValueError('source-hashed exact OpenDRIVE differs')
    xml=ElementTree.parse(map_path).getroot()
    if xml.tag!='OpenDRIVE' or not xml.findall('./road/planView/geometry/line'):
        raise ValueError('candidate OpenDRIVE road line missing')
    return scene

def _trace(actor,sample):
    pose=actor.get_transform();velocity=actor.get_velocity();control=actor.get_control()
    values=[float(v) for v in (pose.location.x,pose.location.y,pose.location.z,
      pose.rotation.yaw,velocity.x,velocity.y,velocity.z,
      control.direction.x,control.direction.y,control.direction.z,control.speed)]
    if not all(map(math.isfinite,values)):
        raise ValueError('nonfinite original walker telemetry')
    x,y,z,yaw,vx,vy,vz,dx,dy,dz,speed=values
    return {'frame':sample['frame'],'time_s':sample['time_s'],'actor_id':sample['actor_id'],
       'position_m':[x,y,z],'position':{'x':x,'y':y,'z':z},'heading_deg':yaw,
       'velocity_mps':[vx,vy,vz],'speed_mps':math.sqrt(vx*vx+vy*vy+vz*vz),
       'speed_mph':math.sqrt(vx*vx+vy*vy+vz*vz)/.44704,'control':{},
       'walker_control':{'direction_xyz':[dx,dy,dz],'requested_speed_mps':speed,
                         'jump':bool(control.jump)}}

def run_native(scene,scene_path,map_path,output,host,port):
    repo=Path(__file__).resolve().parents[2]
    safe=(repo/'.runtime-work').resolve()
    output=Path(output).resolve()
    if not output.is_dir() or not output.is_relative_to(safe):
        raise ValueError('fresh attempt must be under .runtime-work')
    if Path(scene_path).resolve()!=output/'scene.json' or Path(map_path).resolve()!=output/'candidate-crossing.xodr':
        raise ValueError('exact materialized scene/map required')
    if not (output/'construction.json').is_file() or not (output/'config.json').is_file():
        raise ValueError('exact materialized construction/config required')
    if any((output/name).exists() for name in ('trace.jsonl','video_frames.jsonl','walker-body-history.jsonl','capture-seal.json')):
        raise ValueError('original acquisition already exists')
    reviewed = audit_reviewed_site(scene, output)
    write(output/'reviewed-site-audit.json', reviewed)
    os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']=str(safe/'c227749-native-runtime')
    import carla
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import snapshot as snapshot_world,restore
    from walker_pipeline_capture import WalkerPipelineCapture
    client=carla.Client(host,port);client.set_timeout(30)
    previous=snapshot_world(client)
    world=actor=videos=capture=frame_map=None
    frames=[];errors=[];restoration={'restored':False}
    try:
        world=client.generate_opendrive_world(Path(map_path).read_text())
        write(output/'native-crosswalk-readback.json',
              audit_crosswalk_map(scene,world.get_map()))
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.no_rendering_mode=False
        world.apply_settings(settings)
        actor=spawn_walker(world,carla,scene)
        write(output/'acquisition-provenance.json',{'provenance_kind':'native',
              'diagnostic_fixture':False,'case_id':scene['case_id'],
              'map_sha256':sha(map_path),'method':'original walker body, telemetry and four RGB cameras'})
        videos=FourVideoRecorder(world,scene,carla,output)
        capture=WalkerPipelineCapture(client,actor,output,scene['case_id'])
        frame_map=FrameMap(output/'video_frames.jsonl')
        index=1
        with (output/'walker-body-history.jsonl').open('x',buffering=1) as body, \
             (output/'camera-frame-joins.jsonl').open('x',buffering=1) as joins:
            for _ in range(FRAMES):
                index=request_next_control(actor,carla,scene,index)
                frame=world.tick();snapshot=world.get_snapshot()
                if frame!=snapshot.frame:raise RuntimeError('Native tick/snapshot frame mismatch')
                sample=sample_original_walker(scene,actor,snapshot)
                camera_join=videos.append(sample)
                captured=capture.capture(frame,sample['time_s'],sample)
                if captured['frame']!=frame:raise RuntimeError('canonical graph/body frame mismatch')
                frame_map.append(frame,sample['time_s'])
                body.write(json.dumps(sample,allow_nan=False)+'\n')
                joins.write(json.dumps(camera_join,allow_nan=False)+'\n')
                frames.append(frame)
    except BaseException as error:
        errors.append(repr(error))
    finally:
        for resource in (frame_map,capture,videos):
            if resource is not None:
                try:
                    if resource is capture:resource.close(confirmed=not errors)
                    else:resource.close()
                except BaseException as error:errors.append(repr(error))
        if actor is not None:
            try:actor.destroy()
            except BaseException as error:errors.append(repr(error))
        try:restoration=restore(client,previous)
        except BaseException as error:errors.append('world restoration: '+repr(error))
    if errors or not restoration.get('restored'):
        write(output/'native-run-status.json',{'phase':'failed','errors':errors,
             'restoration':restoration,'captured_frames':len(frames)})
        raise RuntimeError('Native acquisition or restoration failed; retained failed attempt')
    sources=('scene.json','candidate-crossing.xodr','reviewed-site.json','reviewed-site-audit.json',
             'native-crosswalk-readback.json','road.xodr','trace.jsonl',
             'walker-body-history.jsonl','video_frames.jsonl','camera-frame-joins.jsonl',
             *(name+'.mkv' for name in CAMERAS))
    sources += tuple(ref['path'] for ref in reviewed['source_refs'].values())
    write(output/'acquisition.json',{name:{'kind':'original_native','sha256':sha(output/name)} for name in dict.fromkeys(sources)})
    seal_capture(output,frames=len(frames),restoration=restoration,errors=[],
       encoder_exit_codes={name:0 for name in CAMERAS},
       context={'case_id':scene['case_id'],'map_sha256':scene['map_source_sha256']})
    return {'case_id':scene['case_id'],'frames':len(frames),
            'native_acquisition_sealed':True,'physical_acceptance_claimed':False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--scene',default='scene.json')
    parser.add_argument('--map',default='candidate-crossing.xodr')
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir');parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    scene=check_scene(args.scene,args.map)
    if args.check:print(json.dumps({'case_id':scene['case_id'],'static_construction_valid':True,
                      'planned_frames':FRAMES,'native_started':False,
                      'physical_crosswalk_readback':'pending'}))
    elif args.output_dir:print(json.dumps(run_native(scene,args.scene,args.map,
                                                     args.output_dir,args.host,args.port)))
    else:parser.error('use --check or --output-dir')

if __name__=='__main__':main()
