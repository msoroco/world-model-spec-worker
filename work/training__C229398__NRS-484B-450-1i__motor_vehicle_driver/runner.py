"""Prospective original Native rail/curb capture; --check is CARLA free.

A real run requires independently identifiable narrow physical rail actors in
its loaded CARLA map. Missing rail assets, curb waypoints or camera joins fail.
No synthetic rail prop is created or passed off as a railroad.
"""

import argparse
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from rail_native_geometry import rail_from_actor, choose_curb_waypoint
from rail_source_contract import CAMERAS

AID = 'training__C229398__NRS-484B-450-1i__motor_vehicle_driver'
RATE = 20
FRAMES = 600
TARGETS = {'condition_a': 12.5, 'condition_b': 16.5,
           'stop_1': 12.5, 'stop_2': 16.5,
           'stand_1': 12.5, 'stand_2': 16.5}
BEHAVIORS = {'condition_a': 'park', 'condition_b': 'park',
             'stop_1': 'stop_depart', 'stop_2': 'stop_depart',
             'stand_1': 'stand_depart', 'stand_2': 'stand_depart'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(config):
    suffix = config['case_id'].split('__')[-1]
    require(suffix in TARGETS, 'Unknown exact rail case')
    require((config.get('law_id'), config.get('cell_id'), config.get('actor')) ==
            ('NRS-484B-450-1i', 'C229398', 'motor_vehicle_driver'),
            'Rail law/cell/actor changed')
    require(config.get('duration_frames') == FRAMES and config.get('rate_hz') == RATE,
            'Exact rail capture window changed')
    require(config.get('target_footprint_gap_m') == TARGETS[suffix],
            'Exact rail comparison target changed')
    require(config.get('behavior_variant') == BEHAVIORS[suffix],
            'Exact rail motion variant changed')
    require([c.get('name') for c in config['cameras']] == list(CAMERAS),
            'Four exact rail cameras required')
    dimensions = [(c.get('width'), c.get('height'), c.get('fps')) for c in config['cameras']]
    require(dimensions == [(1920, 1080, 20)] + [(1280, 720, 20)] * 3,
            'Pinned four-camera profile required')
    require(config.get('physical_verified') is False and config.get('legal_verdict') is None,
            'Prospective rail run claims an outcome')
    require(config.get('approach_distance_m') in (7.0, 10.0) and
            config.get('approach_speed_cap_mps') in (1.0, 1.5),
            'Unknown exact approach engineering knob')
    return {'case_id': config['case_id'], 'frames': FRAMES,
            'physical_rail_source_required': True, 'simulation_started': False}


def _camera(world, carla, library, spec, location, ego):
    bp = library.find('sensor.camera.rgb')
    bp.set_attribute('image_size_x', str(spec['width']))
    bp.set_attribute('image_size_y', str(spec['height']))
    bp.set_attribute('fov', str(spec.get('fov', 90)))
    bp.set_attribute('sensor_tick', '.05')
    name = spec['name']
    if name == 'driver_reference':
        transform = carla.Transform(carla.Location(x=.4, z=1.6), carla.Rotation(pitch=-5))
        return world.spawn_actor(bp, transform, attach_to=ego)
    offsets = {'overview': (-18, -18, 28, -45),
               'approach': (-12, -7, 6, -15),
               'reference_corner': (3, -8, 8, -25)}
    dx, dy, z, pitch = offsets[name]
    transform = carla.Transform(carla.Location(x=location[0] + dx,
                y=location[1] + dy, z=z), carla.Rotation(pitch=pitch))
    return world.spawn_actor(bp, transform)


def _survey(world):
    actors = [actor for actor in world.get_actors()
              if 'rail' in actor.type_id.lower() and not actor.type_id.startswith('vehicle.')]
    rails = []
    for actor in actors:
        try:
            rails.append(rail_from_actor(actor))
        except ValueError:
            continue
    require(len(rails) >= 2, 'Two identifiable original physical rail actors required')
    return rails


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    require(output.is_dir() and not (output / 'original-native-rows.jsonl').exists(),
            'Fresh exact rail Native attempt directory required')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    world = client.get_world()
    require(not saved['settings'].synchronous_mode, 'Exclusive asynchronous Native world required')
    require(not any(actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))
                    for actor in world.get_actors()), 'Exclusive idle Native world required')
    rails = _survey(world)
    library = world.get_blueprint_library()
    bp = library.find('vehicle.tesla.model3')
    bp.set_attribute('role_name', 'rail_subject')
    target = choose_curb_waypoint(world.get_map().generate_waypoints(1.0), rails,
                                  config['target_footprint_gap_m'], 2.0, 1.0)
    waypoint = target['waypoint']
    previous = waypoint.previous(config['approach_distance_m'])
    require(previous, 'No original road approach to rail parking target')
    departure = waypoint.next(12.0) if config['behavior_variant'] != 'park' else []
    if config['behavior_variant'] != 'park':
        require(departure, 'No original road departure for stop/stand target')
    start = previous[0].transform
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1 / RATE
    settings.substepping = True
    settings.max_substep_delta_time = .01
    settings.max_substeps = 10
    owned, encoders, streams = [], {}, {}
    capture = None
    changed = finished = False
    encoder_codes = {}
    try:
        world.apply_settings(settings)
        changed = True
        world.set_weather(carla.WeatherParameters.ClearNoon)
        ego = world.spawn_actor(bp, start)
        owned.append(ego)
        survey = {'source_kind': 'original_native_rail_survey',
                  'case_id': config['case_id'],
                  'review_status': 'original_geometry_pending_independent_review',
                  'rails': rails, 'native_map': world.get_map().name,
                  'map_opendrive_sha256': hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest(),
                  'selected_curb_waypoint': {'road_id': waypoint.road_id,
                                             'lane_id': waypoint.lane_id,
                                             'predicted_gap_m': target['predicted_footprint_gap_m']},
                  'physical_rail_identity_reviewed': False,
                  'legal_verdict': None}
        (output / 'original-rail-survey.json').write_text(json.dumps(survey, indent=2) + '\n')
        capture = PipelineCapture(client, ego, output, config['case_id'],
                                  required_observations=['kin.velocity', 'kin.extent'])
        for spec in config['cameras']:
            name = spec['name']
            sensor = _camera(world, carla, library, spec, target['center_xy_m'], ego)
            owned.append(sensor)
            stream = queue.Queue()
            sensor.listen(stream.put)
            streams[name] = stream
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', str(RATE), '-i', '-',
                '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        goal = target['center_xy_m']
        exit_goal = None if not departure else (departure[0].transform.location.x,
                                                departure[0].transform.location.y)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'original-native-rows.jsonl').open('x') as rows:
            for index in range(FRAMES):
                pose = ego.get_transform()
                dx, dy = goal[0] - pose.location.x, goal[1] - pose.location.y
                distance = math.hypot(dx, dy)
                leaving = ((config['behavior_variant'] == 'stop_depart' and index >= 240) or
                           (config['behavior_variant'] == 'stand_depart' and index >= 350))
                if leaving:
                    dx, dy = exit_goal[0] - pose.location.x, exit_goal[1] - pose.location.y
                    distance = math.hypot(dx, dy)
                    if distance > .35:
                        speed = min(config['approach_speed_cap_mps'], distance)
                        ego.set_target_velocity(carla.Vector3D(x=speed * dx / distance,
                                                               y=speed * dy / distance))
                        ego.apply_control(carla.VehicleControl(throttle=.25, brake=0))
                    else:
                        ego.set_target_velocity(carla.Vector3D())
                        ego.apply_control(carla.VehicleControl(throttle=0, brake=1, hand_brake=True))
                elif index < 200 and distance > .35:
                    speed = min(config['approach_speed_cap_mps'], distance)
                    ego.set_target_velocity(carla.Vector3D(x=speed * dx / distance,
                                                           y=speed * dy / distance))
                    ego.apply_control(carla.VehicleControl(throttle=.25, brake=0))
                else:
                    ego.set_target_velocity(carla.Vector3D())
                    ego.apply_control(carla.VehicleControl(throttle=0, brake=1, hand_brake=True))
                native_frame = world.tick()
                snap = world.get_snapshot()
                require(snap.frame == native_frame, 'Original Native frame differs')
                time_s = index / RATE
                capture.capture(native_frame, time_s)
                camera_frames = {}
                for name, stream in streams.items():
                    image = stream.get(timeout=30)
                    while image.frame < native_frame:
                        image = stream.get(timeout=30)
                    require(image.frame == native_frame, 'Original camera/frame join differs')
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = native_frame
                frame_map.append(native_frame, time_s,
                                 camera_native_frames=camera_frames)
                pose = ego.get_transform()
                box = ego.bounding_box
                velocity = ego.get_velocity()
                row = {'source_kind': 'original_native', 'case_id': config['case_id'],
                       'native_frame': native_frame, 'video_frame': index,
                       'time_s': time_s, 'vehicle_actor_id': ego.id,
                       'vehicle_center_xy_m': [pose.location.x, pose.location.y],
                       'vehicle_half_extent_xy_m': [box.extent.x, box.extent.y],
                       'vehicle_yaw_rad': math.radians(pose.rotation.yaw),
                       'pose_source_ref': f'native-actor:{ego.id}:transform:{native_frame}',
                       'extent_source_ref': f'native-actor:{ego.id}:bounding_box:{native_frame}',
                       'speed_source_ref': f'native-actor:{ego.id}:velocity:{native_frame}',
                       'speed_mps': math.hypot(velocity.x, velocity.y),
                       'halt_reason': 'unknown', 'requested_park_gap_m': config['target_footprint_gap_m']}
                rows.write(json.dumps(row, allow_nan=False) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            encoder_codes[name] = process.wait(timeout=180)
            require(encoder_codes[name] == 0,
                    'Original rail camera encoding failed: ' + name + error.decode()[-300:])
        capture.close(confirmed=True)
        capture = None
        names = ['original-rail-survey.json', 'original-native-rows.jsonl',
                 'video_frames.jsonl'] + [name + '.mkv' for name in CAMERAS]
        (output / 'original-source-seal.json').write_text(json.dumps({
            'format': 'original-rail-native-source-seal', 'case_id': config['case_id'],
            'sha256': {name: sha(output / name) for name in names},
            'physical_or_legal_outcome_claimed': False}, indent=2) + '\n')
        finished = True
    finally:
        if capture is not None:
            capture.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        restored = restore(client, saved) if changed else {'restored': True}
        if finished:
            require(restored.get('restored') is True, 'Original world restoration unverified')
            seal_capture(output, frames=FRAMES, restoration=restored, errors=[],
                         encoder_exit_codes=encoder_codes,
                         context={'rail_identity_reviewed': False,
                                  'legal_outcome_claimed': False})
    return {'case_id': config['case_id'], 'frames': FRAMES,
            'rail_identity_review_required': True,
            'physical_or_legal_outcome_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        require(args.output_dir is not None, '--output-dir required for Native rail capture')
        print(json.dumps(execute(config, args.output_dir, args.host, args.port)))
