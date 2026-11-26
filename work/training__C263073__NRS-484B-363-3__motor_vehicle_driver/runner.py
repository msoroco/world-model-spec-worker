"""Original Native school-zone U-turn draft; --check is CARLA-free."""
import argparse
import json
import os
from pathlib import Path
import queue
import subprocess

from layout import ZONE,TURN,check as layout_check,open_drive,planned_pose
from drive import command
from review_context import attach_original_review

FRAMES=600
CAMERAS=(('overview',1920,1080,-12,-18,25,-65),('approach',1280,720,-25,-12,8,-30),
    ('reference_corner',1280,720,5,13,12,-45),('driver_reference',1280,720,.5,0,1.6,0))


def check():
    cfg=json.loads(Path('config.json').read_text())
    if cfg['cell_id']!='C263073' or cfg['law_id']!='NRS-484B-363-3' or cfg['case_suffix'] not in ('controlled_1','controlled_2'):
        raise ValueError('Exact assignment differs')
    if cfg.get('vehicle_blueprint') not in ('vehicle.tesla.model3','vehicle.mini.cooper_s'):
        raise ValueError('Unexpected original vehicle blueprint')
    if cfg['duration_s']!=30 or cfg['rate_hz']!=20 or len(CAMERAS)!=4 or CAMERAS[0][1:3]!=(1920,1080):
        raise ValueError('Capture policy differs')
    if [(item.get('name'),item.get('width'),item.get('height')) for item in cfg.get('cameras',[])] != [
        (name,width,height) for name,width,height,*_ in CAMERAS]:
        raise ValueError('Four-camera config differs from original Native construction')
    return {'passed':True,'geometry':layout_check(),'frame_count':FRAMES,
        'kinematic_path_only':False,'native_imported':False,'physical_acceptance_claimed':False}


def actor_row(actor):
    transform=actor.get_transform()
    return {'actor_id':actor.id,'blueprint_id':actor.type_id,
        'center_xy_m':[transform.location.x,transform.location.y],
        'heading_deg':transform.rotation.yaw,
        'body_xy_m':[[p.x,p.y] for p in actor.bounding_box.get_world_vertices(transform)]}


