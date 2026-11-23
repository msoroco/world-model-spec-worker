"""Native stop-sign capture with four synchronized original camera streams.

The --check path is CPU only. Native capture must be launched through runtime.py
with a fresh materialized attempt; this runner never declares legal acceptance.
"""

import argparse
from contextlib import ExitStack, contextmanager
import json
import math
from pathlib import Path
from queue import Empty, Queue
import subprocess

import hashlib
import xml.etree.ElementTree as ET





ROAD = Path(__file__).resolve().parent / 'native-map-plan/stop-sign-crossing.xodr'
JUNCTION = 158191
APPROACH = 158190
THROUGH = (158194, 158195, 158196)


def opendrive_to_carla(x, y):
    """CARLA's Native world reflects the OpenDRIVE map's Y axis."""
    return (float(x), -float(y))


def _lanes(road):
    section = road.find('./lanes/laneSection')
    if section is None:
        raise ValueError('Missing authored lane section')
    return {int(lane.attrib['id']): lane for lane in section.findall('./left/lane')
            + section.findall('./right/lane') if lane.attrib.get('type') == 'driving'}


def validate_authored_site(path=ROAD):
    path = Path(path)
    document = ET.parse(path).getroot()
    if document.tag != 'OpenDRIVE':
        raise ValueError('Not an OpenDRIVE site')
    roads = {int(road.attrib['id']): road for road in document.findall('road')}
    if set(roads) != {158190, 158192, 158193, *THROUGH}:
        raise ValueError('Authored junction road inventory differs')
    if set(_lanes(roads[APPROACH])) != {-1}:
        raise ValueError('Stop approach is not one-way')
    if any(set(_lanes(roads[rid])) != {-1, 1} for rid in THROUGH):
        raise ValueError('Through highway is not two-way')
    if any(road.attrib.get('junction') != str(JUNCTION) for road in
           (roads[158192], roads[158195])):
        raise ValueError('Crossing segments lack junction membership')
    for rid, x, y, hdg, length in ((APPROACH, -80, 0, 0, 72),
                                   (158192, -8, 0, 0, 16),
                                   (158193, 8, 0, 0, 72),
                                   (158194, 0, -80, math.pi / 2, 72),
                                   (158195, 0, -8, math.pi / 2, 16),
                                   (158196, 0, 8, math.pi / 2, 72)):
        geometry = roads[rid].find('./planView/geometry')
        if geometry is None or geometry.find('line') is None or any(
                not math.isclose(float(geometry.attrib[key]), value, abs_tol=1e-9)
                for key, value in (('x', x), ('y', y), ('hdg', hdg), ('length', length))):
            raise ValueError('Authored road centerline differs')
    junction = document.find(f"./junction[@id='{JUNCTION}']")
    if junction is None:
        raise ValueError('Missing authored junction')
    links = {(int(c.attrib['incomingRoad']), int(c.attrib['connectingRoad']),
              c.attrib['contactPoint'], tuple((int(link.attrib['from']), int(link.attrib['to']))
              for link in c.findall('laneLink'))) for c in junction.findall('connection')}
    if links != {(APPROACH, 158192, 'start', ((-1, -1),)),
                 (158194, 158195, 'start', ((-1, -1),)),
                 (158196, 158195, 'end', ((1, 1),))}:
        raise ValueError('One-way/through junction lane connections differ')
    signals = roads[APPROACH].findall('./signals/signal')
    if len(signals) != 1:
        raise ValueError('Expected one authored stop sign')
    sign = signals[0]
    validity = sign.find('validity')
    if (sign.attrib.get('type') != '206' or sign.attrib.get('orientation') != '+'
            or not math.isclose(float(sign.attrib['s']), 60)
            or validity is None or (validity.attrib.get('fromLane'),
                                    validity.attrib.get('toLane')) != ('-1', '-1')):
        raise ValueError('Stop sign does not govern the selected approach lane')
    if document.findall('.//object') or len(document.findall('.//signal')) != 1:
        raise ValueError('Authored markings or other controls are present')
    return {'format': 'worker-c158190-authored-stop-site',
            'road_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'approach_road_id': APPROACH, 'approach_lane_id': -1,
            'through_road_ids': list(THROUGH), 'junction_id': JUNCTION,
            'stop_signal_id': sign.attrib['id'],
            'no_authored_stop_line_or_crosswalk_objects': True,
            'native_marking_absence_claimed': False}


