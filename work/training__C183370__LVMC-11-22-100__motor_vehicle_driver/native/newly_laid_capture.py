"""Original CARLA source acquisition for C183370 newly laid surface drafts.

This retains source data only. A separate finalizer must verify the crossing,
warning act, pavement status, exceptions and actual source-camera evidence.
"""
import argparse
import copy
import hashlib
import json
import queue
import subprocess
import sys
from math import atan2, degrees, hypot
from pathlib import Path

from newly_laid_plan import bind
from pathing import repository_root
from newly_laid_recording_contract import CASES, config as recording_config
from route_control import RouteControl

CAMERAS = (
    ('overview', 1920, 1080, 85, (-8.0, 0.0, 24.0), -55.0),
    ('approach', 1280, 720, 90, (-18.0, 0.0, 3.0), -6.0),
    ('reference_corner', 1280, 720, 90, (4.0, 5.0, 3.0), -15.0),
    ('driver_reference', 1280, 720, 90, (0.2, -0.35, 1.6), -4.0),
)


def prepare_attempt(attempt, repo, case, frames, *, materialized=False):
    attempt = Path(attempt).resolve()
    generated = (Path(repo)/'.runtime-work').resolve()
    if not attempt.is_relative_to(generated):
        raise ValueError('Native attempt must stay under .runtime-work')
    if materialized:
        if not attempt.is_dir():
            raise ValueError('Selected Native bundle was not materialized')
        construction = attempt/'construction.json'
        selection = attempt/'candidate-selection.json'
        config_path = attempt/'config.json'
        if not all(path.is_file() for path in (construction,selection,config_path)):
            raise ValueError('Selected Native bundle files missing')
        selected = json.loads(selection.read_text())
        config = json.loads(config_path.read_text())
        digest = hashlib.sha256(construction.read_bytes()).hexdigest()
        if (selected.get('case_id') != config.get('case_id') or
                selected.get('case_id') != recording_config(case,frames)['case_id'] or
                selected.get('construction_sha256') != digest or
                config.get('frames') != frames or
                config.get('recording_description') != recording_config(case,frames)['recording_description']):
            raise ValueError('Selected Native construction/config differs')
        for name in ('capture-receipt.json','native-actors.jsonl',
                     'video_frames.jsonl','trace.jsonl'):
            if (attempt/name).exists():
                raise ValueError('Preserve prior Native capture; use a fresh attempt')
    else:
        if attempt.exists():
            raise ValueError('Use a fresh Native attempt under .runtime-work')
        attempt.mkdir(parents=True)
        config_path=attempt/'config.json'
        config_path.write_text(json.dumps(recording_config(case,frames),indent=2)+'\n')
    return attempt


class FFV1Sink:
    def __init__(self, path, width, height):
        self.path = Path(path)
        self.size = width*height*4
        self.errors = self.path.with_suffix('.ffmpeg.log').open('xb')
        self.process = subprocess.Popen([
            'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
            '-f', 'rawvideo', '-pixel_format', 'bgra', '-video_size',
            f'{width}x{height}', '-framerate', '20', '-i', 'pipe:0',
            '-an', '-c:v', 'ffv1', '-threads', '1', str(self.path)],
            stdin=subprocess.PIPE, stderr=self.errors)
        self.count = 0

    def write(self, image):
        data = bytes(image.raw_data)
        if len(data) != self.size:
            raise ValueError('Original camera frame has wrong dimensions')
        self.process.stdin.write(data)
        self.count += 1

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        code = self.process.wait(timeout=60)
        self.errors.close()
        if code:
            raise ValueError('FFV1 source encoding failed: '+str(self.path))


