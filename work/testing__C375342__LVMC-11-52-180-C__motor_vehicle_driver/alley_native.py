"""Original 60-minute Native alley parking acquisition, lazy with respect to CARLA."""
from __future__ import annotations
import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path
from alley_site import inside

CAMERAS = (("overview",1920,1080),("approach",1280,720),("reference_corner",1280,720),("driver_reference",1280,720))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path,payload):
    Path(path).write_text(json.dumps(payload,indent=2,allow_nan=False)+"\n",encoding="utf-8")

def sha_opendrive(mapping):
    return hashlib.sha256(mapping.to_opendrive().encode()).hexdigest()

def drive_control(position,heading_deg,speed,target,hold,brake_gain=.7):
    distance=math.dist(position,target)
    if hold and distance<1.2 and speed<.15:
        return {"steer":0.0,"throttle":0.0,"brake":1.0,"hand_brake":True},"hold"
    bearing=math.atan2(target[1]-position[1],target[0]-position[0])
    heading=math.radians(heading_deg)
    error=math.atan2(math.sin(bearing-heading),math.cos(bearing-heading))
    steer=max(-.65,min(.65,error*1.2))
    braking_distance=speed*speed/4+1.5
    if distance<=braking_distance:
        return {"steer":steer,"throttle":0.0,"brake":brake_gain,"hand_brake":False},"approach"
    return {"steer":steer,"throttle":.28 if speed<3 else 0.0,"brake":0.0,"hand_brake":False},"approach"

def desired_station(elapsed_s,intervals,approach_lead_s):
    return any(start-approach_lead_s<=elapsed_s<end for start,end in intervals)

class FourCameras:
    def __init__(self, world, carla, ego, target, output):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        try:
            poses = ((-16, -14, 27, -55), (-24, -4, 10, -20),
                     (2, -9, 9, -35), (0, 0, 2, 0))
            for (name, width, height), (dx, dy, z, pitch) in zip(CAMERAS, poses):
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("fov", "90")
                attached = name == "driver_reference"
                location = (carla.Location(x=dx, y=dy, z=z) if attached else
                            carla.Location(x=target[0] + dx, y=target[1] + dy, z=z))
                sensor = world.spawn_actor(blueprint, carla.Transform(
                    location, carla.Rotation(pitch=pitch)), attach_to=ego if attached else None)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames

                def receive(image, q=frames, label=name):
                    try:
                        q.put_nowait(image)
                    except queue.Full:
                        self.errors.append("camera queue overflow: " + label)

                sensor.listen(receive)
                cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                       "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                       f"{width}x{height}", "-framerate", "20", "-i", "pipe:0",
                       "-an", "-c:v", "ffv1", "-pix_fmt", "bgra",
                       str(output / (name + ".mkv"))]
                self.encoders[name] = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                                       stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        if self.errors:
            raise RuntimeError("; ".join(self.errors))
        for name, _, _ in CAMERAS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError("camera frame differs from original world frame: " + name)
            self.encoders[name].stdin.write(image.raw_data)

    def close(self):
        failures = []
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
            except BaseException as error:
                failures.append(repr(error))
        for name, process in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.wait(timeout=180) != 0:
                    failures.append("camera encoder failed: " + name)
            except BaseException as error:
                failures.append(repr(error))
        for sensor in reversed(self.sensors):
            try:
                sensor.destroy()
            except BaseException as error:
                failures.append(repr(error))
        self.sensors = []
        self.encoders = {}
        if failures:
            raise RuntimeError("; ".join(failures))