def validate_native_site(world, *, location_factory=None):
    """Reject a loaded map that lacks the intended lanes or sign trigger."""
    if location_factory is None:
        import carla
        location_factory = carla.Location
    road_map = world.get_map()
    expected = ((-20, -1.8, APPROACH, -1, False),
                (0, -1.8, 158192, -1, True),
                (1.8, -20, 158194, -1, False),
                (1.8, 0, 158195, -1, True),
                (-1.8, 20, 158196, 1, False))
    for map_x, map_y, road_id, lane_id, is_junction in expected:
        x, y = opendrive_to_carla(map_x, map_y)
        point = location_factory(x=x, y=y, z=.25)
        waypoint = road_map.get_waypoint(point, project_to_road=False)
        if (waypoint is None or waypoint.road_id != road_id
                or waypoint.lane_id != lane_id
                or bool(waypoint.is_junction) != is_junction):
            raise ValueError(f'Native road/lane/junction readback differs at {(x, y)}')
    approach_x, approach_y = opendrive_to_carla(-20, -1.8)
    approach_point = location_factory(x=approach_x, y=approach_y, z=.25)
    signs = [actor for actor in world.get_actors().filter('traffic.stop*')
             if actor.trigger_volume.contains(approach_point, actor.get_transform())]
    if len(signs) != 1:
        raise ValueError(f'Expected one Native stop trigger governing approach; found {len(signs)}')
    return {'native_map_name': road_map.name, 'native_stop_sign_id': signs[0].id,
            'native_approach_road_id': APPROACH, 'native_through_road_ids': list(THROUGH),
            'native_marking_absence_claimed': False,
            'properly_erected_sign_face_claimed': False}


def load_native_site(client):
    """Explicit Native operation; never called by CPU diagnostics."""
    validate_authored_site()
    world = client.generate_opendrive_world(ROAD.read_text())
    return world, validate_native_site(world)


def _xyz(point):
    return [float(point.x), float(point.y), float(point.z)]


def observe_stop_control(world, expected_stop_id, *, frame):
    """Sample the Native control actor and crossing inventory at one frame."""
    if type(frame) is not int or world.get_snapshot().frame != frame:
        raise ValueError('Stop-control inventory frame differs from world')
    actors = list(world.get_actors())
    stops = [actor for actor in actors if actor.type_id.startswith('traffic.stop')]
    matched = [actor for actor in stops if actor.id == expected_stop_id]
    if len(matched) != 1:
        raise ValueError('Native stop sign disappeared or changed identity')
    sign = matched[0]
    transform = sign.get_transform()
    if not hasattr(sign, 'trigger_volume'):
        raise ValueError('Native stop sign lacks trigger volume')
    vertices = [_xyz(p) for p in sign.trigger_volume.get_world_vertices(transform)]
    if len(vertices) < 4:
        raise ValueError('Native stop trigger geometry incomplete')
    competing = [{'actor_id': actor.id, 'blueprint': actor.type_id,
                  'position_m': _xyz(actor.get_transform().location)}
                 for actor in actors if actor.type_id.startswith(
                     ('traffic.yield', 'traffic.traffic_light'))]
    return {'frame': frame, 'native_map_name': world.get_map().name,
            'stop_sign': {'actor_id': sign.id, 'blueprint': sign.type_id,
                          'position_m': _xyz(transform.location),
                          'trigger_vertices_m': vertices},
            'other_stop_sign_ids': [actor.id for actor in stops if actor.id != sign.id],
            'competing_controls': competing,
            'native_crosswalk_vertices_m': [_xyz(p) for p in
                                            world.get_map().get_crosswalks()],
            'sign_face_legibility': 'pending_original_source_camera_review',
            'police_direction': 'pending_original_source_review',
            'all_entrance_governance': 'pending_original_source_review'}



