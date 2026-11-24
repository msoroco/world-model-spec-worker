"""Survey-gated Native lane-change speed capture; CPU --check does not import CARLA."""
import argparse
import json
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, open_drive

FRAMES = 600
RATE = 20
CAMERAS = (
    ('overview', 1280, 720, -180, -20, 18, -35, False),
    ('lane_change', 1280, 720, -200, -15, 12, -35, False),
    ('road_ahead', 1280, 720, 0, -10, 10, -25, False),
    ('subject_chase', 1280, 720, -12, 0, 6, -12, True),
)
TARGET_MPS = {'probe_01': 30.0, 'probe_02': 35.5397, 'probe_03': 36.5}


def target(case_id, x):
    suffix = case_id.rsplit('__', 1)[-1]
    if suffix not in TARGET_MPS:
        raise ValueError('unknown exact speed probe')
    speed = TARGET_MPS[suffix]
    phase = max(0.0, min(1.0, (x+300)/200))
    lateral_per_x = -3.5 * 6 * phase * (1-phase) / 200 if 0 < phase < 1 else 0.0
    return speed, speed*lateral_per_x


def check():
    road = geometry_check()
    if FRAMES/RATE != 30 or len(CAMERAS) != 4 or len({c[0] for c in CAMERAS}) != 4:
        raise ValueError('four cameras and 30-second capture required')
    if not (TARGET_MPS['probe_01'] < TARGET_MPS['probe_02'] < 35.7632 < TARGET_MPS['probe_03']):
        raise ValueError('speed probe requests differ')
    assert target('x__probe_03', -200)[1] < 0
    return {'passed':True, 'frames':FRAMES, 'rate_hz':RATE, 'cameras':[c[0] for c in CAMERAS],
            'road':road, 'target_requests_mps':TARGET_MPS,
            'native_imported':False, 'physical_acceptance_claimed':False}


def survey(world, carla):
    mapping = world.get_map()
    rows = []
    for x in (-600, 0, 600):
        for y, lane_id in ((-1.75, -1), (-5.25, -2)):
            wp = mapping.get_waypoint(carla.Location(x=x, y=y, z=1),
                                      project_to_road=True, lane_type=carla.LaneType.Driving)
            if wp is None or wp.road_id != 1 or wp.lane_id != lane_id:
                raise RuntimeError(f'Native lane survey differs at x={x}, lane={lane_id}')
            pos=wp.transform.location
            if abs(pos.x-x)>1 or abs(pos.y-y)>1:
                raise RuntimeError('Native lane position survey differs')
            rows.append({'requested_x_m':x,'requested_lane_id':lane_id,
                         'native_xyz_m':[pos.x,pos.y,pos.z], 'road_id':wp.road_id,
                         'lane_id':wp.lane_id})
    return rows


def execute(case_id, output_dir, host, port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    from measure import measure
    check()
    target(case_id, -700)
    output=Path(output_dir).resolve()
    if output.exists():
        raise ValueError('choose a fresh original Native attempt directory')
    client=carla.Client(host,port);client.set_timeout(180)
    saved=snapshot(client);old=client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.','walker.','sensor.','controller.')) for a in old.get_actors()):
        raise RuntimeError('requires an exclusive idle asynchronous Native world')
    owned=[];queues={};encoders={};changed=False
    try:
        world=client.generate_opendrive_world(open_drive(),carla.OpendriveGenerationParameters(
            vertex_distance=1,max_road_length=100,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings)
        lane_survey=survey(world,carla)
        output.mkdir(parents=True)
        (output/'road.xodr').write_text(world.get_map().to_opendrive())
        (output/'lane-survey.json').write_text(json.dumps(lane_survey,indent=2)+'\n')
        library=world.get_blueprint_library()
        bp=library.find('vehicle.audi.tt')
        bp.set_attribute('role_name','c245490_speed_subject')
        vehicle=world.spawn_actor(bp,carla.Transform(carla.Location(x=-700,y=-1.75,z=1),carla.Rotation(yaw=0)))
        owned.append(vehicle)
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
        with FrameMap(output/'video_frames.jsonl') as frame_map,(output/'speed-lane-history.jsonl').open('x') as history:
            first_elapsed=None
            for index in range(FRAMES):
                x=vehicle.get_transform().location.x
                vx,vy=target(case_id,x)
                vehicle.set_target_velocity(carla.Vector3D(x=vx,y=vy,z=0))
                frame=world.tick();snapshot_frame=world.get_snapshot()
                if snapshot_frame.frame!=frame:raise RuntimeError('Native frame/snapshot identity differs')
                absolute_time=snapshot_frame.timestamp.elapsed_seconds
                if first_elapsed is None:first_elapsed=absolute_time
                relative_time=absolute_time-first_elapsed
                transform=vehicle.get_transform();velocity=vehicle.get_velocity()
                wp=world.get_map().get_waypoint(transform.location,project_to_road=True,
                                                lane_type=carla.LaneType.Driving)
                if wp is None or wp.road_id!=1 or wp.lane_id not in (-1,-2):
                    raise RuntimeError('Original subject left surveyed roadway')
                mapped={}
                for name in queues:
                    image=queues[name].get(timeout=30)
                    while image.frame<frame:image=queues[name].get(timeout=30)
                    if image.frame!=frame:raise RuntimeError('Original camera frame join failed: '+name)
                    encoders[name].stdin.write(image.raw_data);mapped[name]=image.frame
                frame_map.append(frame,relative_time,camera_native_frames=mapped)
                history.write(json.dumps({'video_frame':index,'native_frame':frame,'time_s':relative_time,
                    'native_elapsed_seconds':absolute_time,'subject_id':vehicle.id,
                    'blueprint_id':vehicle.type_id,'position_xyz_m':[
                        transform.location.x,transform.location.y,transform.location.z],
                    'velocity_xyz_mps':[velocity.x,velocity.y,velocity.z],
                    'road_id':wp.road_id,'lane_id':wp.lane_id})+'\n')
        for name,process in encoders.items():
            process.stdin.close();stderr=process.stderr.read()
            if process.wait(timeout=180) or not (output/(name+'.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: '+name+': '+stderr.decode()[-400:])
        measured=measure(output/'speed-lane-history.jsonl')
        (output/'speed-lane-measurement.json').write_text(json.dumps(measured,indent=2)+'\n')
        return {'frames':FRAMES,'camera_names':list(queues),'measurement_summary':{
            'maximum_mph':measured['maximum_mph'],
            'first_destination_lane_frame':measured['first_destination_lane_frame']},
            'physical_acceptance_claimed':False}
    finally:
        for process in encoders.values():
            if process.poll() is None:process.kill();process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception:pass
        if changed:restore(client,saved)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    p.add_argument('--execute',action='store_true');p.add_argument('--case-id')
    p.add_argument('--output-dir');p.add_argument('--host',default='127.0.0.1')
    p.add_argument('--port',type=int,default=2000);a=p.parse_args()
    if a.check==a.execute:raise SystemExit('choose --check or --execute')
    if a.execute and (not a.case_id or not a.output_dir):raise SystemExit('--case-id and --output-dir required')
    print(json.dumps(check() if a.check else execute(a.case_id,a.output_dir,a.host,a.port)))
