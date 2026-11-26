"""Survey-gated Native bridge speed capture; CPU --check never imports CARLA."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from geometry import check as geometry_check, open_drive

FRAMES=600
RATE=20
CAMERAS=(
 ('bridge_overview',1280,720,50,-25,24,-40,False),
 ('near_posting',1280,720,-40,-13,9,-22,False),
 ('far_posting',1280,720,140,13,9,-22,False),
 ('subject_chase',1280,720,-10,0,6,-12,True),
)
TARGET_MPS={'probe_01':9.0,'probe_02':13.0}


def check():
    geo=geometry_check()
    if FRAMES/RATE!=30 or len(CAMERAS)!=4 or len({c[0] for c in CAMERAS})!=4:
        raise ValueError('four cameras and 30-second capture required')
    if not TARGET_MPS['probe_01']*2.2369362921<25<TARGET_MPS['probe_02']*2.2369362921:
        raise ValueError('speed requests do not bracket authored posting')
    return {'passed':True,'frames':FRAMES,'rate_hz':RATE,
            'cameras':[c[0] for c in CAMERAS],
            'geometry':geo,'native_imported':False,'physical_acceptance_claimed':False}


def survey(world,carla):
    mapping=world.get_map();root=ET.fromstring(mapping.to_opendrive())
    signs={s.attrib.get('id'):s.attrib for s in root.findall('.//signal')}
    if set(signs)!={'101','102'} or any(s.get('value')!='25' or s.get('unit')!='mph' for s in signs.values()):
        raise RuntimeError('Native structure maximum sign readback differs')
    if signs['101'].get('orientation')!='+' or signs['102'].get('orientation')!='-':
        raise RuntimeError('Native approach sign direction differs')
    if abs(100-float(signs['101']['s'])-30.48)>.01 or abs(float(signs['102']['s'])-200-30.48)>.01:
        raise RuntimeError('Native 100-foot posting distances differ')
    samples=[]
    for x,expected_z in ((-75,0),(0,8),(50,8),(100,8),(175,0)):
        wp=mapping.get_waypoint(carla.Location(x=x,y=-1.75,z=expected_z+1),
                                project_to_road=True,lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id!=1 or wp.lane_id!=-1:
            raise RuntimeError(f'Native bridge lane readback differs at x={x}')
        pos=wp.transform.location
        if abs(pos.x-x)>1 or abs(pos.y+1.75)>1 or abs(pos.z-expected_z)>1:
            raise RuntimeError(f'Native bridge elevation readback differs at x={x}')
        samples.append({'requested_x_m':x,'native_xyz_m':[pos.x,pos.y,pos.z],
                        'road_id':wp.road_id,'lane_id':wp.lane_id})
    return {'signs':[signs['101'],signs['102']],'bridge':samples,
            'sign_pixels_verified':False,'department_determination_verified':False}


def validate_attempt_destination(output_dir):
    output=Path(output_dir).resolve()
    if not output.is_dir():
        raise ValueError('runtime materialized attempt directory is missing')
    if any((output/name).exists() for name in
           ('video_frames.jsonl','bridge-speed-history.jsonl','bridge-context.json')):
        raise ValueError('original Native capture already exists in attempt directory')
    return output


def execute(case_id,output_dir,host,port):
    output=validate_attempt_destination(output_dir)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import snapshot,restore
    from measure import measure
    check()
    suffix=case_id.rsplit('__',1)[-1]
    if suffix not in TARGET_MPS:raise ValueError('unknown exact case')
    client=carla.Client(host,port);client.set_timeout(180)
    saved=snapshot(client);old=client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
        ('vehicle.','walker.','sensor.','controller.')) for a in old.get_actors()):
        raise RuntimeError('requires exclusive idle asynchronous Native world')
    owned=[];queues={};encoders={};changed=False;capture=None;complete=False
    try:
        world=client.generate_opendrive_world(open_drive(),carla.OpendriveGenerationParameters(
            vertex_distance=.5,max_road_length=25,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings)
        seen=survey(world,carla)
        output.mkdir(parents=True,exist_ok=True)
        (output/'road.xodr').write_text(world.get_map().to_opendrive())
        (output/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind':'native','diagnostic_fixture':False,
            'physical_acceptance_claimed':False},indent=2)+'\n')
        (output/'bridge-context.json').write_text(json.dumps({
            'bridge_x_m':[0.0,100.0],'sign_limit_mph':25.0,'posting_distance_m':30.48,
            'native_sign_survey':seen['signs'],'native_bridge_survey':seen['bridge'],
            'department_determination_verified':False,'physical_sign_pixels_verified':False,
            'structure_load_safety_verified':False},indent=2)+'\n')
        library=world.get_blueprint_library();bp=library.find('vehicle.audi.tt')
        bp.set_attribute('role_name','c32014_bridge_speed_subject')
        vehicle=world.spawn_actor(bp,carla.Transform(carla.Location(x=-70,y=-1.75,z=1),carla.Rotation(yaw=0)))
        owned.append(vehicle)
        capture=PipelineCapture(client,vehicle,output,case_id,visibility=False,
            required_observations=json.loads((Path(__file__).parent/'config.json').read_text()).get('required_atoms',[]))
        for name,width,height,x,y,z,pitch,attached in CAMERAS:
            sensor_bp=library.find('sensor.camera.rgb')
            sensor_bp.set_attribute('image_size_x',str(width));sensor_bp.set_attribute('image_size_y',str(height))
            sensor_bp.set_attribute('fov','85');sensor_bp.set_attribute('sensor_tick','.05')
            transform=carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(pitch=pitch))
            camera=world.spawn_actor(sensor_bp,transform,attach_to=vehicle) if attached else world.spawn_actor(sensor_bp,transform)
            owned.append(camera);q=queue.Queue();camera.listen(q.put);queues[name]=q
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                '-f','rawvideo','-pix_fmt','bgra','-s',f'{width}x{height}','-r','20','-i','-',
                '-frames:v','600','-c:v','ffv1','-level','1',str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        with FrameMap(output/'video_frames.jsonl') as frame_map,(output/'bridge-speed-history.jsonl').open('x') as history,(output/'trace.jsonl').open('x') as trace:
            first_time=None
            for index in range(FRAMES):
                x=vehicle.get_transform().location.x
                requested=TARGET_MPS[suffix] if x<170 else 0.0
                vehicle.set_target_velocity(carla.Vector3D(x=requested,y=0,z=0))
                frame=world.tick();snap=world.get_snapshot()
                if snap.frame!=frame:raise RuntimeError('Native frame/snapshot identity differs')
                absolute_time=snap.timestamp.elapsed_seconds
                if first_time is None:first_time=absolute_time
                relative_time=absolute_time-first_time
                capture.capture(frame,relative_time)
                pose=vehicle.get_transform();velocity=vehicle.get_velocity();mapped={}
                for name in queues:
                    image=queues[name].get(timeout=30)
                    while image.frame<frame:image=queues[name].get(timeout=30)
                    if image.frame!=frame:raise RuntimeError('Original camera frame join failed: '+name)
                    encoders[name].stdin.write(image.raw_data);mapped[name]=image.frame
                frame_map.append(frame,relative_time,camera_native_frames=mapped)
                history.write(json.dumps({'video_frame':index,'native_frame':frame,'time_s':relative_time,
                    'native_elapsed_seconds':absolute_time,'subject_id':vehicle.id,
                    'blueprint_id':vehicle.type_id,'position_xyz_m':[
                        pose.location.x,pose.location.y,pose.location.z],
                    'velocity_xyz_mps':[velocity.x,velocity.y,velocity.z],
                    'requested_speed_mps':requested})+'\n')
                trace.write(json.dumps({'frame':frame,'time_s':relative_time,
                    'position':{'x':pose.location.x,'y':pose.location.y,'z':pose.location.z},
                    'position_m':[pose.location.x,pose.location.y,pose.location.z],
                    'heading_deg':pose.rotation.yaw,
                    'speed_mps':math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
                    'speed_mph':math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)/.44704,
                    'control':{'throttle':vehicle.get_control().throttle,
                               'brake':vehicle.get_control().brake,
                               'hand_brake':vehicle.get_control().hand_brake}})+'\n')
        for name,process in encoders.items():
            process.stdin.close();stderr=process.stderr.read()
            if process.wait(timeout=180) or not (output/(name+'.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: '+name+': '+stderr.decode()[-400:])
        measured=measure(output/'bridge-speed-history.jsonl',output/'bridge-context.json')
        (output/'bridge-speed-measurement.json').write_text(json.dumps(measured,indent=2)+'\n')
        complete=True
        return {'frames':FRAMES,'camera_names':list(queues),'measurement':measured,
                'physical_acceptance_claimed':False}
    finally:
        if capture is not None:capture.close(confirmed=complete)
        for process in encoders.values():
            if process.poll() is None:process.kill();process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception:pass
        restoration=restore(client,saved) if changed else {'restored':True,'world_unchanged':True}
        if complete:
            seal_capture(output,frames=FRAMES,restoration=restoration,errors=[],
                encoder_exit_codes={name:process.returncode for name,process in encoders.items()},
                context={'case_id':case_id,'candidate_id':'primary',
                         'bridge_sign_and_department_review':'pending_original_source'})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    p.add_argument('--case-id');p.add_argument('--output-dir');p.add_argument('--host',default='127.0.0.1')
    p.add_argument('--port',type=int,default=2000);a=p.parse_args()
    if not a.check and (not a.case_id or not a.output_dir):
        raise SystemExit('--case-id and --output-dir required')
    print(json.dumps(check() if a.check else execute(a.case_id,a.output_dir,a.host,a.port)))
