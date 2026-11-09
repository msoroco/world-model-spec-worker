"""Exact C129731 Native capture. Importing or --check never connects to CARLA."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess

from geometry import plan_check, point, route, xodr
from controller import command, next_index


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def camera_spec():
    return [('overview', 1920, 1080, (0, 0, 30), -88),
            ('approach', 1280, 720, (-13, 0, 5), -14),
            ('reference_corner', 1280, 720, (10, -12, 12), -35),
            ('driver_reference', 1280, 720, (1, 0, 1.5), 0)]


def start_cameras(world, ego, config, owned, output):
    import carla
    streams = {}
    for name, width, height, offset, pitch in camera_spec():
        blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
        blueprint.set_attribute('image_size_x', str(width))
        blueprint.set_attribute('image_size_y', str(height))
        blueprint.set_attribute('sensor_tick', '0.05')
        if name == 'reference_corner':
            x, y, z = point(config['turn_station_m'])
            transform = carla.Transform(carla.Location(x=x + offset[0], y=y + offset[1], z=z + offset[2]),
                                        carla.Rotation(pitch=pitch, yaw=math.degrees(config['turn_station_m'] / 115)))
        else:
            transform = carla.Transform(carla.Location(*offset), carla.Rotation(pitch=pitch))
        sensor = world.spawn_actor(blueprint, transform, attach_to=ego if name != 'reference_corner' else None)
        owned.append(sensor)
        images = queue.Queue(maxsize=8)
        sensor.listen(images.put)
        process = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'rawvideo', '-pixel_format', 'bgra', '-video_size', f'{width}x{height}',
            '-framerate', '20', '-i', 'pipe:0', '-c:v', 'ffv1', str(output / (name + '.mkv'))],
            stdin=subprocess.PIPE)
        streams[name] = (sensor, images, process)
    return streams


def image_at(images, frame):
    image = images.get(timeout=60)
    while image.frame < frame:
        image = images.get(timeout=60)
    if image.frame != frame:
        raise RuntimeError('Camera original frame mismatch')
    return image


def body(actor):
    t = actor.get_transform()
    return [[p.x, p.y, p.z] for p in actor.bounding_box.get_world_vertices(t)]


def run(config, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from carla_sgg.law_evidence import actor_visibility
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    client = carla.Client(host, int(port))
    client.set_timeout(120)
    saved = snapshot(client)
    owned, streams = [], {}
    output.mkdir(parents=True, exist_ok=True)
    if json.loads((output / 'config.json').read_text()) != config:
        raise ValueError('Materialized config differs from requested Native case')
    (output / 'authored-road.xodr').write_text(xodr())
    events = []
    try:
        world = client.generate_opendrive_world(xodr())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        weather = carla.WeatherParameters.ClearNoon
        world.set_weather(weather)
        mapping = world.get_map()
        station = config['turn_station_m']
        ego_start = mapping.get_waypoint_xodr(1, -1, station - 30)
        other_start = mapping.get_waypoint_xodr(1, 1, station + 120)
        if ego_start is None or other_start is None:
            raise RuntimeError('Native OpenDRIVE lane not available')
        blueprints = world.get_blueprint_library().filter('vehicle.*')
        cars = [b for b in blueprints if 'vehicle.tesla.model3' == b.id]
        if not cars:
            raise RuntimeError('Required conventional motor-car blueprint missing')
        ego_bp, other_bp = cars[0], cars[0]
        ego_bp.set_attribute('role_name', 'C129731_subject_407')
        ego = world.try_spawn_actor(ego_bp, ego_start.transform)
        if ego is None:
            raise RuntimeError('Subject spawn blocked')
        owned.append(ego)
        other_bp.set_attribute('role_name', 'C129731_approaching_vehicle')
        other = world.try_spawn_actor(other_bp, other_start.transform)
        if other is None:
            raise RuntimeError('Approaching vehicle spawn blocked')
        owned.append(other)
        streams = start_cameras(world, ego, config, owned, output)
        path = route(station)
        index = 0
        with PipelineCapture(client, ego, output, config['selected_case_id'], visibility=True,
                             required_observations=config['required_atoms']) as capture, \
             FrameMap(output / 'video_frames.jsonl') as frame_map, \
             (output / 'turn_history.jsonl').open('x') as history, \
             (output / 'approach_history.jsonl').open('x') as approach, \
             (output / 'visibility_history.jsonl').open('x') as visibility_stream:
            for tick in range(int(config['duration_s'] * config['rate_hz'])):
                transform = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
                position = (transform.location.x, transform.location.y)
                index, pause = next_index(path, index, position, speed)
                target = path[index]
                controls = command(position, transform.rotation.yaw, speed, target,
                                   reverse=not target[3])
                if pause:
                    controls.update(throttle=0., brake=1.)
                ego.apply_control(carla.VehicleControl(throttle=controls['throttle'],
                    steer=controls['steer'], brake=controls['brake'], reverse=controls['reverse']))
                # The other vehicle approaches along the opposite Native lane.
                waypoint = mapping.get_waypoint(other.get_location())
                following = waypoint.next(8.0) if waypoint else []
                if len(following) != 1:
                    raise RuntimeError('Approaching vehicle route ambiguous')
                ot = other.get_transform()
                ov = other.get_velocity()
                ospeed = math.sqrt(ov.x ** 2 + ov.y ** 2 + ov.z ** 2)
                oc = command((ot.location.x, ot.location.y), ot.rotation.yaw, ospeed,
                             (following[0].transform.location.x, following[0].transform.location.y))
                other.apply_control(carla.VehicleControl(throttle=oc['throttle'],
                    steer=oc['steer'], brake=oc['brake']))
                frame = world.tick()
                now = world.get_snapshot().timestamp.elapsed_seconds
                capture.capture(frame, now)
                frame_map.append(frame, now)
                for name, (_, images, process) in streams.items():
                    process.stdin.write(image_at(images, frame).raw_data)
                et = ego.get_transform()
                visibility = actor_visibility(world, ego, distance_m=152.4, mapping=mapping)
                history.write(json.dumps({'frame': frame, 'time_s': now,
                    'heading_deg': et.rotation.yaw, 'body_vertices_m': body(ego),
                    'route_index': index, 'requested_reverse': not target[3]}) + '\n')
                approach.write(json.dumps({'frame': frame, 'time_s': now,
                    'body_vertices_m': body(other), 'velocity_mps': [ov.x, ov.y, ov.z],
                    'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
                    'station_m': waypoint.s}) + '\n')
                visibility_stream.write(json.dumps({'frame': frame, 'time_s': now,
                    'visibility': visibility}) + '\n')
                if index == len(path) - 1 and speed < .2:
                    events.append({'frame': frame, 'event': 'controller_route_end'})
        for sensor, _, process in streams.values():
            sensor.stop()
            process.stdin.close()
            if process.wait(timeout=120) != 0:
                raise RuntimeError('Camera lossless encoder failed')
        streams = {}
        write(output / 'curve_context.json', {'source': 'authored-road.xodr plus Native road.xodr',
            'turn_station_m': station, 'road_id': 1, 'curve_radius_m': 115,
            'crest_location_m': 190, 'roadway_surface_and_occlusion_require_native_review': True,
            'turnout_width_m': 12, 'legal_judgment': 'unresolved'})
        write(output / 'native-run-status.json', {'events': events, 'errors': [],
            'physical_completion_claimed': False, 'visibility_claimed': False})
    except BaseException as error:
        write(output / 'native-run-status.json', {'errors': [repr(error)],
            'physical_completion_claimed': False, 'visibility_claimed': False})
        raise
    finally:
        for sensor, _, process in streams.values():
            try:
                sensor.stop(); process.stdin.close(); process.wait(timeout=30)
            except Exception:
                process.kill()
        for actor in reversed(owned):
            try:
                actor.destroy()
            except Exception:
                pass
        restored = restore(client, saved)
        write(output / 'world-restoration.json', restored)
    from worker_exchange.native_output import seal_capture
    write(output / 'acquisition-provenance.json', {'provenance_kind': 'native',
        'diagnostic_fixture': False, 'acceptance_claimed': False})
    seal_capture(output, frames=config['duration_s'] * config['rate_hz'], restoration=restored,
                 errors=[], encoder_exit_codes={name: 0 for name, *_ in camera_spec()},
                 context={'law_id': config['law_id'], 'cell_id': config['cell_id']})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    proof = plan_check()
    if config['law_id'] != 'NRS-484B-407' or config['cell_id'] != 'C129731':
        raise ValueError('Exact law and cell required')
    if config['rate_hz'] != 20 or config['duration_s'] < 40:
        raise ValueError('Common capture duration and 20 Hz required')
    if args.check:
        print(json.dumps(proof, indent=2))
        return
    if args.output_dir is None:
        parser.error('--output-dir is required for Native capture')
    run(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
