"""Native map and signal binding for the left-arrow crosswalk pair.

CARLA import and capture are deliberately separate. All geometry and source
requirements here can be exercised with a small fake world on a CPU host.
"""
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from runner import control, turn_route


def _distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def connected_turn(start, exit_waypoint, limit=1200):
    target = exit_waypoint.transform.location
    queue = [start]
    visited = set()
    index = 0
    while index < len(queue) and index < limit:
        waypoint = queue[index]
        index += 1
        point = waypoint.transform.location
        identity = (getattr(waypoint, 'road_id', None), getattr(waypoint, 'lane_id', None),
                    round(point.x, 1), round(point.y, 1))
        if identity in visited:
            continue
        visited.add(identity)
        if _distance(point, target) <= 2.5:
            return True
        queue.extend(waypoint.next(2.0))
    return False


def bind_map(world, carla, scene):
    mapping = world.get_map()
    route = turn_route(scene)
    waypoints = []
    for x, y in route:
        target = carla.Location(x=x, y=y, z=0)
        waypoint = mapping.get_waypoint(target)
        if waypoint is None or _distance(waypoint.transform.location, target) > 2:
            raise ValueError('authored left-turn route absent from original Native map')
        waypoints.append(waypoint)
    if not (connected_turn(waypoints[0], waypoints[2]) and
            connected_turn(waypoints[2], waypoints[-1])):
        raise ValueError('original Native map lacks a connected left turn')
    crosswalk_points = mapping.get_crosswalks()
    if not crosswalk_points:
        raise ValueError('original Native map contains no marked adjacent crosswalk')
    left, bottom, right, top = scene['adjacent_crosswalk_bounds_m']
    nearby = [point for point in crosswalk_points
              if left - 2 <= point.x <= right + 2 and bottom - 2 <= point.y <= top + 2]
    if len(nearby) < 4:
        raise ValueError('original marked crosswalk does not match authored adjacent geometry')
    other_route = None
    if scene.get('other_traffic_setup') == 'lawful_entered':
        other_points = []
        for x, y in (scene['other_vehicle_entry_start_xy_m'],
                     scene['other_vehicle_conflict_xy_m'],
                     scene['other_vehicle_end_xy_m']):
            target = carla.Location(x=x, y=y, z=0)
            waypoint = mapping.get_waypoint(target)
            if waypoint is None or _distance(waypoint.transform.location, target) > 2:
                raise ValueError('original lawful other-vehicle lane absent')
            other_points.append(waypoint)
        if not (connected_turn(other_points[0], other_points[1]) and
                connected_turn(other_points[1], other_points[2])):
            raise ValueError('original lawful other-vehicle route is not connected')
        other_route = [{'x_m': wp.transform.location.x, 'y_m': wp.transform.location.y,
                        'road_id': wp.road_id, 'lane_id': wp.lane_id}
                       for wp in other_points]
    return {'map_source': mapping.name,
            'ego_route_source': 'Native CARLA connected waypoints',
            'adjacent_crosswalk_source': 'Native CARLA map crosswalk vertices',
            'adjacent_crosswalk_bounds_m': scene['adjacent_crosswalk_bounds_m'],
            'route_waypoints': [{'x_m': wp.transform.location.x, 'y_m': wp.transform.location.y,
                                 'road_id': wp.road_id, 'lane_id': wp.lane_id}
                                for wp in waypoints],
            'crosswalk_vertices_m': [[point.x, point.y, point.z] for point in nearby],
            'other_vehicle_route_waypoints': other_route}


def bind_facing_arrow(ego, scene):
    """Require original signal asset metadata; CARLA Green alone is insufficient."""
    light = ego.get_traffic_light()
    if light is None or light.id != scene['facing_head_id']:
        raise ValueError('authored signal is not the original ego-facing traffic light')
    attributes = light.attributes
    if (attributes.get('signal_shape') != 'arrow' or
            attributes.get('arrow_direction') != scene['arrow_direction'] or
            attributes.get('sole_illuminated') != 'true'):
        raise ValueError('original signal asset does not establish sole left arrow')
    return light


