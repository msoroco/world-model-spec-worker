"""Proposed observed-pose Native pedestrian capture; only --check runs on CPU."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from engineering import candidate
from geometry import CROSSWALK_ID, check as geometry_check, open_drive

HERE=Path(__file__).resolve().parent
RATE_HZ=20
FRAMES=240


def cameras(plan):
    overhead=plan['engineering']['camera_overhead_z_m']
    return [
        {'name':'overview','width':1920,'height':1080,'fov_deg':90,
         'xyz_m':[-7,0,overhead],'yaw_deg':0,'pitch_deg':-65},
        {'name':'approach','width':1280,'height':720,'fov_deg':90,
         'xyz_m':[-5,-4,3],'yaw_deg':40,'pitch_deg':-20},
        {'name':'reference_corner','width':1280,'height':720,'fov_deg':90,
         'xyz_m':[0,5,3],'yaw_deg':-90,'pitch_deg':-25},
        {'name':'pedestrian_reference','width':1280,'height':720,'fov_deg':90,
         'xyz_m':[5,-3,3],'yaw_deg':150,'pitch_deg':-20}]


def check(config):
    geometry=geometry_check()
    suffix=config['case_suffix']; ident=config['candidate_id']
    plan=candidate(suffix,ident)
    if config['case_id']!=plan['case_id'] or config['selected_case_id']!=plan['case_id']:
        raise ValueError('Crosswalk case identity differs')
    if (config['law_id'],config['cell_id'],config['actor'])!=('NRS-484B-293','C10316','pedestrian'):
        raise ValueError('Frozen crosswalk assignment identity differs')
    if (config['rate_hz'],config['duration_s'])!=(RATE_HZ,12):
        raise ValueError('Full crossing capture window changed')
    profile=cameras(plan)
    if [(x['name'],x['width'],x['height']) for x in profile]!=[
        (x['name'],x['width'],x['height']) for x in config['cameras']]:
        raise ValueError('Declared and executable camera contract differs')
    if (HERE/'road.xodr').read_text().strip()!=open_drive():
        raise ValueError('Authored crosswalk road source changed')
    return {'geometry':geometry,'candidate':ident,'camera_names':[x['name'] for x in profile],
            'native_imported':False,'physical_success_claimed':False}


def write_new(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')


def footprint(actor):
    vertices=actor.bounding_box.get_world_vertices(actor.get_transform())
    points=sorted({(round(v.x,5),round(v.y,5)) for v in vertices})
    if len(points)!=4:
        raise RuntimeError('Native pedestrian lacks four-vertex ground footprint')
    return [list(p) for p in points]


def observe(walker,frame,time_s):
    pose=walker.get_transform(); direction=pose.get_forward_vector(); velocity=walker.get_velocity()
    norm=math.hypot(direction.x,direction.y)
    if norm<.99:
        raise RuntimeError('Native pedestrian heading invalid')
    return {'native_frame':frame,'time_s':time_s,'crosswalk_id':CROSSWALK_ID,
            'pedestrian_xy_m':[pose.location.x,pose.location.y],
            'pedestrian_forward_xy':[direction.x/norm,direction.y/norm],
            'speed_mps':math.hypot(velocity.x,velocity.y),
            'pedestrian_footprint_xy_m':footprint(walker)}


def execute(config,output,host,port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.world_restore import snapshot,restore

    check(config)
    output=Path(output).resolve()
    if not output.is_dir() or not (output/'config.json').is_file():
        raise ValueError('Use a new materialized exact-case output directory')
    client=carla.Client(host,int(port)); client.set_timeout(180)
    prior=client.get_world(); state=snapshot(client)
    if state['settings'].synchronous_mode or any(a.type_id.startswith(('vehicle.','walker.','sensor.'))
                                                  for a in prior.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous world ownership required')
    plan=candidate(config['case_suffix'],config['candidate_id'])
    owned=[]; encoders={}; encoder_logs={}; camera_queues={}; channels={}
    capture=None; changed=False; restored=None; error=None; frames=0
    try:
        world=client.generate_opendrive_world(open_drive(),carla.OpendriveGenerationParameters(
            vertex_distance=.25,max_road_length=50,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=True))
        changed=True
        settings=world.get_settings(); settings.synchronous_mode=True
        settings.fixed_delta_seconds=1/RATE_HZ; settings.substepping=True
        settings.max_substep_delta_time=.01; settings.max_substeps=10
        world.apply_settings(settings); world.set_weather(carla.WeatherParameters.ClearNoon)
        native_xml=world.get_map().to_opendrive()
        native_hash=hashlib.sha256(native_xml.encode()).hexdigest()
        library=world.get_blueprint_library()
        walker_options=sorted(library.filter('walker.pedestrian.*'),key=lambda x:x.id)
        if not walker_options:
            raise RuntimeError('No Native pedestrian blueprint available')
        lateral=plan['engineering']['target_lateral_m']
        start_x=plan['engineering']['spawn_start_x_m']
        walker=world.try_spawn_actor(walker_options[0],carla.Transform(
            carla.Location(x=start_x,y=lateral,z=.5),carla.Rotation(yaw=0)))
        if walker is None:
            raise RuntimeError('Native pedestrian spawn failed')
        owned.append(walker)
        write_new(output/'native-construction-context.json',{
            'case_id':config['case_id'],'candidate_id':config['candidate_id'],
            'native_map_sha256':native_hash,'authored_map_sha256':hashlib.sha256(open_drive().encode()).hexdigest(),
            'pedestrian_blueprint':walker.type_id,'initial_original_footprint':footprint(walker),
            'requested_plan':plan,'crosswalk_object_native_confirmation':'unverified',
            'physical_success_claimed':False})
        for spec in cameras(plan):
            bp=library.find('sensor.camera.rgb')
            for key,value in (('image_size_x',spec['width']),('image_size_y',spec['height']),
                              ('fov',spec['fov_deg']),('sensor_tick',0)):
                bp.set_attribute(key,str(value))
            x,y,z=spec['xyz_m']
            sensor=world.spawn_actor(bp,carla.Transform(carla.Location(x=x,y=y,z=z),
                carla.Rotation(yaw=spec['yaw_deg'],pitch=spec['pitch_deg'])))
            owned.append(sensor); camera_queues[spec['name']]=queue.Queue()
            sensor.listen(camera_queues[spec['name']].put)
            encoder_logs[spec['name']]=(output/(spec['name']+'.encoder.log')).open('x')
            encoders[spec['name']]=subprocess.Popen([
                'ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','rgb24','-s',f"{spec['width']}x{spec['height']}",
                '-r',str(RATE_HZ),'-i','pipe:0','-an','-c:v','ffv1','-level','1',
                str(output/(spec['name']+'.mkv'))],stdin=subprocess.PIPE,
                stderr=encoder_logs[spec['name']])
        velocity=8/12
        walker.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=1),speed=velocity))
        for _ in range(int(plan['engineering']['pre_roll_s']*RATE_HZ)):
            world.tick()
        if abs(walker.get_transform().location.x-plan['engineering']['capture_start_x_m'])>.35:
            raise RuntimeError('Observed Native pre-roll did not reach capture start')
        capture=PipelineCapture(client,walker,output,config['case_id'],
                                visibility=False,required_observations=config.get('required_atoms',[]))
        (output/'channels').mkdir()
        for item in config['recording_description']['channels']:
            channels[item['name']]=(output/'channels'/(item['name']+'.jsonl')).open('x')
        start=world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native_samples.jsonl').open('x') as samples, \
             (output/'video_frames.jsonl').open('x') as video_frames:
            for index in range(FRAMES):
                frame=world.tick(); time_s=world.get_snapshot().timestamp.elapsed_seconds-start
                observed=observe(walker,frame,time_s)
                samples.write(json.dumps(observed,allow_nan=False)+'\n')
                capture.capture(frame,time_s,extra={'c10316_native':observed})
                values={'kin.position':observed['pedestrian_xy_m'],
                        'kin.heading':observed['pedestrian_forward_xy'],
                        'rel.occupies':{'crosswalk_id':CROSSWALK_ID,
                                       'original_footprint_xy_m':observed['pedestrian_footprint_xy_m']},
                        'native_pedestrian_pose':observed,
                        'camera_frame_join':{'native_frame':frame,'video_frame':index}}
                for name,stream in channels.items():
                    stream.write(json.dumps({'time_s':time_s,'value':values[name]},allow_nan=False)+'\n')
                for spec in cameras(plan):
                    image=camera_queues[spec['name']].get(timeout=30)
                    while image.frame<frame:
                        image=camera_queues[spec['name']].get(timeout=30)
                    if image.frame!=frame:
                        raise RuntimeError('Original camera/Native frame join failed')
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(
                        spec['height'],spec['width'],4)[:,:,:3][:,:,::-1]
                    encoders[spec['name']].stdin.write(rgb.tobytes())
                video_frames.write(json.dumps({'video_frame':index,'native_frame':frame,
                                                'carla_frame':frame,'time_s':time_s})+'\n')
                frames+=1
        write_new(output/'crosswalk-context.json',{
            'source_kind':'native_observation','native_map_sha256':native_hash,
            'observed_frame_count':frames,'crosswalk_id':CROSSWALK_ID,
            'crosswalk_center_xy_m':[0,0],'crosswalk_passage_forward_xy':[1,0],
            'crosswalk_length_m':4,'crosswalk_width_m':3,
            'practicability_facts':[{'name':'right_half_obstruction','observed':None},
                                    {'name':'oncoming_pedestrians','observed':None}],
            'physical_practicability_verified':False})
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
            except BaseException as exc:error=error or {'owned_actor_cleanup_error':str(exc)}
        if changed:
            try:restored=restore(client,state)
            except BaseException as exc:error=error or {'world_restore_error':str(exc)}
        write_new(output/'native-capture-report.json',{
            'case_id':config['case_id'],'candidate_id':config['candidate_id'],
            'frames':frames,'expected_frames':FRAMES,'restoration':restored,
            'error':error,'accepted':False,'physical_practicability_verified':False,
            'required_saved_checks':['original pedestrian footprint and full crosswalk traversal',
                                     'full four-camera/Native join','independent original-pixel audit',
                                     'source-grounded practicability review']})
    if error:raise RuntimeError('Native attempt failed; inspect native-capture-report.json: '+str(error))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir');parser.add_argument('--host');parser.add_argument('--port',type=int)
    args=parser.parse_args()
    config=json.loads((HERE/'config.json').read_text())
    if args.check:print(json.dumps(check(config),allow_nan=False,sort_keys=True))
    else:
        if not args.output_dir or not args.host or not args.port:
            raise ValueError('Explicit materialized output and owned Native endpoint required')
        execute(config,args.output_dir,args.host,args.port)


if __name__=='__main__':main()