def observed_intervals(rows, actor_id):
    """Reduce contiguous original parked frames, retaining actual timestamps."""
    intervals = []
    start = None
    last = None
    for row in rows:
        if row['vehicle_actor_id'] != actor_id:
            raise ValueError('original vehicle actor changed')
        if last is not None and (row['sample_index'] != last['sample_index'] + 1 or
                                 row['time_s'] <= last['time_s'] or
                                 row['frame'] != last['frame'] + 1):
            raise ValueError('original parking history has a frame or time gap')
        if row['parked_observed'] and start is None:
            start = row['time_s']
        if not row['parked_observed'] and start is not None:
            intervals.append({'start_s': start, 'end_s': row['time_s'],
                              'vehicle_id': str(actor_id)})
            start = None
        last = row
    if start is not None:
        intervals.append({'start_s': start, 'end_s': last['time_s'] + .05,
                          'vehicle_id': str(actor_id)})
    return intervals


def run_native(cfg, site, records, site_path, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output).resolve()
    if not output.is_dir():
        raise ValueError('Native attempt directory must already exist')
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved_world = snapshot(client)
    world = client.get_world()
    actors = []
    cameras = capture = frame_map = None
    phase = 'initializing'
    errors = []
    restored = False
    frame_count = 0
    try:
        mapping = world.get_map()
        if mapping.name != site['map_id'] or sha_opendrive(mapping) != records['map']['opendrive_sha256']:
            raise ValueError('loaded original OpenDRIVE differs from reviewed source')
        target = site['target_xy']
        relocation = site['relocation_xy']
        exit_station = site['exit_xy']
        target_wp = mapping.get_waypoint(carla.Location(x=target[0],y=target[1],z=0))
        relocation_wp = mapping.get_waypoint(carla.Location(x=relocation[0],y=relocation[1],z=0))
        exit_wp = mapping.get_waypoint(carla.Location(x=exit_station[0],y=exit_station[1],z=0))
        if not target_wp or target_wp.road_id != site['road_id'] or not relocation_wp or not exit_wp:
            raise ValueError('Native target alley or relocation station differs from reviewed source')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        marking = records['marking']
        pose = marking['prop_pose']
        prop = world.spawn_actor(library.find(marking['prop_blueprint_id']), carla.Transform(
            carla.Location(x=pose['x'],y=pose['y'],z=pose['z']),carla.Rotation(yaw=pose['yaw_deg'])))
        actors.append(prop)
        if prop.type_id != marking['prop_blueprint_id']:
            raise ValueError('Native marking prop readback differs')
        ego = world.spawn_actor(library.find(site['vehicle_blueprint_id']), carla.Transform(
            carla.Location(x=relocation[0],y=relocation[1],z=relocation_wp.transform.location.z+.5),
            carla.Rotation(yaw=site['approach_heading_degrees'])))
        actors.append(ego)
        if ego.type_id != site['vehicle_blueprint_id']:
            raise ValueError('Native vehicle blueprint readback differs')
        source_output = output / 'reviewed-site'
        source_output.mkdir(exist_ok=False)
        shutil.copy2(site_path, source_output/'site.json')
        for ref in site['sources'].values():
            source = (Path(site_path).parent/ref['path']).resolve()
            dest = source_output/ref['path']
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,dest)
        context = {'assignment_id':cfg['assignment_id'],'case_id':cfg['selected_case_id'],
                   'site_sha256':sha(site_path),'map_sha256':records['map']['opendrive_sha256'],
                   'vehicle_actor_id':ego.id,'marking_actor_id':prop.id,
                   'municipal_alley_source':site['sources']['alley']['sha256'],
                   'engineer_designation_source':site['sources']['designation']['sha256'],
                   'angle_marking_source':site['sources']['marking']['sha256'],
                   'other_parking_rules_source':site['sources']['other_parking_rules']['sha256'],
                   'loading_activity_source':site['sources']['other_parking_rules']['sha256'],
                   'prior_vehicle_history_source':site['sources']['prior_history']['sha256'],
                   'review_status':'original_reviewed'}
        write(output/'alley-context.json',context)
        write(output/'acquisition-provenance.json',{'provenance_kind':'native',
              'diagnostic_fixture':False,'method':'original CARLA 3600-second designated alley parking history'})
        cameras = FourCameras(world,carla,ego,target,output)
        capture = PipelineCapture(client,ego,output,cfg['selected_case_id'])
        frame_map = FrameMap(output/'video_frames.jsonl')
        total_frames = round(cfg['duration_s']*cfg['rate_hz'])
        if cfg['duration_s'] != 3600 or cfg['rate_hz'] != 20:
            raise ValueError('exact rolling-hour Native frame contract differs')
        requested = site['requested_intervals_s']
        lead = cfg.get('engineering_approach_lead_s',15)
        rows = []
        first_time = None
        phase = 'capturing'
        with (output/'parking-history.jsonl').open('x',buffering=1) as stream:
            for index in range(total_frames):
                desired_park = desired_station(index/20,requested,lead)
                station = target if desired_park else (exit_station if index/20 >= requested[-1][1] else relocation)
                transform = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                position = [transform.location.x,transform.location.y]
                command,state = drive_control(position,transform.rotation.yaw,speed,station,True,
                                              cfg.get('engineering_brake_gain',.7))
                ego.apply_control(carla.VehicleControl(**command))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError('Native world frame differs from snapshot')
                time_s = snap.timestamp.elapsed_seconds
                if first_time is None:
                    first_time = time_s
                capture.capture(frame,time_s)
                cameras.append(frame)
                frame_map.append(frame,time_s)
                transform = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                position = [transform.location.x,transform.location.y]
                in_space = inside(tuple(position),marking['governed_space_polygon_xy'])
                parked = bool(speed<=.15 and in_space)
                row = {'frame':frame,'sample_index':index,'time_s':time_s,
                       'relative_time_s':time_s-first_time,
                       'native_time_s':time_s,'position_xy':position,'body_yaw_degrees':transform.rotation.yaw,
                       'speed_mps':speed,'parked_observed':parked,'inside_marked_space':in_space,
                       'desired_park':desired_park,'control_state':state,'control_command':command,
                       'vehicle_actor_id':ego.id,'marking_actor_id':prop.id}
                stream.write(json.dumps(row,allow_nan=False)+'\n')
                rows.append(row)
                frame_count += 1
        intervals = observed_intervals(rows,ego.id)
        write(output/'parking-intervals.json',{'case_id':cfg['selected_case_id'],
              'vehicle_id':str(ego.id),'window_history_status':'complete_original',
              'sampling_rate_hz':20,'first_native_frame':rows[0]['frame'],
              'last_native_frame':rows[-1]['frame'],'requested_intervals_s':requested,
              'intervals':intervals})
        phase='closing'
        capture.close();capture=None
        frame_map.close();frame_map=None
        cameras.close();cameras=None
        names=['trace.jsonl','video_frames.jsonl','parking-history.jsonl',
               'parking-intervals.json','alley-context.json','road.xodr','carla_recorder.log',
               'reviewed-site/site.json',
               *['reviewed-site/'+ref['path'] for ref in site['sources'].values()],
               *[name+'.mkv' for name,_,_ in CAMERAS]]
        write(output/'acquisition.json',{name:{'kind':'original_native','sha256':sha(output/name)} for name in names})
        phase='sealed'
    except BaseException as error:
        errors.append(repr(error))
        raise
    finally:
        for resource in (capture,frame_map,cameras):
            if resource:
                try:resource.close()
                except BaseException as error:errors.append(repr(error))
        for actor in reversed(actors):
            try:actor.destroy()
            except BaseException as error:errors.append(repr(error))
        try:restored=restore(client,saved_world)['restored']
        except BaseException as error:errors.append(repr(error))
        if phase=='sealed' and not errors and restored:
            seal_capture(output,frames=frame_count,
                         restoration={'restored':True,'settings_readback':'original world snapshot restored'},
                         errors=[],encoder_exit_codes={name:0 for name,_,_ in CAMERAS},
                         context={'designated_alley_duration':context,'observed_intervals':intervals})
        else:
            write(output/'native-run-status.json',{'phase':phase,'errors':errors,'settings_restored':restored})
            if phase=='sealed':
                raise RuntimeError('Native cleanup or restoration failed')