def observed_arrow(light, scene, frame):
    state = str(light.get_state()).split('.')[-1].lower()
    if state != 'green':
        raise ValueError('original ego-facing left arrow is not green in this frame')
    return {'source_verified': True,
            'source_ref': f'Native CARLA traffic light {light.id} asset attributes and state',
            'head_id': light.id, 'observed_frame': frame,
            'illuminated_indications': [{'color': 'green', 'shape': 'arrow',
                                         'direction': scene['arrow_direction']}]}


def bind_pedestrian_walk(world, scene):
    """Require an official original Walk indication before staged crosswalk entry."""
    head = world.get_actor(scene['pedestrian_signal_head_id'])
    if head is None or head.attributes.get('official_pedestrian_signal') != 'true':
        raise ValueError('original official pedestrian signal missing')
    if str(head.get_state()).split('.')[-1].lower() != 'walk':
        raise ValueError('original pedestrian Walk indication absent at entry')
    return head


def bind_other_vehicle_green(world, scene):
    """Require the original official green head governing the other vehicle's entry."""
    head = world.get_actor(scene['other_vehicle_signal_head_id'])
    if head is None or head.attributes.get('official_traffic_signal') != 'true':
        raise ValueError('original official other-vehicle signal missing')
    if str(head.get_state()).split('.')[-1].lower() != 'green':
        raise ValueError('original other-vehicle green entry indication absent')
    return head


def other_vehicle_station(scene, index, entry=False):
    if type(index) is not int or index < 0:
        raise ValueError('invalid other-vehicle motion step')
    start = (scene['other_vehicle_entry_start_xy_m'] if entry else
             scene['other_vehicle_conflict_xy_m'])
    end = scene['other_vehicle_conflict_xy_m'] if entry else scene['other_vehicle_end_xy_m']
    y = min(end[1], start[1] + (index + 1) *
            scene['other_vehicle_target_speed_mps'] / scene['rate_hz'])
    return start[0], y


def pedestrian_station(scene, index, entry=False):
    """Bounded authored position for staged entry or crosswalk clearance."""
    if type(index) is not int or index < 0:
        raise ValueError('invalid pedestrian motion step')
    start = (scene['pedestrian_entry_start_xy_m'] if entry else
             scene['pedestrian_start_xy_m'])
    end = scene['pedestrian_start_xy_m'] if entry else scene['pedestrian_end_xy_m']
    x = min(end[0], start[0] + (index + 1) * scene['pedestrian_target_speed_mps'] /
            scene['rate_hz'])
    return x, start[1]


def spawn_entities(world, scene, vehicle_bp, person_bp, transform):
    """Create distinct ego and pedestrian and destroy partial creations on failure."""
    actors = []
    try:
        ego = world.spawn_actor(vehicle_bp, transform(*scene['ego_start_xy_m'], 0))
        actors.append(ego)
        if scene['crosswalk_setup'] == 'occupied':
            person = world.spawn_actor(person_bp, transform(*scene['pedestrian_entry_start_xy_m'], 0))
            actors.append(person)
        if scene.get('other_traffic_setup') == 'lawful_entered':
            other = world.spawn_actor(vehicle_bp, transform(*scene['other_vehicle_entry_start_xy_m'], 90))
            actors.append(other)
        if any(actor is None for actor in actors) or len({a.id for a in actors}) != len(actors):
            raise ValueError('Native ego and pedestrian identities are not distinct')
        return actors
    except BaseException:
        for actor in reversed(actors):
            if actor is not None:
                actor.destroy()
        raise


def _vertices(actor):
    return [[point.x, point.y, point.z]
            for point in actor.bounding_box.get_world_vertices(actor.get_transform())]


def _speed(actor):
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


