"""Proposed original Native C104538 capture; no physical or legal verdict.

Only an operator-supplied exclusive CARLA endpoint may be used. CPU --check
does not import CARLA. This file does not start a server or touch campaign DBs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from cameras import camera_plan
from engineering import CANDIDATES, plan
from geometry import (FT_M, OBSERVER_DISTANCES_FT, TURN_STATION_M,
                      check as geometry_check, open_drive, road_height)
from obstruction import check as obstruction_check, placements

ROOT=Path(__file__).resolve().parent
ASSUMED_DRIVER_EYE_OFFSET_M=1.15


def write_new(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def frame_map_row(index,frame,time_s):
    if type(index) is not int or index<0 or type(frame) is not int or frame<0:
        raise ValueError('Invalid original frame identity')
    if type(time_s) not in (int,float) or not math.isfinite(time_s):
        raise ValueError('Invalid original frame time')
    return {'video_frame':index,'native_frame':frame,'carla_frame':frame,'time_s':time_s}


def check(config):
    suffix=config['case_suffix'];candidate=config['candidate_id']
    if suffix not in OBSERVER_DISTANCES_FT or candidate not in CANDIDATES:
        raise ValueError('Unknown exact case or candidate')
    if config['case_id']!='training__C104538__NRS-484B-407__motor_vehicle_driver__'+suffix:
        raise ValueError('Wrong source-bound case identity')
    if (config['law_id'],config['cell_id'],config['actor']) != (
        'NRS-484B-407','C104538','motor_vehicle_driver'):
        raise ValueError('Wrong frozen law/cell/actor')
    if config['duration_s']!=24 or config['rate_hz']!=20:
        raise ValueError('Original capture timing changed')
    construction=plan(suffix,candidate)
    authored_road=ROOT/'authored_road.xodr'
    if authored_road.exists() and authored_road.read_text()!=open_drive():
        raise ValueError('Materialized authored road differs from exact construction')
    authored_obstruction=ROOT/'obstruction.json'
    if authored_obstruction.exists():
        source=json.loads(authored_obstruction.read_text())
        if (source.get('case_suffix')!=suffix or
            source.get('inner_radius_m')!=construction['authored_obstruction_radius_m'] or
            source.get('road_xodr_sha256')!=hashlib.sha256(open_drive().encode()).hexdigest()):
            raise ValueError('Materialized obstruction differs from exact case source')
    cameras=camera_plan(suffix,candidate)
    if [(c['name'],c['width'],c['height']) for c in cameras] != [
        ('overview',1920,1080),('approach',1280,720),
        ('reference_corner',1280,720),('driver_reference',1280,720)]:
        raise ValueError('Four-view original camera contract changed')
    layout=placements(suffix,candidate)
    return {'geometry':geometry_check(),'obstruction':obstruction_check(),
            'candidate':candidate,'planned_barrier_actors':len(layout),
            'construction_sha256':construction['construction_sha256'],
            'camera_count':4,'native_imported':False,
            'physical_success_claimed':False}


def body_vertices(actor):
    return [[v.x,v.y,v.z] for v in actor.bounding_box.get_world_vertices(actor.get_transform())]


def assumed_driver_viewpoint(location):
    return [location.x,location.y,location.z+ASSUMED_DRIVER_EYE_OFFSET_M]


def camera_pose(carla,spec,ego):
    x,y,z=spec['native_xyz_m']
    if spec['attachment']=='world':
        target=ego.get_transform().location
        dx,dy,dz=target.x-x,target.y-y,target.z-z
        yaw=math.degrees(math.atan2(dy,dx))
        pitch=math.degrees(math.atan2(dz,math.hypot(dx,dy)))
    else:
        yaw=0;pitch=-4
    return carla.Transform(carla.Location(x=x,y=y,z=z),
                           carla.Rotation(yaw=yaw,pitch=pitch))


def control_for_time(carla,time_s):
    # Requested three-point reversal only. Saved heading and footprint decide
    # whether any reversal occurred; these phase times do not prove it.
    if time_s<5:return carla.VehicleControl(throttle=.26,steer=0)
    if time_s<9:return carla.VehicleControl(throttle=.17,steer=-.72)
    if time_s<11:return carla.VehicleControl(brake=1)
    if time_s<15:return carla.VehicleControl(throttle=.17,steer=.72,reverse=True)
    if time_s<19:return carla.VehicleControl(throttle=.17,steer=-.72)
    return carla.VehicleControl(brake=1)


def execute(config,output,host,port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot,restore

    check(config)
    output=Path(output).resolve()
    if not output.is_dir() or not (output/'config.json').is_file():
        raise ValueError('Use a fresh materialized exact-case output directory')
    client=carla.Client(host,int(port));client.set_timeout(180)
    saved=snapshot(client);prior=client.get_world()
    if saved['settings'].synchronous_mode or [actor for actor in prior.get_actors()
        if actor.type_id.startswith(('vehicle.','walker.','sensor.','controller.'))]:
        raise RuntimeError('Requires exclusive idle asynchronous world ownership')
    owned=[];queues={};encoders={};encoder_logs={};capture=None;channels={}
    changed=False;error=None;frames=0;restoration=None
    try:
        suffix=config['case_suffix'];candidate=config['candidate_id']
        construction=plan(suffix,candidate)
        xml=open_drive()
        authored_road=output/'authored_road.xodr'
        if authored_road.exists():
            if authored_road.read_text()!=xml:
                raise ValueError('Materialized authored road differs from exact construction')
        else:
            with authored_road.open('x') as stream:stream.write(xml)
        world=client.generate_opendrive_world(xml,carla.OpendriveGenerationParameters(
            vertex_distance=construction['knobs']['opendrive_vertex_distance_m'],
            max_road_length=50,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping=world.get_map();native_xml=mapping.to_opendrive()
        native_hash=hashlib.sha256(native_xml.encode()).hexdigest()
        with (output/'native_road_readback.xodr').open('x') as stream:stream.write(native_xml)
        library=world.get_blueprint_library()
        barrier_bp=library.find('static.prop.stonewall')
        actor_layout=placements(suffix,candidate)
        barrier_inventory=[]
        for row in actor_layout:
            x,y,z=row['native_xyz_m']
            actor=world.spawn_actor(barrier_bp,carla.Transform(
                carla.Location(x=x,y=y,z=z),
                carla.Rotation(yaw=row['native_tangent_yaw_deg'])))
            owned.append(actor)
            barrier_inventory.append({'id':actor.id,'type_id':actor.type_id,
                'requested':row,'world_vertices_m':body_vertices(actor)})
        actors={}
        elevation_samples=[]
        for station in range(100,301,5):
            waypoint=mapping.get_waypoint_xodr(1,-1,float(station))
            if waypoint is None:raise RuntimeError('Native crest elevation readback missing')
            elevation_samples.append({'station_m':station,
                'native_waypoint_z_m':waypoint.transform.location.z,
                'authored_road_height_m':road_height(station)})
        stations={'ego':TURN_STATION_M-24,
                  'reference_left':TURN_STATION_M-500*FT_M,
                  'reference_right':TURN_STATION_M+500*FT_M}
        for role,station in stations.items():
            lane=-1 if role!='reference_right' else 1
            waypoint=mapping.get_waypoint_xodr(1,lane,station)
            if waypoint is None or waypoint.road_id!=1 or waypoint.lane_id!=lane:
                raise RuntimeError('Native road/lane readback failed: '+role)
            transform=waypoint.transform;transform.location.z+=.5
            blueprint=library.find('vehicle.lincoln.mkz_2020')
            blueprint.set_attribute('role_name','c104538_'+role)
            actor=world.spawn_actor(blueprint,transform)
            owned.append(actor);actors[role]=actor
            actor.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        ego=actors['ego']
        write_new(output/'native-construction-context.json',{
            'case_id':config['case_id'],'candidate_id':candidate,
            'authored_road_sha256':hashlib.sha256(xml.encode()).hexdigest(),
            'authored_obstruction_sha256':hashlib.sha256(
                (ROOT/'obstruction.json').read_bytes()).hexdigest()
                if (ROOT/'obstruction.json').is_file() else None,
            'native_road_sha256':native_hash,
            'authored_limit_ft':OBSERVABILITY_LIMIT(suffix),
            'barrier_blueprint':barrier_bp.id,'barrier_inventory':barrier_inventory,
            'waypoint_elevation_samples':elevation_samples,
            'vehicle_ids':{role:actor.id for role,actor in actors.items()},
            'planned_view_stations_m':stations,
            'driver_eye_offset_assumed_m':ASSUMED_DRIVER_EYE_OFFSET_M,
            'physical_visibility_verified':False,
            'legal_verdict_claimed':False})
        for spec in camera_plan(suffix,candidate):
            blueprint=library.find('sensor.camera.rgb')
            for key,value in (('image_size_x',spec['width']),('image_size_y',spec['height']),
                              ('fov',spec['fov_deg']),('sensor_tick',0)):
                blueprint.set_attribute(key,str(value))
            attached=None if spec['attachment']=='world' else actors[
                'ego' if spec['attachment']=='ego' else spec['attachment']]
            camera=world.spawn_actor(blueprint,camera_pose(carla,spec,ego),attach_to=attached)
            owned.append(camera);queues[spec['name']]=queue.Queue()
            camera.listen(queues[spec['name']].put)
            log=(output/(spec['name']+'.encoder.log')).open('x')
            encoder_logs[spec['name']]=log
            encoders[spec['name']]=subprocess.Popen([
                'ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','rgb24','-s',f"{spec['width']}x{spec['height']}",
                '-r','20','-i','pipe:0','-an','-c:v','ffv1','-level','1',
                str(output/(spec['name']+'.mkv'))],stdin=subprocess.PIPE,stderr=log)
        capture=PipelineCapture(client,ego,output,config['case_id'],visibility=False,
                                required_observations=config.get('required_atoms',[]))
        (output/'channels').mkdir()
        for name in ('drv.u_turn','st.curvature','st.grade','st.crest',
                     'st.sight_distance','rel.oncoming','drv.approaching','kin.position'):
            channels[name]=(output/'channels'/(name+'.jsonl')).open('x')
        start=world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native_body_history.jsonl').open('x') as history, \
             (output/'driver_eye_rays.jsonl').open('x') as rays, \
             (output/'video_frames.jsonl').open('x') as frames_file:
            for index in range(config['duration_s']*config['rate_hz']):
                elapsed=index/config['rate_hz']
                ego.apply_control(control_for_time(carla,elapsed))
                for role in ('reference_left','reference_right'):
                    actors[role].apply_control(carla.VehicleControl(throttle=.10))
                frame=world.tick()
                time_s=world.get_snapshot().timestamp.elapsed_seconds-start
                ego_pose=ego.get_transform()
                motion={'native_frame':frame,'time_s':time_s,
                        'ego_body_vertices_m':body_vertices(ego),
                        'ego_heading_deg':ego_pose.rotation.yaw,
                        'ego_center_xyz_m':[ego_pose.location.x,ego_pose.location.y,ego_pose.location.z],
                        'requested_control_phase_s':elapsed}
                views={}
                for role in ('reference_left','reference_right'):
                    actor=actors[role];pose=actor.get_transform()
                    views[role]={'actor_id':actor.id,
                        'driver_viewpoint_xyz_m':assumed_driver_viewpoint(pose.location),
                        'driver_eye_point_is_assumed':True,
                        'approach_heading_deg':pose.rotation.yaw,
                        'vehicle_body_vertices_m':body_vertices(actor)}
                capture.capture(frame,time_s,extra={'c104538_native':motion,
                                                    'approaching_driver_views':views})
                channel_values={
                    'drv.u_turn':{'observed_ego_heading_deg':motion['ego_heading_deg'],
                                  'observed_body_vertices_m':motion['ego_body_vertices_m'],
                                  'authored_intent':'reverse travel direction'},
                    'st.curvature':{'authored_curvature_per_m':1/500,
                                     'native_map_sha256':native_hash},
                    'st.grade':{'native_map_sha256':native_hash,
                                'authored_crest_height_m':3.2},
                    'st.crest':{'native_map_sha256':native_hash,
                                'authored_turn_station_m':TURN_STATION_M},
                    'st.sight_distance':{'authored_reference_limit_ft':OBSERVABILITY_LIMIT(suffix),
                                         'physical_visibility_verified':False},
                    'rel.oncoming':views,
                    'drv.approaching':views,
                    'kin.position':motion['ego_center_xyz_m']}
                for name,stream in channels.items():
                    stream.write(json.dumps({'time_s':time_s,'native_frame':frame,
                        'value':channel_values[name]},allow_nan=False)+'\n')
                history.write(json.dumps(motion,allow_nan=False)+'\n')
                rays.write(json.dumps({'native_frame':frame,'time_s':time_s,'views':views},
                                      allow_nan=False)+'\n')
                image_hashes={}
                for spec in camera_plan(suffix,candidate):
                    image=queues[spec['name']].get(timeout=30)
                    while image.frame<frame:image=queues[spec['name']].get(timeout=30)
                    if image.frame!=frame:raise RuntimeError('Original camera/Native frame join failed')
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(
                        spec['height'],spec['width'],4)[:,:,:3][:,:,::-1]
                    original_pixels=rgb.tobytes()
                    image_hashes[spec['name']]=hashlib.sha256(original_pixels).hexdigest()
                    encoders[spec['name']].stdin.write(original_pixels)
                frame_row=frame_map_row(index,frame,time_s)
                frame_row['original_rgb_sha256']=image_hashes
                frames_file.write(json.dumps(frame_row)+'\n')
                frames+=1
        if frames!=480:raise RuntimeError('Original frame count incomplete')
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    finally:
        for stream in channels.values():stream.close()
        if capture is not None:
            try:capture.close(confirmed=error is None)
            except BaseException as exc:error=error or {'capture_close_error':str(exc)}
        for name,encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180)!=0:raise RuntimeError('Lossless encoder failed: '+name)
            except BaseException as exc:error=error or {'encoder_error':str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:actor.stop()
                actor.destroy()
            except BaseException as exc:error=error or {'actor_cleanup_error':str(exc)}
        if changed:
            try:restoration=restore(client,saved)
            except BaseException as exc:error=error or {'world_restore_error':str(exc)}
        write_new(output/'native-attempt-status.json',{'frames':frames,'error':error,
            'restoration':restoration,'accepted':False,'legal_verdict_claimed':False})
    if error:raise RuntimeError('Native attempt failed; see native-attempt-status.json: '+str(error))
    return {'frames':frames,'native_attempt_recorded':True,
            'physical_visibility_verified':False,'accepted':False}


def OBSERVABILITY_LIMIT(suffix):return OBSERVER_DISTANCES_FT[suffix]


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',default=str(ROOT/'config.json'))
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output','--output-dir',dest='output')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args();config=json.loads(Path(args.config).read_text())
    if args.check:print(json.dumps(check(config),allow_nan=False))
    else:
        if not args.output:parser.error('--output is required for a Native attempt')
        print(json.dumps(execute(config,args.output,args.host,args.port),allow_nan=False))
