"""Unselected Native proposal for the two walking-side comparison conditions.

An operator must supply a reviewed road-source packet; CPU checks never contact CARLA.
"""

import argparse
import json
import queue
import math
from pathlib import Path

from walking_side import FRAMES, HZ, _source

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def check(config):
    if config.get('law_id') != 'NRS-484B-297-2' or config.get('cell_id') != 'C230259' or config.get('actor') != 'pedestrian':
        raise ValueError('Exact law, cell and actor required')
    if config.get('case_id') not in config.get('selected_case_ids', []) or config.get('condition') not in ('a', 'b'):
        raise ValueError('Exact comparison case required')
    if config.get('duration_s') != 30 or config.get('rate_hz') != HZ or config.get('frames') != FRAMES:
        raise ValueError('Full 30-second 600-frame capture required')
    if tuple(x.get('name') for x in config.get('cameras', [])) != VIEWS:
        raise ValueError('Four named source cameras required')
    for camera in config['cameras']:
        if not all(camera.get(k) for k in ('width', 'height', 'fov_deg', 'pose_strategy', 'location_xyz_m', 'rotation_pyr_deg')) or camera.get('fps') != HZ:
            raise ValueError('Source camera geometry incomplete')
    if config.get('source_packet_required') is not True or config.get('physical_completion') is not False or config.get('legal_verdict') is not None:
        raise ValueError('Source provenance and unknown outcome required')
    return {'case_id': config['case_id'], 'frames': FRAMES, 'rate_hz': HZ,
            'source_views': VIEWS, 'source_packet_required': True,
            'physical_completion': False, 'legal_verdict': None, 'carla_contacted': False}


def _packet(path, config):
    packet = json.loads(Path(path).read_text())
    traffic = _source(packet)
    if packet.get('source_kind') != 'original_native':
        raise ValueError('Native execution requires a reviewed original map packet')
    if packet.get('map_name') is None or packet.get('pedestrian_spawn_transform') is None or packet.get('vehicle_spawn_transform') is None:
        raise ValueError('Reviewed Native map and participant spawns required')
    if packet.get('condition') != config['condition']:
        raise ValueError('Source packet selected another condition')
    if packet.get('pedestrian_route_side') != ('traffic_left' if config['condition'] == 'a' else 'traffic_right'):
        raise ValueError('Source route side differs from planned comparison')
    direction = packet.get('pedestrian_direction_xyz')
    if not isinstance(direction, list) or len(direction) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in direction):
        raise ValueError('Pedestrian direction missing')
    dot = direction[0] * traffic[0] + direction[1] * traffic[1]
    if dot >= 0:
        raise ValueError('Pedestrian must face approaching traffic in both conditions')
    if not 0 < packet.get('pedestrian_speed_mps', 0) <= 3 or not 0 <= packet.get('vehicle_throttle', -1) <= 1:
        raise ValueError('Participant control source invalid')
    return packet


def execute(config, source_path, output_path, host, port):
    """Capture source pixels and positions; actual pixels and physical success remain unconfirmed."""
    check(config)
    packet = _packet(source_path, config)
    import carla
    from worker_exchange.world_restore import snapshot, restore
    from worker_exchange.native_output import FrameMap
    from pipeline_capture import PipelineCapture

    def transform(data):
        return carla.Transform(carla.Location(**data['location']), carla.Rotation(**data['rotation']))

    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'reviewed-road-source.json').write_text(Path(source_path).read_text())
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    initial = snapshot(client)
    actors = []
    cameras = []
    received = queue.Queue()
    try:
        if world.get_map().name != packet['map_name']:
            raise ValueError('Native map differs from reviewed source packet')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / HZ
        world.apply_settings(settings)
        blueprints = world.get_blueprint_library()
        pedestrian = world.try_spawn_actor(blueprints.find(packet['pedestrian_blueprint']), transform(packet['pedestrian_spawn_transform']))
        vehicle = world.try_spawn_actor(blueprints.find(packet['vehicle_blueprint']), transform(packet['vehicle_spawn_transform']))
        if pedestrian is None or vehicle is None:
            raise ValueError('Participant spawn occupied')
        actors += [pedestrian, vehicle]
        for camera in config['cameras']:
            bp = blueprints.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(camera['width']))
            bp.set_attribute('image_size_y', str(camera['height']))
            bp.set_attribute('fov', str(camera['fov_deg']))
            loc = camera['location_xyz_m']
            rot = camera['rotation_pyr_deg']
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=loc[0], y=loc[1], z=loc[2]),
                                                            carla.Rotation(pitch=rot[0], yaw=rot[1], roll=rot[2])), attach_to=vehicle)
            actors.append(sensor)
            cameras.append(sensor)
            (output / camera['name']).mkdir()
            sensor.listen(lambda image, name=camera['name']: received.put((name, image)))
        direction = packet['pedestrian_direction_xyz']
        control = carla.WalkerControl(direction=carla.Vector3D(x=direction[0], y=direction[1], z=direction[2]),
                                      speed=packet['pedestrian_speed_mps'])
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
             PipelineCapture(client, vehicle, output, config['case_id'], required_observations=config.get('required_atoms', [])) as capture, \
             (output / 'walking-source.jsonl').open('x', buffering=1) as trace:
            for index in range(FRAMES):
                pedestrian.apply_control(control)
                vehicle.set_autopilot(False)
                vehicle.apply_control(carla.VehicleControl(throttle=packet['vehicle_throttle'], brake=0, steer=0))
                tick = world.tick()
                seen = set()
                while len(seen) != len(VIEWS):
                    name, image = received.get(timeout=15)
                    if image.frame != tick or name in seen:
                        continue
                    image.save_to_disk(str(output / name / f'{index:06d}.png'))
                    seen.add(name)
                capture.capture(tick, index / HZ, extra={'video_frame': index, 'pedestrian_id': pedestrian.id})
                frame_map.append(tick, index / HZ, native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                p = pedestrian.get_transform()
                p_velocity = pedestrian.get_velocity()
                v = vehicle.get_transform()
                trace.write(json.dumps({'source_kind': 'original_native', 'video_frame': index, 'native_frame': tick,
                                        'time_s': index / HZ, 'pedestrian_id': pedestrian.id, 'vehicle_id': vehicle.id,
                                        'pedestrian_xy_m': [p.location.x, p.location.y],
                                        'vehicle_xy_m': [v.location.x, v.location.y],
                                        'pedestrian_heading_xy': [p_velocity.x, p_velocity.y]}) + '\n')
    finally:
        for sensor in cameras:
            sensor.stop()
        for actor in reversed(actors):
            actor.destroy()
        restore(client, initial)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--source')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        if not args.source or not args.output_dir:
            raise ValueError('Reviewed source packet and output dir required')
        execute(config, args.source, args.output_dir, args.host, args.port)