PREFIX = 'testing__C158190__NRS-484B-257-2__motor_vehicle_driver__'
EGO_BLUEPRINT = 'vehicle.tesla.model3'
OTHER_BLUEPRINT = 'vehicle.tesla.model3'
EGO_POINT = opendrive_to_carla(-60.0, -1.8)
OTHER_APPROACH = opendrive_to_carla(1.8, -45.0)
OTHER_INSIDE = opendrive_to_carla(1.8, -4.0)
SUPPORTED = {
    PREFIX + 'stop_other_inside',
    PREFIX + 'stop_other_approaching',
    PREFIX + 'stop_no_other',
    PREFIX + 'stop_no_halt',
}


class StopStage:
    """Engineering speed targets; actual stop and yielding require source review."""

    def __init__(self, case_id, *, hold_frames=12):
        self.plan = plan_case(case_id)
        if type(hold_frames) is not int or hold_frames < 2:
            raise ValueError('Invalid requested stop hold')
        self.hold_frames = hold_frames
        self.stopped_frames = 0
        self.released = False

    def target(self, distance_to_reference_m, observed_speed_mps, *,
               before_reference, within_intersection, other_clear):
        if any(not isinstance(v, (int, float)) or isinstance(v, bool)
               or not math.isfinite(v) or v < 0 for v in
               (distance_to_reference_m, observed_speed_mps)):
            raise ValueError('Missing finite Native speed or stop-reference distance')
        if any(type(v) is not bool for v in
               (before_reference, within_intersection, other_clear)):
            raise ValueError('Missing Native road/crossing state')
        if self.plan['rolling_response_requested']:
            return 4.0 if distance_to_reference_m <= 18 else 8.0
        if within_intersection:
            return 5.0
        if self.released:
            return 5.0
        if before_reference and distance_to_reference_m <= 3.0:
            if observed_speed_mps <= .05:
                self.stopped_frames += 1
            else:
                self.stopped_frames = 0
            if self.stopped_frames >= self.hold_frames and other_clear:
                self.released = True
                return 5.0
            return 0.0
        if not before_reference:
            raise ValueError('Ego crossed stop reference without staged halt')
        return 3.0 if distance_to_reference_m <= 18 else 8.0


def plan_case(case_id):
    if case_id not in SUPPORTED:
        raise ValueError('Case needs a different control construction: ' + case_id)
    suffix = case_id.removeprefix(PREFIX)
    other_point = (None if suffix == 'stop_no_other' else
                   OTHER_INSIDE if suffix == 'stop_other_inside' else OTHER_APPROACH)
    return {'case_id': case_id, 'ego_point_xy_m': EGO_POINT,
            'other_point_xy_m': other_point,
            'other_start_road_id': None if other_point is None else
            158195 if suffix == 'stop_other_inside' else 158194,
            'rolling_response_requested': suffix == 'stop_no_halt'}


def _waypoint(world, location, road_id, lane_id):
    waypoint = world.get_map().get_waypoint(location, project_to_road=False)
    if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (road_id, lane_id):
        raise ValueError('Selected spawn point is not on the authored lane')
    return waypoint


def _spawn(world, blueprint_id, waypoint, road_id, lane_id):
    blueprint = world.get_blueprint_library().find(blueprint_id)
    if blueprint is None:
        raise ValueError('Missing Native motor-vehicle blueprint: ' + blueprint_id)
    actor = world.try_spawn_actor(blueprint, waypoint.transform)
    if actor is None:
        raise ValueError('Native actor could not spawn at selected point')
    try:
        actual = _waypoint(world, actor.get_location(), road_id, lane_id)
        if actor.type_id != blueprint_id or actual.is_junction != waypoint.is_junction:
            raise ValueError('Native actor identity or junction location differs')
    except BaseException:
        actor.destroy()
        raise
    return actor


