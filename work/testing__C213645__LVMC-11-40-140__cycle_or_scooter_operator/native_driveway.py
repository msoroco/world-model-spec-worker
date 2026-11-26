"""Original source-gated CARLA driveway-to-sidewalk cycle capture."""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import subprocess
from pathlib import Path

from driveway_case import CASES, measure_original, signed_distance, validate_case


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def body_hull(actor):
    vertices=actor.bounding_box.get_world_vertices(actor.get_transform())
    points=sorted(set((v.x,v.y) for v in vertices))
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lower=[]
    for p in points:
        while len(lower)>1 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    upper=[]
    for p in reversed(points):
        while len(upper)>1 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return [list(p) for p in lower[:-1]+upper[:-1]]


def speed(actor):
    v=actor.get_velocity()
    return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)


class Cameras:
    SPECS = (("overview", 1920, 1080), ("approach", 1280, 720),
             ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))

    def __init__(self, world, carla, ego, target, output):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        try:
            poses = ((-16, -14, 27, -55), (-24, -4, 10, -20),
                     (2, -9, 9, -35), (0, 0, 2, 0))
            for (name, width, height), (dx, dy, z, pitch) in zip(self.SPECS, poses):
                bp = world.get_blueprint_library().find("sensor.camera.rgb")
                bp.set_attribute("image_size_x", str(width))
                bp.set_attribute("image_size_y", str(height))
                bp.set_attribute("fov", "90")
                attached = name == "driver_reference"
                location = (carla.Location(x=dx, y=dy, z=z) if attached else
                            carla.Location(x=target[0] + dx, y=target[1] + dy, z=z))
                pose = carla.Transform(location, carla.Rotation(pitch=pitch))
                sensor = world.spawn_actor(bp, pose, attach_to=ego if attached else None)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames

                def receive(image, q=frames, label=name):
                    try:
                        q.put_nowait(image)
                    except queue.Full:
                        self.errors.append("camera queue overflow: " + label)

                sensor.listen(receive)
                args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                        f"{width}x{height}", "-framerate", "20", "-i", "pipe:0",
                        "-an", "-c:v", "ffv1", "-pix_fmt", "bgra", str(output / (name + ".mkv"))]
                self.encoders[name] = subprocess.Popen(args, stdin=subprocess.PIPE,
                                                       stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        if self.errors:
            raise RuntimeError("; ".join(self.errors))
        for name, _, _ in self.SPECS:
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



class Adapter:
    """Spawn source-reviewed cycle and optional pedestrian for driveway crossing."""
    def __init__(self,world,carla,site):
        self.world,self.carla,self.site=world,carla,site
        self.owned=[]

    def spawn_cycle(self):
        site=self.site;xy=site['approach_route_xy'][0]
        next_xy=site['approach_route_xy'][1]
        yaw=math.degrees(math.atan2(next_xy[1]-xy[1],next_xy[0]-xy[0]))
        loc=self.carla.Location(x=xy[0],y=xy[1],z=site['ego_spawn_z'])
        blueprint=self.world.get_blueprint_library().find(site['vehicle_blueprint_id'])
        actor=self.world.try_spawn_actor(blueprint,self.carla.Transform(loc,self.carla.Rotation(yaw=yaw)))
        if actor is None or actor.type_id!=site['vehicle_blueprint_id']:
            raise ValueError('reviewed cycle spawn failed Native readback')
        self.owned.append(actor);return actor

    def spawn_pedestrian(self):
        site=self.site;xy=site['pedestrian_route_xy'][0]
        loc=self.carla.Location(x=xy[0],y=xy[1],z=site['pedestrian_spawn_z'])
        blueprint=self.world.get_blueprint_library().find(site['pedestrian_blueprint_id'])
        actor=self.world.try_spawn_actor(blueprint,self.carla.Transform(loc))
        if actor is None or actor.type_id!=site['pedestrian_blueprint_id']:
            raise ValueError('reviewed pedestrian spawn failed Native readback')
        self.owned.append(actor);return actor

    def destroy_all(self):
        errors=[]
        for actor in reversed(self.owned):
            try:actor.destroy()
            except BaseException as error:errors.append(repr(error))
        self.owned=[]
        if errors:raise RuntimeError('; '.join(errors))


def steer_to(actor,xy):
    pose=actor.get_transform();desired=math.degrees(math.atan2(xy[1]-pose.location.y,xy[0]-pose.location.x))
    error=((desired-pose.rotation.yaw+180)%360)-180
    return max(-1.,min(1.,error/35.))


def pedestrian_in_region(actor,site):
    if actor is None:return False
    pos=actor.get_location();center=site['pedestrian_conflict_center_xy']
    return math.dist((pos.x,pos.y),center)<=site['pedestrian_conflict_radius_m']


def run_native(cfg,site,site_path,output,host,port):
    """Acquire 900 original frames and physically observed stop/yield contrasts."""
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import snapshot,restore

    output=Path(output).resolve()
    if not output.is_dir():raise ValueError('Native attempt directory must already exist')
    suffix=cfg['selected_case_id'].split('__')[-1]
    case=next((x for x in CASES if x.case_id==suffix),None)
    if case is None:raise ValueError('unknown exact driveway case')
    validate_case(site,case)
    client=carla.Client(host,port);client.set_timeout(30)
    saved_world=snapshot(client);world=client.get_world()
    adapter=None;cameras=capture=frame_map=None
    phase,errors,restored='initializing',[],False
    rows=[]
    try:
        archive=output/'reviewed-site-packet';archive.mkdir(exist_ok=False)
        shutil.copy2(site_path,archive/'site.json')
        for item in site['sources'].values():
            source=(Path(site_path).parent/item['path']).resolve()
            target=archive/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
        map_source=Path(site_path).parent/site['sources']['map']['path']
        map_record=json.loads(map_source.read_text(encoding='utf-8'))
        if (world.get_map().name!=site['map_id'] or
                hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()!=
                map_record.get('opendrive_sha256')):
            raise ValueError('reviewed driveway map differs from Native world')
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        world.apply_settings(settings)
        adapter=Adapter(world,carla,site);ego=adapter.spawn_cycle()
        pedestrian=adapter.spawn_pedestrian() if case.pedestrian else None
        write(output/'acquisition-provenance.json',{'provenance_kind':'native',
              'diagnostic_fixture':False,'method':'original CARLA live run'})
        cameras=Cameras(world,carla,ego,site['edge_point_xy'],output)
        capture=PipelineCapture(client,ego,output,cfg['selected_case_id'])
        frame_map=FrameMap(output/'video_frames.jsonl')
        phase='capturing';site_sha=sha(site_path);native_sha=sha(__file__)
        stop_hold=0;yield_hold=0;stop_done=False;yield_done=False
        with (output/'driveway-history.jsonl').open('x',buffering=1) as stream:
            for index in range(round(cfg['duration_s']*cfg['rate_hz'])):
                pos=ego.get_location();xy=(pos.x,pos.y)
                target=site['stop_point_xy'] if case.stop and not stop_done else site['approach_route_xy'][-1]
                distance=math.dist(xy,target)
                in_region=pedestrian_in_region(pedestrian,site)
                if case.stop and not stop_done and distance<=1.0:
                    stop_hold+=1 if speed(ego)<=.1 else 0
                    brake=True
                    if stop_hold>=20:stop_done=True
                elif case.yield_to_pedestrian and stop_done and in_region and not yield_done:
                    yield_hold+=1 if speed(ego)<=.1 else 0
                    brake=True
                    if yield_hold>=20:yield_done=True
                else:
                    brake=distance<=speed(ego)**2/5+.5 and distance<1.0
                control={'throttle':0. if brake else .25,'brake':.8 if brake else 0.,
                         'hand_brake':False,'steer':steer_to(ego,target)}
                ego.apply_control(carla.VehicleControl(**control))
                if pedestrian is not None:
                    end=site['pedestrian_route_xy'][-1]
                    p=pedestrian.get_location();dx,dy=end[0]-p.x,end[1]-p.y
                    norm=max(math.hypot(dx,dy),.001)
                    direction=carla.Vector3D(dx/norm,dy/norm,0)
                    pedestrian.apply_control(carla.WalkerControl(direction=direction,
                                                                  speed=site['pedestrian_speed_mps']))
                frame=world.tick();snap=world.get_snapshot()
                if snap.frame!=frame:raise RuntimeError('original Native frame identity changed')
                time_s=snap.timestamp.elapsed_seconds
                capture.capture(frame,time_s);cameras.append(frame);frame_map.append(frame,time_s)
                current=ego.get_location();current_region=pedestrian_in_region(pedestrian,site)
                observed_yield=bool(yield_hold>=20 and
                                    current_region and speed(ego)<=.1)
                row={'original_frame':frame,'time_s':time_s,
                     'source_sha256':site_sha,'vehicle_motion_source_sha256':native_sha,
                     'edge_source_sha256':site['sidewalk_edge_source_sha256'],
                     'pedestrian_motion_source_sha256':site['pedestrian_route_source_sha256'],
                     'yield_source_sha256':site['operator_yield_plan_source_sha256'],
                     'ego_id':ego.id,'vehicle_type':site['vehicle_type'],
                     'speed_mps':speed(ego),
                     'distance_before_sidewalk_edge_m':signed_distance((current.x,current.y),site),
                     'pedestrian_in_conflict_area':current_region,
                     'pedestrian_actor_ids':[pedestrian.id] if pedestrian is not None else [],
                     'operator_yield_observed':observed_yield,
                     'pedestrian_position_xy':[pedestrian.get_location().x,pedestrian.get_location().y]
                     if pedestrian is not None else None,
                     'ego_position_xy':[current.x,current.y],
                     'control_command':control}
                stream.write(json.dumps(row,allow_nan=False)+'\n');rows.append(row)
        phase='closing';capture.close();capture=None;frame_map.close();frame_map=None
        cameras.close();cameras=None
        write(output/'driveway-site.json',site)
        write(output/'driveway-measurement.json',measure_original(rows,site,case))
        names=['trace.jsonl','video_frames.jsonl','driveway-history.jsonl',
               'driveway-site.json','driveway-measurement.json','road.xodr','carla_recorder.log',
               *[name+'.mkv' for name,_,_ in Cameras.SPECS]]
        names.extend(str(path.relative_to(output)) for path in archive.rglob('*') if path.is_file())
        write(output/'acquisition.json',{name:{'kind':'original_native','sha256':sha(output/name)} for name in names})
        phase='sealed'
    except BaseException as error:
        errors.append(repr(error));raise
    finally:
        for resource in (capture,frame_map,cameras):
            if resource:
                try:resource.close()
                except BaseException as error:errors.append(repr(error))
        if adapter:
            try:adapter.destroy_all()
            except BaseException as error:errors.append(repr(error))
        try:restored=restore(client,saved_world)['restored']
        except BaseException as error:errors.append(repr(error))
        if phase=='sealed' and not errors and restored:
            seal_capture(output,frames=len(rows),
                         restoration={'restored':True,'settings_readback':'original world snapshot restored'},
                         errors=[],encoder_exit_codes={name:0 for name,_,_ in Cameras.SPECS},
                         context={'driveway_case':cfg['selected_case_id']})
        else:
            write(output/'native-run-status.json',{'phase':phase,'errors':errors,
                                                     'settings_restored':restored})
            if phase=='sealed':raise RuntimeError('Native cleanup or restoration failed')