class Cameras:
    SPECS = (('overview', 1920, 1080, (0, 0, 45, -90)),
             ('approach', 1280, 720, (-15, -12, 12, -25)),
             ('reference_corner', 1280, 720, (4, 4, 12, -45)),
             ('driver_reference', 1280, 720, (0, 0, 2, 0)))

    def __init__(self, world, ego, output, carla):
        self.sensors = []
        self.encoders = {}
        self.queues = {}
        self.errors = []
        try:
            for name, width, height, pose in self.SPECS:
                bp = world.get_blueprint_library().find('sensor.camera.rgb')
                bp.set_attribute('image_size_x', str(width))
                bp.set_attribute('image_size_y', str(height))
                bp.set_attribute('fov', '90')
                x, y, z, pitch = pose
                transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                            carla.Rotation(pitch=pitch))
                sensor = world.spawn_actor(bp, transform,
                    attach_to=ego if name == 'driver_reference' else None)
                self.sensors.append(sensor)
                frames = queue.Queue(maxsize=4)
                self.queues[name] = frames
                def receive(image, destination=frames, label=name):
                    try:
                        destination.put_nowait(image)
                    except queue.Full:
                        self.errors.append('camera queue overflow: ' + label)
                sensor.listen(receive)
                command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                           '-n', '-f', 'rawvideo', '-pixel_format', 'bgra',
                           '-video_size', f'{width}x{height}', '-framerate', '20',
                           '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgra',
                           str(output / (name + '.mkv'))]
                self.encoders[name] = subprocess.Popen(command, stdin=subprocess.PIPE,
                                                        stderr=subprocess.DEVNULL)
        except BaseException:
            self.close()
            raise

    def append(self, frame):
        if self.errors:
            raise RuntimeError('; '.join(self.errors))
        for name, _, _, _ in self.SPECS:
            image = self.queues[name].get(timeout=15)
            if image.frame != frame:
                raise RuntimeError('camera/world frame mismatch: ' + name)
            self.encoders[name].stdin.write(image.raw_data)

    def close(self):
        for sensor in reversed(self.sensors):
            sensor.stop()
        for name, process in self.encoders.items():
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if process.wait(timeout=180) != 0:
                raise RuntimeError('camera encoder failed: ' + name)
        for sensor in reversed(self.sensors):
            sensor.destroy()


