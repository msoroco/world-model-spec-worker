"""Unselected C229954 Native stop proposal; original device source is mandatory."""

import argparse
import json
import math
import queue
from pathlib import Path

from stop_controller import FRAMES, command

VIEWS = ('overview', 'ego_front', 'curb_side', 'traffic_rear')
CASE = 'training__C229954__NRS-484B-500__vehicle_stopping_person__selected_d67fe2ae__condition_a'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(config):
    require(config.get('case_id') == CASE and config.get('law_id') == 'NRS-484B-500'
            and config.get('cell_id') == 'C229954'
            and config.get('actor') == 'vehicle_stopping_person'
            and config.get('frozen_cell') == {'layout': 'road', 'maneuver': 'stop_stand',
                                               'control': 'parking_restriction_device'},
            'Wrong exact case, law, actor or frozen cell')
    require(config.get('rate_hz') == 20 and config.get('duration_s') == 30
            and config.get('frames') == FRAMES, 'Full 600-frame capture required')
    cameras = config.get('cameras')
    require(isinstance(cameras, list) and tuple(x.get('name') for x in cameras) == VIEWS,
            'Four named source cameras required')
    for camera in cameras:
        require(all(type(camera.get(key)) is int and camera[key] >= 16
                    for key in ('width', 'height')) and camera.get('fps') == 20
                and len(camera.get('location_xyz_m', [])) == 3
                and len(camera.get('rotation_pyr_deg', [])) == 3,
                'Camera optics or pose missing')
    require(type(config.get('spawn_point_index')) is int and
            config['spawn_point_index'] >= 0 and
            config.get('vehicle_blueprint') == 'vehicle.tesla.model3',
            'Vehicle spawn proposal invalid')
    require(config.get('device_source_required') is True and
            config.get('device_designation_not_inferred_from_pose') is True and
            config.get('physical_completion') is False and
            config.get('legal_verdict') is None,
            'Original device provenance or outcome guard missing')
    require(config.get('controller') == 'observed_route_distance_stop_hold',
            'Controller policy differs')
    return {'case_id': CASE, 'frames': FRAMES, 'rate_hz': 20,
            'source_views': list(VIEWS), 'device_source_required': True,
            'physical_completion': False, 'legal_verdict': None,
            'carla_contacted': False}


def _source(path):
    source = json.loads(Path(path).read_text())
    require(source.get('source_kind') == 'original_official_device_review'
            and source.get('map_name') and source.get('device_id')
            and source.get('authority_source') and source.get('content_source')
            and source.get('designation_source')
            and source.get('hazard_context_source')
            and source.get('designated_polygon_map_m'),
            'Original official device/designation source missing')
    return source


def _xyz(vector):
    return [vector.x, vector.y, vector.z]


def execute(config, output, device_source_path, host, port):
    # No CARLA connection occurs before all original device fields are present.
    check(config)
    require(device_source_path is not None, 'Original device source required for Native run')
    source = _source(device_source_path)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import restore, snapshot

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original_world = snapshot(client)
    actors, sensors = [], []
    packets = queue.Queue()
    try:
        require(world.get_map().name == source['map_name'], 'Device source map differs')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        spawns = world.get_map().get_spawn_points()
        require(len(spawns) > config['spawn_point_index'], 'Spawn point unavailable')
        ego = world.try_spawn_actor(world.get_blueprint_library().find(config['vehicle_blueprint']),
                                    spawns[config['spawn_point_index']])
        require(ego is not None, 'Vehicle spawn occupied')
        actors.append(ego)
        for camera in config['cameras']:
            blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(camera['width']))
            blueprint.set_attribute('image_size_y', str(camera['height']))
            blueprint.set_attribute('fov', str(camera['fov_deg']))
            x, y, z = camera['location_xyz_m']
            pitch, yaw, roll = camera['rotation_pyr_deg']
            pose = carla.Transform(carla.Location(x=x, y=y, z=z),
                                   carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))
            sensor = world.spawn_actor(blueprint, pose, attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            (output / camera['name']).mkdir()
            sensor.listen(lambda image, name=camera['name']: packets.put((name, image)))
        polygon = source['designated_polygon_map_m']
        target_x = sum(p[0] for p in polygon) / len(polygon)
        target_y = sum(p[1] for p in polygon) / len(polygon)
        with PipelineCapture(client, ego, output, CASE,
                             required_observations=config.get('required_atoms', [])) as capture, \
                FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'native-stop-trace.jsonl').open('x', buffering=1) as trace:
            for index in range(FRAMES):
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(sum(v * v for v in _xyz(velocity)))
                remaining = math.hypot(target_x - pose.location.x, target_y - pose.location.y)
                control = command(index, remaining, speed)
                ego.apply_control(carla.VehicleControl(throttle=control['throttle'],
                                                       brake=control['brake'],
                                                       steer=control['steer']))
                tick = world.tick()
                seen = set()
                while len(seen) < len(VIEWS):
                    name, image = packets.get(timeout=15)
                    if image.frame != tick or name in seen:
                        continue
                    image.save_to_disk(str(output / name / f'{index:06d}.png'))
                    seen.add(name)
                capture.capture(tick, index / 20, extra={'video_frame': index,
                                                          'control_phase': control['phase']})
                frame_map.append(tick, index / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                trace.write(json.dumps({'source_kind': 'original_native_observation',
                                        'video_frame': index, 'native_frame': tick,
                                        'time_s': index / 20, 'position_m': _xyz(pose.location),
                                        'velocity_mps': _xyz(velocity),
                                        'target_xy_m': [target_x, target_y],
                                        'requested_control': control}) + '\n')
    finally:
        for sensor in sensors:
            sensor.stop()
        for actor in reversed(actors):
            actor.destroy()
        restore(client, original_world)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--device-source')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        require(args.output_dir is not None, '--output-dir required')
        execute(config, args.output_dir, args.device_source, args.host, args.port)