def sample(world, carla, ego, person, command):
    if person is None:
        raise ValueError('Original warning person disappeared')
    transform = ego.get_transform()
    location = transform.location
    velocity = ego.get_velocity()
    body = ego.bounding_box.get_world_vertices(transform)
    if len(body) != 8:
        raise ValueError('Original vehicle body needs eight vertices')
    waypoint = world.get_map().get_waypoint(
        location, project_to_road=False, lane_type=carla.LaneType.Any)
    if waypoint is None:
        raise ValueError('Original vehicle left mapped pavement')
    if waypoint.lane_type not in (carla.LaneType.Driving,
                                  carla.LaneType.Shoulder):
        raise ValueError('Original vehicle left drivable pavement')
    person_transform = person.get_transform()
    person_location = person_transform.location
    return {
        'source_kind': 'original_carla_actor_and_map_readback',
        'ego_actor_id': ego.id, 'ego_type_id': ego.type_id,
        'ego_position_xyz_m': [location.x, location.y, location.z],
        'ego_yaw_deg': transform.rotation.yaw,
        'ego_velocity_xyz_mps': [velocity.x, velocity.y, velocity.z],
        'ego_speed_mps': hypot(hypot(velocity.x, velocity.y), velocity.z),
        'ego_body_vertices_xyz_m': [[v.x, v.y, v.z] for v in body],
        'ego_road_id': waypoint.road_id, 'ego_lane_id': waypoint.lane_id,
        'ego_lane_type': str(waypoint.lane_type),
        'warning_person_actor_id': person.id,
        'warning_person_type_id': person.type_id,
        'warning_person_xyz_m': [person_location.x, person_location.y,
                                 person_location.z],
        'requested_control': command,
        'warning_act_verified': False,
        'physical_completion_claimed': False,
    }


def install_cameras(world, library, carla, ego, callbacks, overrides=None):
    sensors = []
    overrides = overrides or {}
    try:
        for name, width, height, fov, offset, pitch in CAMERAS:
            if name in overrides:
                row = overrides[name]
                offset = row['offset_xyz_m']
                pitch = row['pitch_deg']
            blueprint = library.find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('fov', str(fov))
            blueprint.set_attribute('sensor_tick', '0.05')
            location = carla.Location(x=offset[0], y=offset[1], z=offset[2])
            transform = carla.Transform(location, carla.Rotation(pitch=pitch))
            sensor = world.spawn_actor(blueprint, transform, attach_to=ego)
            sensors.append(sensor)
            sensor.listen(lambda image, key=name: callbacks[key].put(image))
    except Exception:
        for sensor in reversed(sensors):
            sensor.stop()
            sensor.destroy()
        raise
    return sensors