def run_native(scene, output, host, port):
    """Capture original frames only after a sourced Walk entry and sole arrow."""
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import fields, equal

    output = Path(output).resolve()
    if not output.is_dir():
        raise ValueError('Native attempt directory must already exist')
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    original = world.get_settings()
    actors = []
    cameras = capture = frame_map = None
    rows = []
    errors = []
    phase = 'initializing'
    restored = False
    context = None
    try:
        context = bind_map(world, carla, scene)
        library = world.get_blueprint_library()
        vehicles = list(library.filter('vehicle.*'))
        people = list(library.filter('walker.pedestrian.*'))
        if not vehicles or (scene['crosswalk_setup'] == 'occupied' and not people):
            raise ValueError('Native vehicle or pedestrian blueprint absent')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / scene['rate_hz']
        world.apply_settings(settings)

        def transform(x, y, yaw=0):
            waypoint = world.get_map().get_waypoint(carla.Location(x=x, y=y, z=0))
            z = waypoint.transform.location.z + .5 if waypoint else .5
            return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw))

        actors = spawn_entities(world, scene, vehicles[0], people[0] if people else None,
                                transform)
        ego = actors[0]
        person = actors[1] if scene['crosswalk_setup'] == 'occupied' else None
        other = actors[-1] if scene.get('other_traffic_setup') == 'lawful_entered' else None
        arrow = bind_facing_arrow(ego, scene)
        context.update({'facing_head_id': arrow.id,
                        'facing_head_source': f'Native CARLA traffic light {arrow.id}',
                        'camera_profile': 'overview1080-capability',
                        'duration_s': scene['duration_s'],
                        'lawful_presence_method': 'original pedestrian Walk entry and marked crosswalk' if person else 'no pedestrian',
                        'other_vehicle_lawfulness_method': 'original green entry and connected Native route' if other else 'no other traffic'})
        if person:
            head = bind_pedestrian_walk(world, scene)
            entry_steps = math.ceil((scene['pedestrian_start_xy_m'][0] -
                                     scene['pedestrian_entry_start_xy_m'][0]) *
                                    scene['rate_hz'] / scene['pedestrian_target_speed_mps'])
            entry_rows = []
            for index in range(entry_steps):
                bind_pedestrian_walk(world, scene)
                x, y = pedestrian_station(scene, index, entry=True)
                person.set_transform(transform(x, y, 0))
                frame = world.tick()
                snapshot = world.get_snapshot()
                if frame != snapshot.frame:
                    raise RuntimeError('pedestrian entry frame mismatch')
                entry_rows.append({'frame': frame, 'time_s': snapshot.timestamp.elapsed_seconds,
                                   'pedestrian_signal_head_id': head.id,
                                   'walk_state': str(head.get_state()),
                                   'person_body_vertices_m': _vertices(person)})
            with (output / 'pedestrian-entry.jsonl').open('x') as stream:
                for row in entry_rows:
                    stream.write(json.dumps(row, allow_nan=False) + '\n')
            context['pedestrian_entry_source'] = 'pedestrian-entry.jsonl'
        else:
            context['pedestrian_entry_source'] = None
        if other:
            head = bind_other_vehicle_green(world, scene)
            entry_steps = math.ceil((scene['other_vehicle_conflict_xy_m'][1] -
                                     scene['other_vehicle_entry_start_xy_m'][1]) *
                                    scene['rate_hz'] / scene['other_vehicle_target_speed_mps'])
            entry_rows = []
            for index in range(entry_steps):
                bind_other_vehicle_green(world, scene)
                x, y = other_vehicle_station(scene, index, entry=True)
                other.set_transform(transform(x, y, 90))
                frame = world.tick()
                snapshot = world.get_snapshot()
                if frame != snapshot.frame:
                    raise RuntimeError('other-vehicle entry frame mismatch')
                entry_rows.append({'frame': frame,
                    'time_s': snapshot.timestamp.elapsed_seconds,
                    'other_vehicle_signal_head_id': head.id,
                    'green_state': str(head.get_state()),
                    'vehicle_body_vertices_m': _vertices(other),
                    'route_source': 'Native CARLA connected waypoints'})
            with (output / 'traffic-entry.jsonl').open('x') as stream:
                for row in entry_rows:
                    stream.write(json.dumps(row, allow_nan=False) + '\n')
            context['other_vehicle_entry_source'] = 'traffic-entry.jsonl'
            context['other_vehicle_signal_head_id'] = head.id
        else:
            context['other_vehicle_entry_source'] = None
        _write(output / 'intersection-context.json', context)
        _write(output / 'acquisition-provenance.json', {
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'method': 'original CARLA live run'})
        cameras = Cameras(world, ego, output, carla)
        capture = PipelineCapture(client, ego, output, scene['case_id'])
        frame_map = FrameMap(output / 'video_frames.jsonl')
        phase = 'capturing'
        with (output / 'turn-history.jsonl').open('x', buffering=1) as stream:
            for index in range(round(scene['duration_s'] * scene['rate_hz'])):
                frame_before = world.get_snapshot().frame
                signal = observed_arrow(arrow, scene, frame_before)
                ego_body = _vertices(ego)
                pedestrians = []
                if person:
                    pedestrians = [{'id': person.id, 'role': 'pedestrian',
                        'source_ref': f'Native CARLA walker {person.id}',
                        'lawful_presence_source': 'pedestrian-entry.jsonl and original Walk head',
                        'lawfully_present': True, 'body_vertices_m': _vertices(person)}]
                heading = ego.get_transform().rotation.yaw
                traffic = []
                if other and other.get_transform().location.y < scene['adjacent_crosswalk_bounds_m'][1]:
                    traffic = [{'id': other.id, 'role': 'motor_vehicle',
                        'source_ref': f'Native CARLA vehicle {other.id}',
                        'lawful_presence_source': 'traffic-entry.jsonl and original green head',
                        'lawfully_using_intersection': True,
                        'body_vertices_m': _vertices(other)}]
                command = control(scene, signal, frame_before, ego_body, pedestrians, traffic, heading)
                ego.apply_control(carla.VehicleControl(throttle=command['throttle'],
                                   brake=command['brake'], steer=command['steer']))
                if person:
                    x, y = pedestrian_station(scene, index)
                    person.set_transform(transform(x, y, 0))
                if other:
                    x, y = other_vehicle_station(scene, index)
                    other.set_transform(transform(x, y, 90))
                frame = world.tick()
                snapshot = world.get_snapshot()
                if frame != snapshot.frame:
                    raise RuntimeError('original world frame mismatch')
                time_s = snapshot.timestamp.elapsed_seconds
                signal = observed_arrow(arrow, scene, frame)
                capture.capture(frame, time_s)
                cameras.append(frame)
                frame_map.append(frame, time_s)
                pedestrians = [] if not person else [{
                    'id': person.id, 'role': 'pedestrian',
                    'source_ref': f'Native CARLA walker {person.id}',
                    'lawful_presence_source': 'pedestrian-entry.jsonl and original Walk head',
                    'lawfully_present': True, 'body_vertices_m': _vertices(person)}]
                traffic = []
                if other and other.get_transform().location.y < scene['adjacent_crosswalk_bounds_m'][1]:
                    traffic = [{'id': other.id, 'role': 'motor_vehicle',
                        'source_ref': f'Native CARLA vehicle {other.id}',
                        'lawful_presence_source': 'traffic-entry.jsonl and original green head',
                        'lawfully_using_intersection': True,
                        'body_vertices_m': _vertices(other)}]
                row = {'frame': frame, 'time_s': time_s, 'facing_signal': signal,
                       'ego': {'source_ref': f'Native CARLA vehicle {ego.id}',
                               'heading_source': 'Native CARLA transform',
                               'heading_deg': ego.get_transform().rotation.yaw,
                               'body_vertices_m': _vertices(ego), 'speed_mps': _speed(ego),
                               'brake': command['brake']},
                       'pedestrians': pedestrians, 'other_traffic': traffic}
                stream.write(json.dumps(row, allow_nan=False) + '\n')
                rows.append(row)
        phase = 'closing'
        capture.close(); capture = None
        frame_map.close(); frame_map = None
        cameras.close(); cameras = None
        names = ['trace.jsonl', 'video_frames.jsonl', 'turn-history.jsonl',
                 'intersection-context.json', 'road.xodr', 'carla_recorder.log',
                 *[name + '.mkv' for name, *_ in Cameras.SPECS]]
        if person:
            names.append('pedestrian-entry.jsonl')
        if other:
            names.append('traffic-entry.jsonl')
        _write(output / 'acquisition.json', {name: {
            'kind': 'original_native',
            'sha256': hashlib.sha256((output / name).read_bytes()).hexdigest()}
            for name in names})
        phase = 'sealed'
    except BaseException as error:
        errors.append(repr(error))
        raise
    finally:
        for resource in (capture, frame_map, cameras):
            if resource:
                try:
                    resource.close()
                except BaseException as error:
                    errors.append(repr(error))
        for actor in reversed(actors):
            try:
                actor.destroy()
            except BaseException as error:
                errors.append(repr(error))
        try:
            world.apply_settings(original)
            restored = all(equal(fields(world.get_settings()).get(key), value)
                           for key, value in fields(original).items())
        except BaseException as error:
            errors.append(repr(error))
        if phase == 'sealed' and not errors and restored:
            seal_capture(output, frames=len(rows),
                         restoration={'restored': True,
                                      'settings_readback': 'synchronous mode and fixed delta restored'},
                         errors=[], encoder_exit_codes={name: 0 for name, *_ in Cameras.SPECS},
                         context={'turn_arrow_crosswalk': context})
        else:
            _write(output / 'native-run-status.json', {
                'phase': phase, 'errors': errors, 'settings_restored': restored})
            if phase == 'sealed':
                raise RuntimeError('Native cleanup or restoration failed')
