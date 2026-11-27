"""Lazy CARLA acquisition of original lane/body motion and four cameras."""
from __future__ import annotations

from hashlib import sha256
import io
import json
import math
from pathlib import Path
from queue import Queue
import shutil
import subprocess

from outside_lane import build_case, signed_distance, segment_fraction

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


class Adapter:
    def __init__(self, host, port, site, steer_gain):
        import carla
        self.carla = carla
        self.client = carla.Client(str(host), int(port))
        self.client.set_timeout(20)
        self.world = self.client.get_world()
        self.site = site
        if not .015 <= steer_gain <= .04:
            raise ValueError('engineering steer gain outside reviewed controller range')
        self.steer_gain = steer_gain
        self.owned = []
        self.queues = {}
        self.ego = None
        self.route = None
        self.route_index = 0

    def configure(self):
        map_obj = self.world.get_map()
        if map_obj.name != self.site['map_name'] or sha256(map_obj.to_opendrive().encode()).hexdigest() != self.site['map_sha256']:
            raise ValueError('Native OpenDRIVE differs from reviewed source')
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)

    def spawn_vehicle(self, point, **_):
        pose = self.site['native_spawn']['pose_xyz_ypr']
        if math.hypot(pose[0]-point[0], pose[1]-point[1]) > 4:
            raise ValueError('reviewed spawn differs from case route')
        c = self.carla
        transform = c.Transform(c.Location(x=pose[0], y=pose[1], z=pose[2]),
                                c.Rotation(pitch=pose[3], yaw=pose[4], roll=pose[5]))
        blueprint = self.world.get_blueprint_library().find(self.site['native_spawn']['blueprint_id'])
        ego = self.world.try_spawn_actor(blueprint, transform)
        if ego is None or not ego.id:
            raise ValueError('source-pose Native ego spawn failed')
        self.owned.append(ego)
        self.ego = ego
        return ego

    def set_route(self, actor, route, **_):
        if actor != self.ego or len(route) < 2:
            raise ValueError('case Native route absent')
        self.route = route
        offsets = {'overview': (-18, 0, 20), 'approach': (-9, 3, 5),
                   'reference_corner': (3, 4, 5), 'driver_reference': (0, 0, 2)}
        c = self.carla
        for index, name in enumerate(CAMERAS):
            camera = self.world.get_blueprint_library().find('sensor.camera.rgb')
            camera.set_attribute('image_size_x', str(1920 if index == 0 else 1280))
            camera.set_attribute('image_size_y', str(1080 if index == 0 else 720))
            camera.set_attribute('sensor_tick', '.05')
            xyz = offsets[name]
            sensor = self.world.spawn_actor(camera, c.Transform(c.Location(x=xyz[0], y=xyz[1], z=xyz[2])), attach_to=actor)
            queue = Queue()
            sensor.listen(queue.put)
            self.owned.append(sensor)
            self.queues[name] = queue

    def set_capture_metadata(self, actor, metadata):
        if (actor != self.ego or
                metadata.get('lane_marking_source_sha256') != self.site['lane_marking_source_sha256'] or
                metadata.get('route_id') != self.site['routes'][metadata.get('case', '')]['id']):
            raise ValueError('Native capture metadata differs')

    def destroy(self, actor):
        if actor in self.owned:
            actor.destroy()
            self.owned.remove(actor)

    def tick(self):
        loc = self.ego.get_location()
        while self.route_index < len(self.route)-1 and math.hypot(loc.x-self.route[self.route_index][0], loc.y-self.route[self.route_index][1]) < 4:
            self.route_index += 1
        target = self.route[self.route_index]
        yaw = self.ego.get_transform().rotation.yaw
        desired = math.degrees(math.atan2(target[1]-loc.y, target[0]-loc.x))
        error = (desired-yaw+180) % 360-180
        speed = self.ego.get_velocity()
        speed_mps = math.sqrt(speed.x**2+speed.y**2+speed.z**2)
        self.ego.apply_control(self.carla.VehicleControl(
            throttle=max(0,min(.55,(8-speed_mps)*.18)),
            brake=max(0,min(.6,(speed_mps-8)*.2)),
            steer=max(-.7,min(.7,error*self.steer_gain))))
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError('Native tick frame differs')
        return frame, snapshot.timestamp.elapsed_seconds

    def row(self, frame, case):
        loc = self.ego.get_location()
        vel = self.ego.get_velocity()
        speed = math.sqrt(vel.x**2+vel.y**2+vel.z**2)
        selected_route = self.site['routes'][case.name]
        separator = selected_route['separator']
        vertices = self.ego.bounding_box.get_world_vertices(self.ego.get_transform())
        if len(vertices) != 8:
            raise ValueError('original vehicle body vertices missing')
        distances = [signed_distance((p.x, p.y), separator) for p in vertices]
        fractions = [segment_fraction((p.x, p.y), separator) for p in vertices]
        center_signed = signed_distance((loc.x, loc.y), separator)
        center_fraction = segment_fraction((loc.x, loc.y), separator)
        fields = ('map_sha256','lane_marking_source_sha256',
                  'legal_controlled_access_source_sha256','public_highway_boundary_source_sha256',
                  'direction_source_sha256','lane_function_source_sha256',
                  'vehicle_class_source_sha256','paved_shoulder_source_sha256',
                  'lawful_shoulder_sign_source_sha256',
                  'emergency_record_source_sha256',
                  'subsection3_authorization_source_sha256')
        row = {field: self.site[field] for field in fields}
        row.update(case=case.name, ego_id=str(self.ego.id), camera_plan_sha256=self.site['camera_plan_sha256'],
                   approach=case.approach, origin=case.origin,
                   destination=case.destination, route_id=selected_route['id'],
                   vehicle_class=case.vehicle_class,
                   separator_kind='solid_white',
                   separator_source_sha256=separator['source_sha256'],
                   emergency_required=case.emergency_required,
                   subsection3_shoulder_authorized=case.subsection3_shoulder_authorized,
                   shoulder_paved=bool(self.site.get('shoulder_paved')),
                   lawful_sign_permits_shoulder=bool(self.site.get('lawful_sign_permits_shoulder')),
                   original_frame=frame, source_sha256=self.site['reviewed_site_sha256'],
                   capture_packet_sha256=self.site['reviewed_site_sha256'],
                   ego_speed_mps=speed, center_signed_m=center_signed,
                   body_min_signed_m=min(distances),
                   body_max_signed_m=max(distances),
                   center_segment_fraction=center_fraction,
                   body_min_segment_fraction=min(fractions),
                   body_max_segment_fraction=max(fractions))
        return row, [loc.x,loc.y,loc.z], self.ego.get_transform().rotation.yaw

    def pixels(self, frame):
        from PIL import Image
        images = {}
        for name in CAMERAS:
            image = self.queues[name].get(timeout=10)
            if image.frame != frame:
                raise ValueError('original camera frame differs: '+name)
            raw = Image.frombytes('RGBA',(image.width,image.height),bytes(image.raw_data),'raw','BGRA')
            stream = io.BytesIO()
            raw.convert('RGB').save(stream,format='PNG')
            images[name] = stream.getvalue()
        return images

    def cleanup(self):
        try:
            if self.ego is not None:
                self.ego.apply_control(self.carla.VehicleControl(brake=1))
        finally:
            for actor in reversed(self.owned):
                try:
                    actor.destroy()
                except Exception:
                    pass


