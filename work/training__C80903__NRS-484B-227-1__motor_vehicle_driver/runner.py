"""Source-gated Native divided-roadway turn capture with observed pose and turn review."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
ASSIGNMENT='training__C80903__NRS-484B-227-1__motor_vehicle_driver'
VIEWS=('overview','approach','reference_corner','driver_reference')
SOURCE_KEYS=('native_map_sha256','divider_geometry_sha256','roadway_direction_sha256',
             'physical_opening_sha256','vehicle_extent_sha256','ego_pose_source_sha256',
             'turn_annotation_sha256')

def require(ok,message):
    if not ok:raise ValueError(message)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def check(config):
    require(config.get('case_id','').startswith(ASSIGNMENT+'__') and
            config.get('law_id')=='NRS-484B-227-1' and config.get('cell_id')=='C80903' and
            config.get('actor')=='motor_vehicle_driver','Exact divided-road assignment changed')
    require(config.get('frozen_cell')=={'layout':'divided_road','maneuver':'left_turn','control':'median_barrier'},
            'Frozen divided-road cell changed')
    require(config.get('rate_hz')==20 and config.get('duration_s')==30 and config.get('frames')==600,
            'Exact 600-frame 30-second capture missing')
    require(tuple(c.get('name') for c in config.get('cameras',[]))==VIEWS and
            all(c.get('fps')==20 and c.get('width',0)>=1280 and c.get('height',0)>=720 for c in config['cameras']),
            'Canonical four-camera Native plan missing')
    require(config.get('legal_verdict') is None and not config.get('physical_completion'),
            'Premature physical or legal outcome')
    return {'case_id':config['case_id'],'frames':600,'carla_contacted':False,
            'requested_crossing_station_m':config.get('requested_crossing_station_m'),
            'observed_crossing_station_m':None}

def read_original(context_path,annotation_path):
    require(context_path and annotation_path,'Original divided-road survey and turn annotation required')
    p=Path(context_path);context=json.loads(p.read_text());annotation=json.loads(Path(annotation_path).read_text())
    require(context.get('assignment_id')==ASSIGNMENT and
            context.get('source_kind')=='original_native_divided_highway_readback' and
            context.get('fixed_cell')=={'layout':'divided_road','maneuver':'left_turn','control':'median_barrier'},
            'Original divided-road source identity missing')
    require(context.get('map_name') and context.get('vehicle_blueprint') and
            len(context.get('spawn_xyz_yaw_deg',[]))==4 and
            len(context.get('route_waypoints_xy_m',[]))>=4,
            'Original map, vehicle or route survey missing')
    require(set(context.get('camera_poses',{}))==set(VIEWS),
            'Original four-camera pose survey missing')
    require(context.get('turn_annotation_sha256')==sha(annotation_path),
            'Original turn annotation source hash changed')
    for key in SOURCE_KEYS:
        value=context.get(key);doc=context.get('source_documents',{}).get(key)
        require(isinstance(value,str) and len(value)==64 and all(x in '0123456789abcdef' for x in value) and
                isinstance(doc,str) and doc.startswith('original-') and '/' not in doc and '\\' not in doc and
                sha(p.parent/doc)==value,'Original source document missing or changed: '+key)
    require(context.get('public_authority_crossover_established') in (True,False,None),
            'Original public-authority disposition malformed')
    if context['public_authority_crossover_established'] in (True,False):
        key='public_authority_crossover_sha256';doc=context.get('source_documents',{}).get(key)
        require(isinstance(doc,str) and doc.startswith('original-') and sha(p.parent/doc)==context.get(key),
                'Original public-authority establishment document missing')
    require(len(annotation.get('frames',[]))==600 and
            all(row.get('video_frame')==i and row.get('turn_mode') in ('none','left_turn','semicircular_turn','u_turn')
                for i,row in enumerate(annotation['frames'])),
            'Original per-frame turn annotation missing')
    for name in VIEWS:
        pose=context['camera_poses'][name]
        require(len(pose.get('location_xyz_m',[]))==3 and len(pose.get('rotation_pyr_deg',[]))==3,
                'Original camera pose missing: '+name)
    return context,annotation

def controller(position,yaw_deg,speed,waypoints):
    """Pure proportional waypoint steering; never infers observed turn from target."""
    px,py=position;nearest=min(range(len(waypoints)),key=lambda i:math.hypot(px-waypoints[i][0],py-waypoints[i][1]))
    target=waypoints[min(nearest+2,len(waypoints)-1)]
    bearing=math.degrees(math.atan2(target[1]-py,target[0]-px))
    error=(bearing-yaw_deg+180)%360-180
    steer=max(-1,min(1,error/45))
    finish=nearest>=len(waypoints)-2 and math.hypot(px-waypoints[-1][0],py-waypoints[-1][1])<2
    return {'throttle':0 if finish or speed>=4 else 0.28,'brake':1 if finish else 0,
            'steer':steer,'target_index':min(nearest+2,len(waypoints)-1)}

def execute(config,output_dir,context_path,annotation_path,host,port):
    check(config);context,annotations=read_original(context_path,annotation_path)
    require('.runtime-work' in os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT',''),
            'Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    repo=ROOT.parents[2];sys.path.insert(0,str(repo/'runtime/scenario_pipeline'))
    sys.path.insert(1,str(repo/'runtime/python'))
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import snapshot,restore
    output=Path(output_dir);require(output.is_dir(),'Materialized Native output required')
    (output/'original_divided_context.json').write_bytes(Path(context_path).read_bytes())
    (output/'original_turn_annotations.json').write_bytes(Path(annotation_path).read_bytes())
    for doc in context['source_documents'].values():
        (output/doc).write_bytes((Path(context_path).parent/doc).read_bytes())
    client=carla.Client(host,port);client.set_timeout(15);world=client.get_world();original=snapshot(client)
    actors=[];sensors=[];encoders={};codes={};images=queue.Queue();finished=False
    try:
        require(world.get_map().name==context['map_name'],'Original divided-road map differs')
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        world.apply_settings(settings)
        bp=world.get_blueprint_library().find(context['vehicle_blueprint'])
        require(bp is not None,'Original vehicle blueprint unavailable')
        x,y,z,yaw=context['spawn_xyz_yaw_deg']
        vehicle=world.try_spawn_actor(bp,carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(yaw=yaw)))
        require(vehicle is not None,'Original divided-road spawn occupied');actors.append(vehicle)
        for camera in config['cameras']:
            cb=world.get_blueprint_library().find('sensor.camera.rgb')
            cb.set_attribute('image_size_x',str(camera['width']))
            cb.set_attribute('image_size_y',str(camera['height']))
            cb.set_attribute('fov',str(camera['fov_deg']))
            pose=context['camera_poses'][camera['name']];cx,cy,cz=pose['location_xyz_m'];pitch,cyaw,roll=pose['rotation_pyr_deg']
            sensor=world.spawn_actor(cb,carla.Transform(carla.Location(x=cx,y=cy,z=cz),
                carla.Rotation(pitch=pitch,yaw=cyaw,roll=roll)),attach_to=vehicle if camera['name']=='driver' else None)
            actors.append(sensor);sensors.append(sensor)
            encoders[camera['name']]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                '-f','rawvideo','-pix_fmt','bgra','-s',f"{camera['width']}x{camera['height']}",
                '-r','20','-i','-','-frames:v','600','-c:v','ffv1','-level','1',str(output/(camera['name']+'.mkv'))],
                stdin=subprocess.PIPE,stderr=subprocess.PIPE)
            sensor.listen(lambda image,name=camera['name']:images.put((name,image)))
        with PipelineCapture(client,vehicle,output,config['case_id'],required_observations=config['required_atoms']) as capture,\
                FrameMap(output/'video_frames.jsonl') as frame_map,\
                (output/'median-capture.jsonl').open('x',buffering=1) as trace:
            for i in range(600):
                pose=vehicle.get_transform();velocity=vehicle.get_velocity()
                speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                control=controller((pose.location.x,pose.location.y),pose.rotation.yaw,speed,
                                   context['route_waypoints_xy_m'])
                vehicle.apply_control(carla.VehicleControl(throttle=control['throttle'],
                    brake=control['brake'],steer=control['steer']))
                frame=world.tick();pose=vehicle.get_transform();velocity=vehicle.get_velocity()
                seen=set()
                while len(seen)<4:
                    name,image=images.get(timeout=15)
                    if image.frame!=frame or name in seen:continue
                    encoders[name].stdin.write(image.raw_data);seen.add(name)
                capture.capture(frame,i/20,extra={'video_frame':i})
                frame_map.append(frame,i/20,native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                ann=annotations['frames'][i]
                direction='median' if context['median_y_m'][0]<=pose.location.y<=context['median_y_m'][1] else (
                    'right_hand' if pose.location.y<context['median_y_m'][0] else 'opposite')
                trace.write(json.dumps({'video_frame':i,'native_frame':frame,'time_s':i/20,
                    'source_cameras':{name:i for name in VIEWS},'ego_center_x_m':pose.location.x,
                    'ego_center_y_m':pose.location.y,'ego_width_m':vehicle.bounding_box.extent.y*2,
                    'ego_length_m':vehicle.bounding_box.extent.x*2,'observed_yaw_deg':pose.rotation.yaw,
                    'roadway_direction':direction,'left_turn_active':ann['turn_mode']=='left_turn',
                    'semicircular_turn_active':ann['turn_mode']=='semicircular_turn',
                    'u_turn_active':ann['turn_mode']=='u_turn','controller_target_index':control['target_index']})+'\n')
        for name,process in encoders.items():
            process.stdin.close();error=process.stderr.read();codes[name]=process.wait(timeout=180)
            require(codes[name]==0 and (output/(name+'.mkv')).is_file(),
                    'Source camera encode failed: '+name+' '+error.decode()[-200:])
        finished=True
    finally:
        for process in encoders.values():
            if process.poll() is None:process.kill();process.wait()
        for sensor in sensors:sensor.stop()
        for actor in reversed(actors):actor.destroy()
        restored=restore(client,original)
        if finished and len(codes)==4:
            seal_capture(output,frames=600,restoration=restored,errors=[],encoder_exit_codes=codes,
                         context={'case_id':config['case_id'],'original_divider_source':context['divider_geometry_sha256']})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir')
    p.add_argument('--divided-context');p.add_argument('--turn-annotations')
    p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=2000)
    a=p.parse_args();config=json.loads((ROOT/'config.json').read_text())
    if a.check:print(json.dumps(check(config)))
    else:
        require(a.output_dir,'Output directory required')
        execute(config,a.output_dir,a.divided_context or os.environ.get('SCENARIO_DIVIDED_CONTEXT'),
                a.turn_annotations or os.environ.get('SCENARIO_TURN_ANNOTATIONS'),a.host,a.port)