def acquire(survey, case, attempt, client, carla, *, sink_factory=FFV1Sink,
            materialized=False):
    if case not in CASES:
        raise ValueError('Unknown warning-person draft case')
    repo = repository_root(__file__)
    attempt = prepare_attempt(attempt, repo, case, survey['frames'],
                              materialized=materialized)
    selected_config = json.loads((attempt/'config.json').read_text())
    controls = selected_config.get('controller_knobs', {})
    camera_overrides = selected_config.get('camera_overrides', {})
    world = client.get_world()
    readback = bind(survey, world, carla)
    route = readback['plan']['cases'][case]['route_xy_m']
    first, second = route[:2]
    yaw = degrees(atan2(second[1]-first[1], second[0]-first[0]))
    transform = carla.Transform(
        carla.Location(x=first[0], y=first[1], z=survey['anchor_z_m']+0.25),
        carla.Rotation(yaw=yaw))
    original_settings = world.get_settings()
    settings = copy.copy(original_settings)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05
    ego = None
    sensors = []
    sinks = {}
    (attempt/'live-readback.json').write_text(json.dumps(readback, indent=2)+'\n')
    (attempt/'road.xodr').write_text(world.get_map().to_opendrive())
    callbacks = {name: queue.Queue() for name, *_ in CAMERAS}
    controller = RouteControl(route, **controls)
    prior_frame = -1
    prior_time = -1.0
    try:
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        ego = world.try_spawn_actor(library.find(survey['ego_blueprint']), transform)
        if ego is None:
            raise ValueError('Surveyed ego spawn is occupied')
        person = world.get_actors().find(survey['warning_person_actor_id'])
        sensors = install_cameras(world, library, carla, ego, callbacks,
                                  camera_overrides)
        for name, width, height, *_ in CAMERAS:
            sinks[name] = sink_factory(attempt/(name+'.mkv'), width, height)
        with (attempt/'native-actors.jsonl').open('x') as actors, \
             (attempt/'video_frames.jsonl').open('x') as frames, \
             (attempt/'trace.jsonl').open('x') as trace:
            for index in range(survey['frames']):
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                speed = hypot(hypot(velocity.x, velocity.y), velocity.z)
                command = controller.decide(pose.location.x, pose.location.y,
                                             pose.rotation.yaw, speed)
                ego.apply_control(carla.VehicleControl(
                    throttle=command['throttle'], brake=command['brake'],
                    steer=command['steer']))
                frame = world.tick()
                if type(frame) is not int or frame <= prior_frame:
                    raise ValueError('Original CARLA frame did not advance')
                prior_frame = frame
                for name, *_ in CAMERAS:
                    image = callbacks[name].get(timeout=10)
                    if image.frame != frame:
                        raise ValueError('Camera frame mismatch: '+name)
                    sinks[name].write(image)
                timestamp = world.get_snapshot().timestamp.elapsed_seconds
                if timestamp <= prior_time:
                    raise ValueError('Original CARLA time did not advance')
                prior_time = timestamp
                frames.write(json.dumps({'video_frame': index,
                                         'carla_frame': frame,
                                         'native_frame': frame,
                                         'time_s': timestamp})+'\n')
                observed = sample(world, carla, ego, person, command)
                actors.write(json.dumps(dict(observed, frame=frame,
                                             video_frame=index,
                                             time_s=timestamp), allow_nan=False)+'\n')
                trace.write(json.dumps({
                    'frame': frame, 'time_s': timestamp,
                    'position_m': observed['ego_position_xyz_m'][:2],
                    'position': dict(zip(('x','y','z'),observed['ego_position_xyz_m'])),
                    'heading_deg': observed['ego_yaw_deg'],
                    'speed_mps': observed['ego_speed_mps'],
                    'speed_mph': observed['ego_speed_mps']/.44704,
                    'velocity_mps': observed['ego_velocity_xyz_mps'],
                    'speed_provenance': 'original_carla_velocity',
                    'control': command,
                }, allow_nan=False)+'\n')
    finally:
        active_error = sys.exc_info()[0] is not None
        errors = []
        if ego is not None:
            try:
                ego.apply_control(carla.VehicleControl(throttle=0, brake=1))
            except Exception as error:
                errors.append(error)
        for sensor in reversed(sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except Exception as error:
                errors.append(error)
        for sink in sinks.values():
            try:
                sink.close()
            except Exception as error:
                errors.append(error)
        if ego is not None:
            try:
                ego.destroy()
            except Exception as error:
                errors.append(error)
        try:
            world.apply_settings(original_settings)
        except Exception as error:
            errors.append(error)
        if errors and not active_error:
            raise errors[0]
    receipt = {'source_frames': survey['frames'], 'capture_rate_hz': 20,
               'case': case, 'four_cameras': [name+'.mkv' for name, *_ in CAMERAS],
               'frame_map': 'video_frames.jsonl', 'actor_rows': 'native-actors.jsonl',
               'map': 'road.xodr', 'trace': 'trace.jsonl',
               'source_kind': 'original_carla_capture',
               'physical_completion_claimed': False,
               'warning_act_verified': False}
    (attempt/'capture-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    (attempt/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'source': 'live_carla_synchronous_20hz',
        'physical_acceptance_claimed': False,
    }, indent=2)+'\n')
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--survey', required=True)
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)
    acquire(json.loads(Path(args.survey).read_text()), args.case,
            args.attempt, client, carla)


if __name__ == '__main__':
    main()
