"""Source-gated CARLA bus-stop duration acquisition with owned actors.

The requested D-relative hold is an engineering target. Original activity timing
and location are measured from Native frames and independently reviewed later.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import queue
from pathlib import Path

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SIZES = {'overview': (1920, 1080), 'approach': (1280, 720),
         'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value, name: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('invalid ' + name)
    return float(value)


def pose(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError('reviewed Native transform missing')
    for key in ('x', 'y', 'z', 'yaw'):
        finite(value.get(key), key)
    return value


def read_site(path: Path, expected_sha256: str) -> dict:
    path = Path(path)
    if sha(path) != expected_sha256:
        raise ValueError('reviewed bus-stop site SHA256 differs')
    site = json.loads(path.read_text())
    if site.get('source_kind') != 'original_independent_site_review' or site.get('cell_id') != 'C393262':
        raise ValueError('original independent C393262 site review required')
    if site.get('layout') != 'residence_district' or site.get('stop_kind') != 'bus_stop':
        raise ValueError('reviewed residential bus stop differs')
    for key in ('reviewer', 'map_sha256', 'stop_id', 'stop_boundary_source_sha256',
                'designation_source_sha256', 'operator_source_sha256'):
        if not site.get(key):
            raise ValueError('missing reviewed bus-stop source: ' + key)
    designation = site.get('designation')
    if not isinstance(designation, dict) or designation.get('authority') != 'City Traffic Engineer' or \
            designation.get('stop_id') != site['stop_id'] or not designation.get('conditions_reviewed') or \
            designation.get('source_sha256') != site['designation_source_sha256']:
        raise ValueError('actual stop-specific designation unproved')
    boundary = site.get('stop_polygon_xy_m')
    if not isinstance(boundary, list) or len(boundary) < 4 or any(not isinstance(point, list) or len(point) != 2 for point in boundary):
        raise ValueError('reviewed bus stop boundary polygon required')
    for point in boundary:
        finite(point[0], 'stop boundary x');finite(point[1], 'stop boundary y')
    duration = finite(designation.get('applicable_duration_s'), 'applicable designated duration')
    if duration <= 2 or duration > 30:
        raise ValueError('actual designated duration does not fit 45 s complete-interval profile')
    identity = site.get('bus_identity')
    if not isinstance(identity, dict) or identity.get('tour_bus') is not False or not identity.get('covered_operator') or not identity.get('bus_id'):
        raise ValueError('covered non-tour bus/operator identity unproved')
    scene = site.get('native_scene')
    if not isinstance(scene, dict) or not str(scene.get('bus_blueprint_id', '')).startswith('vehicle.'):
        raise ValueError('reviewed Native bus blueprint required')
    for key in ('approach_pose', 'stop_pose', 'exit_pose'):
        pose(scene.get(key))
    cameras = scene.get('camera_mounts')
    if not isinstance(cameras, dict) or set(cameras) != set(VIEWS):
        raise ValueError('four reviewed camera mounts required')
    for spec in cameras.values():
        pose(spec.get('transform'))
        if spec.get('attach_to') not in ('bus', 'world'):
            raise ValueError('reviewed camera parent differs')
        if not 0 < finite(spec.get('fov_deg'), 'camera fov') < 180:
            raise ValueError('reviewed camera fov differs')
    return site


def inside_polygon(point, polygon) -> bool:
    x,y=point;inside=False
    for i in range(len(polygon)):
        x1,y1=polygon[i-1];x2,y2=polygon[i]
        if ((y1>y)!=(y2>y)) and x<(x2-x1)*(y-y1)/(y2-y1)+x1:
            inside=not inside
    return inside


def steer_toward(transform, target: dict) -> float:
    loc=transform.location
    heading=math.degrees(math.atan2(target['y']-loc.y,target['x']-loc.x))
    delta=(heading-transform.rotation.yaw+180)%360-180
    return max(-1.0,min(1.0,delta/45.0))


def requested_hold(site: dict, relation: str) -> float:
    duration = float(site['designation']['applicable_duration_s'])
    if relation not in ('below', 'at', 'above'):
        raise ValueError('unknown duration relation')
    target = duration + {'below': -2.0, 'at': 0.0, 'above': 2.0}[relation]
    if target <= 0 or target > 32:
        raise ValueError('duration target outside complete capture profile')
    return target


class NativeBusOperator:
    def __init__(self, world, carla, site: dict):
        self.world, self.carla, self.site = world, carla, site
        self.owned = []
        self.bus = None
        self.cameras = {}

    def transform(self, value: dict):
        value = pose(value)
        return self.carla.Transform(self.carla.Location(x=value['x'], y=value['y'], z=value['z']),
                                    self.carla.Rotation(yaw=value['yaw'], pitch=value.get('pitch', 0), roll=value.get('roll', 0)))

    def setup(self):
        if sha_bytes(self.world.get_map().to_opendrive().encode('utf-8')) != self.site['map_sha256']:
            raise ValueError('reviewed OpenDRIVE differs from Native world')
        scene = self.site['native_scene']
        try:
            blueprint = self.world.get_blueprint_library().find(scene['bus_blueprint_id'])
            self.bus = self.world.spawn_actor(blueprint, self.transform(scene['approach_pose']))
            if self.bus is None:
                raise ValueError('Native bus actor spawn failed')
            self.owned.append(self.bus)
            for name in VIEWS:
                spec = scene['camera_mounts'][name]
                blueprint = self.world.get_blueprint_library().find('sensor.camera.rgb')
                width, height = SIZES[name]
                blueprint.set_attribute('image_size_x', str(width))
                blueprint.set_attribute('image_size_y', str(height))
                blueprint.set_attribute('fov', str(spec['fov_deg']))
                kwargs = {'attach_to': self.bus} if spec['attach_to'] == 'bus' else {}
                camera = self.world.spawn_actor(blueprint, self.transform(spec['transform']), **kwargs)
                if camera is None:
                    raise ValueError('Native bus camera spawn failed: ' + name)
                self.owned.append(camera)
                self.cameras[name] = camera
            return {'bus_actor_id': self.bus.id, 'camera_actor_ids': {name: camera.id for name, camera in self.cameras.items()}}
        except BaseException:
            self.close()
            raise

    def close(self):
        errors = []
        for actor in reversed(self.owned):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                actor.destroy()
            except BaseException as error:
                errors.append(error)
        self.owned.clear(); self.cameras.clear(); self.bus = None
        if errors:
            raise ValueError('Native bus ownership cleanup failed') from errors[0]

    def capture(self, output: Path, conduct: str, relation: str) -> dict:
        if self.bus is None or set(self.cameras) != set(VIEWS):
            raise ValueError('bus and four cameras must be constructed')
        if conduct not in ('stand', 'park'):
            raise ValueError('unknown standing or parking conduct')
        hold = requested_hold(self.site, relation)
        output = Path(output)
        if output.exists():
            raise ValueError('retain prior Native bus attempt')
        output.mkdir(parents=True)
        previous = copy.deepcopy(self.world.get_settings())
        settings = copy.deepcopy(previous)
        settings.synchronous_mode = True; settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)
        inbox = {name: queue.Queue() for name in VIEWS}
        rows = []
        state = 'approach'; hold_start = None; hold_end = None
        stop = self.site['native_scene']['stop_pose']; exit_pose = self.site['native_scene']['exit_pose']
        try:
            for name, sensor in self.cameras.items():
                sensor.listen(lambda image, q=inbox[name]: q.put(image))
            for index in range(900):
                transform = self.bus.get_transform(); loc = transform.location
                velocity = self.bus.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                distance_to_stop = math.hypot(loc.x-stop['x'], loc.y-stop['y'])
                distance_to_exit = math.hypot(loc.x-exit_pose['x'], loc.y-exit_pose['y'])
                if state == 'approach' and distance_to_stop < 2.5:
                    state = 'settle'
                if state == 'settle' and speed < .1:
                    state = 'hold'; hold_start = index
                if state == 'hold' and (index-hold_start)/20 >= hold:
                    state = 'depart'; hold_end = index
                if state == 'depart' and distance_to_exit < 2.5:
                    state = 'clear'
                if state in ('approach', 'depart'):
                    target=stop if state == 'approach' else exit_pose
                    control = self.carla.VehicleControl(throttle=.28, steer=steer_toward(transform,target), brake=0, hand_brake=False)
                else:
                    control = self.carla.VehicleControl(throttle=0, brake=1,
                                                        hand_brake=(state == 'hold' and conduct == 'park'))
                self.bus.apply_control(control)
                frame = self.world.tick()
                cameras = {}
                for name in VIEWS:
                    image = inbox[name].get(timeout=30)
                    if image.frame != frame:
                        raise ValueError('Native bus camera/world frame mismatch')
                    folder = output / name;folder.mkdir(exist_ok=True)
                    path = folder / f'{index:04d}.png';image.save_to_disk(str(path))
                    cameras[name] = {'path': str(path.relative_to(output)), 'sha256': sha(path), 'native_frame': frame}
                transform = self.bus.get_transform();loc = transform.location
                velocity = self.bus.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                box = self.bus.bounding_box
                corners=[]
                for sx,sy in ((-1,-1),(1,-1),(1,1),(-1,1)):
                    vertex=transform.transform(box.location+self.carla.Location(x=sx*box.extent.x,y=sy*box.extent.y,z=0))
                    corners.append([finite(vertex.x,'body x'),finite(vertex.y,'body y')])
                in_stop=all(inside_polygon(point,self.site['stop_polygon_xy_m']) for point in corners)
                rows.append({'frame': index,'time_s':index/20,'original_frame':frame,'bus_id':self.site['bus_identity']['bus_id'],'native_actor_id':self.bus.id,
                             'bus_center_xy_m':[finite(loc.x,'bus x'),finite(loc.y,'bus y')],
                             'bus_footprint_xy_m':corners,'bus_speed_mps':speed,
                             'controller_state':state,'inside_stop_boundary':in_stop,
                             'cameras':cameras})
            if hold_start is None or hold_end is None or state not in ('depart','clear'):
                raise ValueError('Native bus did not complete requested stopped interval and departure')
            ledger = {'kind':'native_bus_frame_ledger','source_class':'original_native_capture',
                      'bus_id':self.site['bus_identity']['bus_id'],'native_actor_id':self.bus.id,'frames':rows,'controller_hold_frames':[hold_start,hold_end],
                      'physical_acceptance':False,'legal_verdict':None}
            path=output/'native_frames.json';path.write_text(json.dumps(ledger,indent=2)+'\n')
            return {'native_frames_sha256':sha(path),'frame_count':900,'hold_target_s':hold,
                    'controller_hold_frames':[hold_start,hold_end],'physical_acceptance':False}
        finally:
            for sensor in self.cameras.values():
                sensor.stop()
            self.world.apply_settings(previous)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def capture(adapter, site_path: Path, case_id: str, destination: Path) -> dict:
    """The adapter owns a dedicated CARLA world connection, not a server lifecycle."""
    site_path=Path(site_path)
    expected=site_path.with_suffix(site_path.suffix+'.sha256')
    if not expected.is_file():
        raise ValueError('independent reviewed site SHA256 sidecar required')
    site=read_site(site_path,expected.read_text().strip())
    relation=case_id.split('__')[-1].split('_')[-1]
    conduct=case_id.split('__')[-1].split('_')[0]
    operator=NativeBusOperator(adapter.world,adapter.carla,site)
    try:
        setup=operator.setup()
        result=operator.capture(destination,conduct,relation)
        result.update(setup)
        result['case_id']=case_id
        result['reviewed_site_sha256']=sha(site_path)
        return result
    finally:
        operator.close()