@contextmanager
def stage_case(world, case_id, *, location_factory=None):
    """Read back the map and stage exactly the selected participants."""
    if location_factory is None:
        import carla
        location_factory = carla.Location
    plan = plan_case(case_id)
    site = validate_native_site(world, location_factory=location_factory)
    owned = []
    try:
        x, y = plan['ego_point_xy_m']
        ego_location = location_factory(x=x, y=y, z=.25)
        ego = _spawn(world, EGO_BLUEPRINT,
                     _waypoint(world, ego_location, 158190, -1), 158190, -1)
        owned.append(ego)
        other = None
        if plan['other_point_xy_m'] is not None:
            x, y = plan['other_point_xy_m']
            road_id = plan['other_start_road_id']
            other_location = location_factory(x=x, y=y, z=.25)
            other = _spawn(world, OTHER_BLUEPRINT,
                           _waypoint(world, other_location, road_id, -1), road_id, -1)
            owned.append(other)
            if other.id == ego.id:
                raise ValueError('Native actor identity reused for both roles')
        yield {'ego': ego, 'other': other, 'site': site, 'plan': plan}
    finally:
        for actor in reversed(owned):
            actor.destroy()



CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SIZES = {'overview': (1920, 1080), 'approach': (1280, 720),
         'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}
STOP_REFERENCE_X = -11.0  # Authored engineering target; legal reference needs review.
JUNCTION_BOUNDS = (-8.0, 8.0, -8.0, 8.0)


def validate_config(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-257-2', 'C158190', 'motor_vehicle_driver'):
        raise ValueError('Wrong C158190 stop-sign identity')
    case_id = config.get('selected_case_id')
    plan_case(case_id)
    if case_id not in config.get('supported_case_ids', ()):
        raise ValueError('Selected case absent from full case plan')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 30:
        raise ValueError('Stop-sign capture needs 20 Hz and 30 seconds')
    cameras = config.get('cameras')
    if not isinstance(cameras, list) or [c.get('name') for c in cameras] != list(CAMERAS):
        raise ValueError('Four named source cameras required')
    if any((c.get('width'), c.get('height')) != SIZES[c['name']]
           or c.get('fov_deg') != 90 for c in cameras):
        raise ValueError('Source camera profile differs')
    if 'dev.stop_sign' not in config.get('required_atoms', ()):
        raise ValueError('Stop-sign atom omitted')
    validate_authored_site()
    return config


def camera_transforms(carla):
    def pose(x, y, z, yaw, pitch):
        return carla.Transform(carla.Location(x=x, y=y, z=z),
                               carla.Rotation(yaw=yaw, pitch=pitch))
    return {'overview': pose(-15, 0, 48, 0, -85),
            'approach': pose(-38, -16, 9, 30, -13),
            'reference_corner': pose(19, -25, 15, 135, -24),
            'driver_reference': pose(1.0, 0, 1.6, 0, -5)}


@contextmanager
def source_cameras(world, ego, transforms):
    if set(transforms) != set(CAMERAS):
        raise ValueError('All four source camera poses required')
    sensors = {}
    try:
        for name in CAMERAS:
            width, height = SIZES[name]
            blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 90), ('sensor_tick', .05)):
                blueprint.set_attribute(key, str(value))
            kwargs = {'attach_to': ego} if name == 'driver_reference' else {}
            sensor = world.spawn_actor(blueprint, transforms[name], **kwargs)
            if sensor is None:
                raise ValueError('Native source camera spawn failed: ' + name)
            sensors[name] = sensor
        yield sensors
    finally:
        for sensor in reversed(list(sensors.values())):
            sensor.stop()
            sensor.destroy()