def capture(host, port, destination, site, case, bundle):
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    from pipeline_capture import PipelineCapture
    destination = Path(destination).resolve()
    if not destination.is_dir() or 'runtime-work' not in str(destination):
        raise ValueError('fresh materialized .runtime-work attempt required')
    if any((destination / name).exists() for name in ('original-history.jsonl','capture-seal.json','result.json')):
        raise ValueError('original attempt already contains capture evidence')
    config = json.loads((destination/'config.json').read_text())
    adapter = Adapter(host,port,site,float(config.get('steer_gain',.025)))
    saved = snapshot(adapter.client)
    finished = False
    pipeline = None
    try:
        adapter.configure()
        build_case(adapter,site,case)
        pipeline = PipelineCapture(adapter.client,adapter.ego,destination,
                                   site['assignment_id']+'__'+case.name)
        folders = {name: destination / ('frames-'+name) for name in CAMERAS}
        for folder in folders.values(): folder.mkdir()
        rows = []
        previous = None
        with FrameMap(destination/'video_frames.jsonl') as mapping:
            for index in range(900):
                frame, elapsed = adapter.tick()
                if previous and (frame != previous[0]+1 or abs(elapsed-previous[1]-.05) > .002):
                    raise ValueError('original Native 20 Hz continuity failed')
                previous = frame, elapsed
                row, xyz, yaw = adapter.row(frame,case)
                pipeline.capture(frame,index/20)
                images = adapter.pixels(frame)
                hashes = {}
                for name, raw in images.items():
                    if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
                        raise ValueError('original pixels absent: '+name)
                    (folders[name]/f'{index:04d}.png').write_bytes(raw)
                    hashes[name] = sha256(raw).hexdigest()
                mapping.append(frame,index/20,camera_png_sha256=hashes)
                rows.append(row)
        pipeline.close(confirmed=True)
        (destination/'original-history.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
        for name, folder in folders.items():
            subprocess.run(['ffmpeg','-v','error','-nostdin','-framerate','20','-i',str(folder/'%04d.png'),
                            '-frames:v','900','-c:v','ffv1',str(destination/(name+'.mkv'))],check=True)
            shutil.rmtree(folder)
        (destination/'original-source-receipt.json').write_text(json.dumps({
            'source_kind':'original_native_capture','diagnostic_fixture':False,
            'case_id':site['assignment_id']+'__'+case.name,'frame_count':900,
            'history_sha256':digest(destination/'original-history.jsonl'),
            'trace_sha256':digest(destination/'trace.jsonl'),
            'frame_map_sha256':digest(destination/'video_frames.jsonl'),
            'lane_function_source_sha256':site['lane_function_source_sha256']},sort_keys=True)+'\n')
        finished = True
    finally:
        if pipeline is not None:
            pipeline.close(confirmed=False)
        adapter.cleanup()
        restoration = restore(adapter.client,saved)
        if finished:
            (destination/'restoration.json').write_text(json.dumps(restoration,sort_keys=True)+'\n')
    if finished:
        from worker_exchange.native_output import seal_capture
        (destination/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind':'native','diagnostic_fixture':False,
            'source_kind':'original_native_capture','case_id':site['assignment_id']+'__'+case.name},
            sort_keys=True)+'\n')
        seal_capture(destination,frames=900,restoration=restoration,errors=[],
                     encoder_exit_codes={name:0 for name in CAMERAS},
                     context={'reviewed_site_sha256':site['reviewed_site_sha256'],
                              'origin':case.origin,'destination':case.destination,
                              'separator':'solid_white','approach':case.approach})