def execute(output,host,port,review_source_dir):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import snapshot,restore
    cfg=json.loads(Path('config.json').read_text());check();output=Path(output).resolve()
    if not output.is_dir() or not (output/'construction.json').is_file() or not (output/'config.json').is_file():
        raise ValueError('Native output must be a fresh materialized exact-case directory')
    if (output/'native-motion.jsonl').exists() or (output/'capture-seal.json').exists():
        raise ValueError('Original Native acquisition already exists')
    review_source_dir=Path(review_source_dir).resolve()
    from review_context import verified_sources
    try:
        review_packet=json.loads((review_source_dir/'review.json').read_text())
        verified_sources(review_source_dir,review_packet)
    except BaseException as exc:
        (output/'native-run-status.json').write_text(json.dumps({
            'errors':[{'pre_capture_source_error':str(exc)}],'frames':0},indent=2)+'\n')
        raise
    try:
        client=carla.Client(host,port);client.set_timeout(180)
        old=client.get_world();saved=snapshot(client)
        if old.get_settings().synchronous_mode or any(a.type_id.startswith(('vehicle.','walker.','sensor.','controller.')) for a in old.get_actors()):
            raise RuntimeError('Exclusive idle asynchronous Native world required')
    except BaseException as exc:
        (output/'native-run-status.json').write_text(json.dumps({
            'errors':[{'native_preflight_error':str(exc)}],'frames':0},indent=2)+'\n')
        raise
    owned=[];encoders={};queues={};changed=False;pipeline_capture=None
    frames=[];encoder_exit_codes={};errors=[];restoration={'restored':False}
    try:
        world=client.generate_opendrive_world(open_drive(),carla.OpendriveGenerationParameters(
            vertex_distance=.5,max_road_length=50,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True;settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10;world.apply_settings(settings)
        mapping=world.get_map()
        for y,lane in ((-5.5,-1),(5.5,1)):
            waypoint=mapping.get_waypoint(carla.Location(x=-12,y=y,z=1),project_to_road=True,lane_type=carla.LaneType.Driving)
            if waypoint is None or waypoint.road_id!=1 or waypoint.lane_id!=lane:
                raise RuntimeError('Native two-way road readback failed')
        # Diagnostic zone outline does not establish legal designation or sign/beacon activity.
        for x in (-20,20):
            world.debug.draw_line(carla.Location(x=x,y=-8,z=.05),carla.Location(x=x,y=8,z=.05),
                thickness=.08,color=carla.Color(255,255,0),life_time=35,persistent_lines=False)
        bp=world.get_blueprint_library().find(cfg['vehicle_blueprint'])
        ego=world.try_spawn_actor(bp,carla.Transform(carla.Location(x=-25,y=-5.5,z=1.2),carla.Rotation(yaw=0)))
        if ego is None:raise RuntimeError('Original vehicle spawn failed')
        ego.set_simulate_physics(True);owned.append(ego)
        (output/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind':'native','diagnostic_fixture':False,
            'physical_acceptance_claimed':False},indent=2)+'\n')
        pipeline_capture=PipelineCapture(client,ego,output,cfg['case_id'],
            visibility=False,required_observations=cfg.get('required_atoms',[]))
        walker_bp=next((x for x in world.get_blueprint_library().filter('walker.pedestrian.*')),None)
        if walker_bp is None:raise RuntimeError('Original pedestrian blueprint missing')
        walker=world.try_spawn_actor(walker_bp,carla.Transform(carla.Location(x=4,y=7.5,z=1.2)))
        if walker is None:raise RuntimeError('Original pedestrian spawn failed')
        owned.append(walker)
        for name,width,height,x,y,z,pitch in CAMERAS:
            cbp=world.get_blueprint_library().find('sensor.camera.rgb')
            for key,value in (('image_size_x',width),('image_size_y',height),('fov',85),('sensor_tick',.05)):
                cbp.set_attribute(key,str(value))
            camera_pose=carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(pitch=pitch))
            sensor=world.spawn_actor(cbp,camera_pose,attach_to=ego if name=='driver_reference' else None)
            owned.append(sensor);received=queue.Queue();sensor.listen(received.put);queues[name]=received
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','bgra','-s',f'{width}x{height}','-r','20','-i','-',
                '-frames:v',str(FRAMES),'-c:v','ffv1',str(output/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        with (output/'native-motion.jsonl').open('x') as motion,FrameMap(output/'video_frames.jsonl') as frame_map:
            for index in range(FRAMES):
                transform=ego.get_transform();velocity=ego.get_velocity()
                control=command(index,cfg['case_suffix']=='controlled_2',
                    (transform.location.x,transform.location.y),transform.rotation.yaw,
                    (velocity.x**2+velocity.y**2)**.5)
                ego.apply_control(carla.VehicleControl(steer=control['steer'],
                    throttle=control['throttle'],brake=control['brake']))
                native=world.tick()
                pipeline_capture.capture(native,index/20)
                motion.write(json.dumps({'frame':native,'native_frame':native,'video_frame':index,'time_s':index/20,
                    'source_kind':'original_native','ego':actor_row(ego),
                    'other_person':actor_row(walker),'control':control,
                    'kinematic_path_only':False},allow_nan=False)+'\n')
                camera_frames={}
                for name,*_ in CAMERAS:
                    image=queues[name].get(timeout=30)
                    while image.frame<native:image=queues[name].get(timeout=30)
                    if image.frame!=native:raise RuntimeError('Original four-camera join differs')
                    encoders[name].stdin.write(image.raw_data);camera_frames[name]=image.frame
                frames.append(frame_map.append(native,index/20,camera_native_frames=camera_frames))
        pipeline_capture.close(confirmed=True);pipeline_capture=None
        for name,process in encoders.items():
            process.stdin.close();error=process.stderr.read();code=process.wait(timeout=180)
            encoder_exit_codes[name]=code
            if code or not (output/(name+'.mkv')).is_file():
                raise RuntimeError('Original FFV1 encoding failed: '+name+error.decode()[-400:])
        (output/'frame-map.json').write_text(json.dumps(frames)+'\n')
        (output/'road.xodr').write_text(open_drive())
        independent_review=attach_original_review(output,review_source_dir)
        (output/'school-context.json').write_text(json.dumps({'source_kind':'original_native',
            'cell_id':'C263073','zone':ZONE,'turn':TURN,'zone_designation_reviewed':False,
            'school_adjacency_reviewed':False,'highway_status_reviewed':False,
            'child_identity_and_presence_reviewed':False,'session_operation_civil_time_reviewed':False,
            'class_hours_reviewed':False,'beacon_and_sign_state_reviewed':False,
            'all_five_exceptions_reviewed':False,'partial_zone_maneuver_treatment_reviewed':False,
            'path_is_kinematic':False,'independent_review':independent_review},indent=2)+'\n')
    except BaseException as exc:
        errors.append({'type':type(exc).__name__,'message':str(exc)})
        raise
    finally:
        if pipeline_capture is not None:
            try:pipeline_capture.close(confirmed=False)
            except BaseException as exc:errors.append({'capture_close_error':str(exc)})
        for process in encoders.values():
            if process.poll() is None:process.kill();process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception:pass
        if changed:
            try:restoration=restore(client,saved)
            except BaseException as exc:errors.append({'restore_error':str(exc)})
        (output/'native-attempt-status.json').write_text(json.dumps({
            'frames':len(frames),'errors':errors,'physical_completion':None,
            'legal_verdict':None},indent=2)+'\n')
        if errors:
            (output/'native-run-status.json').write_text(json.dumps({
                'errors':errors,'frames':len(frames)},indent=2)+'\n')
    if errors:raise RuntimeError('Native capture failed: '+str(errors))
    try:
        seal_capture(output,frames=len(frames),restoration=restoration,errors=[],
            encoder_exit_codes=encoder_exit_codes,
            context={'school_zone_source_review_bound':True,'physical_completion':None})
    except BaseException as exc:
        (output/'native-run-status.json').write_text(json.dumps({
            'errors':[{'capture_seal_error':str(exc)}],'frames':len(frames)},indent=2)+'\n')
        raise
    return {'frames':len(frames),'camera_names':list(queues),'path_is_kinematic':False,
        'zone_designation_unverified':True,'physical_acceptance_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir',type=Path);parser.add_argument('--host',default='localhost')
    parser.add_argument('--port',type=int,default=2000)
    parser.add_argument('--review-source-dir',type=Path);args=parser.parse_args()
    if args.check:print(json.dumps(check()))
    else:
        review_dir=args.review_source_dir or os.environ.get('C263073_REVIEW_SOURCE_DIR')
        if args.output_dir is None or review_dir is None:
            parser.error('Materialized Native output and C263073_REVIEW_SOURCE_DIR required')
        print(json.dumps(execute(args.output_dir,args.host,args.port,review_dir)))