class FFV1Writer:
    def __init__(self, path, width, height):
        self.path, self.width, self.height = Path(path), width, height
        if self.path.exists():
            raise ValueError('Fresh source-camera path required')
        self.frames = 0
        self.exit_code = None
        self.process = subprocess.Popen([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-n',
            '-f', 'rawvideo', '-pixel_format', 'bgra',
            '-video_size', f'{width}x{height}', '-framerate', '20',
            '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '3',
            '-pix_fmt', 'bgr0', str(self.path)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def write(self, data):
        if not isinstance(data, bytes) or len(data) != self.width * self.height * 4:
            raise ValueError('Original BGRA source frame size differs')
        if self.process.poll() is not None:
            raise ValueError('Source encoder exited before capture completed')
        self.process.stdin.write(data)
        self.frames += 1

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        self.exit_code = self.process.wait(timeout=60)
        detail = self.process.stderr.read().decode(errors='replace')
        self.process.stderr.close()
        if self.exit_code != 0 or self.frames == 0 or not self.path.is_file():
            raise ValueError('Source encoder failed: ' + detail[-1000:])

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def sensor_frame(queue, expected):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError('Missing original camera frame ' + str(expected)) from error
        if image.frame == expected:
            return image
        if image.frame > expected:
            raise ValueError('Source camera skipped frame ' + str(expected))
    raise ValueError('Source camera frame join failed')


def _speed(actor):
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
    if not math.isfinite(speed):
        raise ValueError('Original actor velocity is nonfinite')
    return speed


def _body_vertices(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) < 8:
        raise ValueError('Original actor body vertices incomplete')
    return vertices


def _intersects_junction(vertices):
    left, right, bottom, top = JUNCTION_BOUNDS
    return (min(p.x for p in vertices) <= right
            and max(p.x for p in vertices) >= left
            and min(p.y for p in vertices) <= top
            and max(p.y for p in vertices) >= bottom)


def _control(target, observed):
    delta = .25 * (target - observed)
    return {'throttle': min(1.0, max(0.0, delta)),
            'brake': min(1.0, max(0.0, -delta))}


def apply_motion(world, staging, stage, carla):
    ego, other = staging['ego'], staging['other']
    point = ego.get_location()
    waypoint = world.get_map().get_waypoint(point, project_to_road=False)
    if waypoint is None or waypoint.road_id not in (158190, 158192, 158193):
        raise ValueError('Ego left authored approach and crossing route')
    front_x = max(p.x for p in _body_vertices(ego))
    before_reference = front_x < STOP_REFERENCE_X
    other_clear = other is None or (
        not _intersects_junction(_body_vertices(other)) and other.get_location().y < -12)
    target = stage.target(max(0.0, STOP_REFERENCE_X - front_x), _speed(ego),
                          before_reference=before_reference,
                          within_intersection=waypoint.road_id != 158190,
                          other_clear=other_clear)
    if point.x >= 55:
        target = 0.0
    ego.apply_control(carla.VehicleControl(**_control(target, _speed(ego))))
    if other is not None:
        other_target = 0.0 if other.get_location().y <= -50 else 7.0
        other.apply_control(carla.VehicleControl(**_control(other_target, _speed(other))))
    return {'ego_target_mps': target, 'other_clear_by_engineering_position': other_clear,
            'stop_stage_released': stage.released}


def source_row(world, staging, frame, time_s, video_frame):
    ego, other = staging['ego'], staging['other']
    ego_body = _body_vertices(ego)
    ego_waypoint = world.get_map().get_waypoint(ego.get_location(), project_to_road=False)
    if ego_waypoint is None:
        raise ValueError('Original ego road identity missing')
    other_body = [] if other is None else _body_vertices(other)
    return {'frame': frame, 'time_s': float(time_s), 'video_frame': video_frame,
            'ego_road_id': ego_waypoint.road_id,
            'ego': {'body_vertices_m': [_xyz(p) for p in ego_body]},
            'ego_speed_source': 'actor.get_velocity', 'ego_speed_mps': _speed(ego),
            'ego_body_before_stop_reference': max(p.x for p in ego_body) < STOP_REFERENCE_X,
            'ego_body_in_intersection': _intersects_junction(ego_body),
            'other_body_in_intersection': bool(other_body) and _intersects_junction(other_body),
            'other_actor_id': None if other is None else other.id,
            'other_body_vertices_m': None if other is None else
            [_xyz(p) for p in other_body],
            'other_speed_mps': None if other is None else _speed(other),
            'other_center_m': None if other is None else
            [other.get_location().x, other.get_location().y, other.get_location().z],
            'occupancy_source': 'Native_actor_bounding_box_vertices_and_authored_junction_bounds'}


def capture(args, config):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / 'construction.json').is_file():
        raise ValueError('Use runtime.py capture to materialize exact construction')
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = snapshot(client)
    encoders = {}
    helper = None
    frames = 0
    succeeded = False
    try:
        world, site = load_native_site(client)
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        with stage_case(world, config['selected_case_id']) as staging:
            stage = StopStage(config['selected_case_id'])
            context = {'native_map_id': world.get_map().name,
                       'intersection_id': 158191, 'ego_approach_road_id': 158190,
                       'ego_route_road_ids': [158190, 158192, 158193],
                       'native_stop_sign_id': site['native_stop_sign_id'],
                       'sign_governance_source': 'Native_stop_trigger_and_authored_OpenDRIVE',
                       'entrance_inventory_source': 'Native_control_inventory_and_camera_review_pending',
                       'stop_reference_source': 'authored_junction_boundary_and_camera_review_pending',
                       'highway_status_source': 'authored_site_and_map_review_pending',
                       'non_through_highway': None, 'police_control': None,
                       'traffic_signal_control': None, 'ego_entrance_device': 'stop',
                       'entrances': [{'road_id': 158190, 'device': 'stop'},
                                     {'road_id': 158194, 'device': 'unreviewed'},
                                     {'road_id': 158196, 'device': 'unreviewed'}]}
            (output / 'intersection_context.json').write_text(json.dumps(context, indent=2) + '\n')
            with source_cameras(world, staging['ego'], camera_transforms(carla)) as cameras:
                queues = {name: Queue() for name in CAMERAS}
                for name, sensor in cameras.items():
                    sensor.listen(lambda image, name=name: queues[name].put(image))
                with ExitStack() as stack:
                    for name in CAMERAS:
                        width, height = SIZES[name]
                        encoders[name] = stack.enter_context(
                            FFV1Writer(output / (name + '.mkv'), width, height))
                    helper = PipelineCapture(client, staging['ego'], output,
                                             config['selected_case_id'],
                                             required_observations=config['required_atoms'])
                    try:
                        with (output / 'entry_history.jsonl').open('x') as history, \
                             (output / 'video_frames.jsonl').open('x') as frame_map, \
                             (output / 'stop_control_inventory.jsonl').open('x') as controls:
                            for index in range(config['rate_hz'] * config['duration_s']):
                                command = apply_motion(world, staging, stage, carla)
                                world.tick()
                                snap = world.get_snapshot()
                                for name in CAMERAS:
                                    image = sensor_frame(queues[name], snap.frame)
                                    encoders[name].write(bytes(image.raw_data))
                                helper.capture(snap.frame, snap.timestamp.elapsed_seconds,
                                               extra={'stop_construction_control': command})
                                controls.write(json.dumps(observe_stop_control(
                                    world, site['native_stop_sign_id'], frame=snap.frame),
                                    sort_keys=True) + '\n')
                                row = source_row(world, staging, snap.frame,
                                                 snap.timestamp.elapsed_seconds, index)
                                history.write(json.dumps(row, sort_keys=True) + '\n')
                                frame_map.write(json.dumps({
                                    'video_frame': index, 'carla_frame': snap.frame,
                                    'time_s': snap.timestamp.elapsed_seconds},
                                    sort_keys=True) + '\n')
                                frames += 1
                        succeeded = True
                    finally:
                        helper.close(confirmed=succeeded)
                        helper = None
    finally:
        if helper is not None:
            helper.close(confirmed=False)
        restoration = restore(client, saved)
    if succeeded:
        seal_capture(output, frames=frames, restoration=restoration, errors=[],
                     encoder_exit_codes={name: encoders[name].exit_code for name in CAMERAS},
                     context={'selected_case_id': config['selected_case_id'],
                              'sign_face_and_entrance_review_pending': True,
                              'stop_and_hazard_legal_review_pending': True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    config = validate_config(json.loads(Path('config.json').read_text()))
    if args.check:
        print(json.dumps({'case_id': config['selected_case_id'],
                          'cpu_config_checked': True, 'simulation_started': False}))
        return
    if not args.output_dir:
        raise ValueError('Native capture requires --output-dir')
    capture(args, config)


if __name__ == '__main__':
    main()
