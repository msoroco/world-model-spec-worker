"""CARLA-lazy original capture for the paved-road speed/conditions cases.

The runner records eight source-driven variants. It does not decide whether an
observed speed is reasonable or proper under NRS 484B.600(1)(a).
"""
import argparse
import hashlib
import json
import math
from contextlib import ExitStack
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import PROFILE, source_cameras
from condition_capture import sample_frame, validate_surface_packet
from condition_construction import apply_sourced_weather, survey_narrow_route
from traffic_construction import spawn_lead_traffic
from traffic_controller import LongitudinalController

ASSIGNMENT = 'testing__C179789__NRS-484B-600-1a__motor_vehicle_driver'
SUFFIXES = ('dry_open_traffic', 'wet_same_traffic', 'narrow_same_traffic',
            'dense_traffic', 'low_visibility', 'ice_or_snow',
            'dry_4mps', 'dry_6mps')
CASES = tuple(ASSIGNMENT + '__' + suffix for suffix in SUFFIXES)
CAMERAS = tuple(PROFILE)


def validate_config(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-600-1a', 'C179789', 'motor_vehicle_driver'):
        raise ValueError('Exact speed/conditions law, cell and actor required')
    if config.get('selected_case_id') not in CASES or set(config.get('supported_case_ids', [])) != set(CASES):
        raise ValueError('Eight exact speed/conditions cases required')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('Pinned 20 Hz, 45-second source capture required')
    cameras = config.get('cameras')
    if not isinstance(cameras, list) or [row.get('name') for row in cameras] != list(CAMERAS):
        raise ValueError('Four ordered original cameras required')
    if any((row.get('width'), row.get('height')) != PROFILE[row['name']] or
           type(row.get('fov_deg')) not in (int, float) or not 30 <= row['fov_deg'] <= 120
           for row in cameras):
        raise ValueError('Pinned source camera dimensions/FOV required')
    if config.get('site_packet') != 'road_packet.json' or not isinstance(config.get('required_atoms'), list):
        raise ValueError('Original road packet and atom inventory required')
    target = config.get('condition_target')
    if not isinstance(target, dict) or target.get('surface') not in ('dry', 'wet', 'ice_or_snow'):
        raise ValueError('Exact sourced condition target required')
    for key in ('lane_width_m', 'longitudinal_body_gap_m', 'sight_distance_m',
                'precipitation_percent', 'fog_density_percent', 'fog_distance_m'):
        if key.startswith('fog_') and key not in target:
            continue
        bounds = target.get(key)
        if (not isinstance(bounds, list) or len(bounds) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in bounds) or
                bounds[0] < 0 or bounds[1] <= bounds[0]):
            raise ValueError('Finite target condition range required: ' + key)
    return config


def verify_observed_target(row, target):
    if row.get('surface') != target['surface']:
        raise ValueError('Original surface differs from selected case')
    values = {'lane_width_m': row['lane_width_m'],
              'longitudinal_body_gap_m': row['surrounding_traffic'][0]['longitudinal_body_gap_m'],
              'sight_distance_m': row['sight_distance_m'],
              'precipitation_percent': row['precipitation_percent']}
    for key in ('fog_density_percent', 'fog_distance_m'):
        if key in target:
            values[key] = row[key]
    for key, value in values.items():
        low, high = target[key]
        if not low <= value <= high:
            raise ValueError('Original Native condition outside selected case: ' + key)
    return True


def require_site_packet(packet, root, case_id):
    if not isinstance(packet, dict) or packet.get('review_status') != 'reviewed_native_road_site':
        raise ValueError('Original Native road, traffic and camera review required before capture')
    for key in ('reviewer', 'road_review_basis', 'traffic_review_basis',
                'camera_review_basis', 'native_map_id', 'vehicle_blueprint_id',
                'lead_blueprint_id'):
        value = packet.get(key)
        if not isinstance(value, str) or not value.strip() or any(
                word in value.lower() for word in ('synthetic', 'diagnostic')):
            raise ValueError('Original Native road review declaration required: ' + key)
    if packet.get('case_id') != case_id or type(packet.get('road_id')) is not int or type(packet.get('lane_id')) is not int:
        raise ValueError('Reviewed road/case identity differs')
    if packet.get('surface_packet') != 'surface_packet.json':
        raise ValueError('Original surface packet path required')
    surface = json.loads((Path(root) / 'surface_packet.json').read_text())
    surface_review = validate_surface_packet(surface, root)
    if (surface['native_map_id'], surface['road_id']) != (packet['native_map_id'], packet['road_id']):
        raise ValueError('Original roadway-surface map/road identity differs')
    for key in ('ego_spawn', 'lead_spawn'):
        transform = packet.get(key)
        if not isinstance(transform, dict) or any(type(transform.get(axis)) not in (int, float) or
            not math.isfinite(transform[axis]) for axis in ('x', 'y', 'z', 'yaw_deg')):
            raise ValueError('Finite reviewed Native spawn required: ' + key)
    weather_source = packet.get('weather_profile_source')
    if not isinstance(weather_source, dict) or not isinstance(weather_source.get('path'), str):
        raise ValueError('Original weather profile source binding required')
    relative = Path(weather_source['path'])
    root = Path(root).resolve()
    if relative.is_absolute() or '..' in relative.parts or str(relative) in ('', '.'):
        raise ValueError('Unsafe weather profile source path')
    path = root / relative
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError('Original weather profile source missing')
    text = path.read_text(encoding='utf-8')
    if not text.strip() or any(word in text.lower() for word in ('synthetic', 'diagnostic')):
        raise ValueError('Original weather profile document required')
    if hashlib.sha256(path.read_bytes()).hexdigest() != weather_source.get('sha256'):
        raise ValueError('Original weather profile source hash changed')
    try:
        source_profile = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError('Original weather profile source must be JSON') from error
    weather = packet.get('weather_profile')
    if (not isinstance(source_profile, dict) or source_profile.get('native_map_id') != packet['native_map_id']
            or source_profile.get('weather_profile') != weather):
        raise ValueError('Original weather document does not bind requested Native profile')
    if not isinstance(weather, dict):
        raise ValueError('Native weather profile required')
    for key in ('ego_target_speed_mps', 'lead_target_speed_mps'):
        if type(packet.get(key)) not in (int, float) or not math.isfinite(packet[key]) or packet[key] < 0:
            raise ValueError('Finite construction target speed required: ' + key)
    return surface_review, weather_source


def _transform(carla, row):
    return carla.Transform(carla.Location(x=row['x'], y=row['y'], z=row['z']),
                           carla.Rotation(yaw=row['yaw_deg']))


def _camera_transforms(carla, start):
    x, y, z, yaw = (start[key] for key in ('x', 'y', 'z', 'yaw_deg'))
    def pose(dx, dy, dz, turn, pitch):
        return carla.Transform(carla.Location(x=x + dx, y=y + dy, z=z + dz),
                               carla.Rotation(yaw=yaw + turn, pitch=pitch))
    return {'overview': pose(0, 0, 35, 0, -75),
            'approach': pose(18, 0, 5, 180, -12),
            'reference_corner': pose(15, 5, 6, -150, -20),
            'driver_reference': pose(1, 0, 1.65, 180, -5)}


def _sensor_frame(queue, frame):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError('Original source camera frame missing') from error
        if image.frame == frame:
            return image
        if image.frame > frame:
            raise ValueError('Original source camera skipped Native frame')
    raise ValueError('Original source camera frame join failed')


def capture(args, config):
    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / 'construction.json').is_file():
        raise ValueError('Use runtime.py capture to materialize exact construction first')
    packet = json.loads((output / 'road_packet.json').read_text())
    surface_review, weather_source = require_site_packet(packet, output, config['selected_case_id'])
    if surface_review['surface'] != config['condition_target']['surface']:
        raise ValueError('Sourced surface differs from selected condition target')
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as snapshot_world, restore
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = snapshot_world(client)
    world = client.get_world()
    ego = None
    capture_helper = None
    encoders = {}
    frames = 0
    error = None
    try:
        if world.get_map().name != packet['native_map_id']:
            raise ValueError('Native map differs from reviewed road')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        with apply_sourced_weather(world, packet['weather_profile'],
                                   profile_source=weather_source['path']) as weather_receipt:
            road = world.get_map()
            start = packet['ego_spawn']
            waypoint = road.get_waypoint(carla.Location(x=start['x'], y=start['y'], z=start['z']),
                                         project_to_road=False)
            if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (packet['road_id'], packet['lane_id']):
                raise ValueError('Ego spawn differs from reviewed road/lane')
            narrow_survey = None
            if config['selected_case_id'].endswith('__narrow_same_traffic'):
                narrow_survey = survey_narrow_route(
                    waypoint, target_width_m=config['condition_target']['lane_width_m'])
            ego_blueprint = world.get_blueprint_library().find(packet['vehicle_blueprint_id'])
            ego = world.try_spawn_actor(ego_blueprint, _transform(carla, start))
            if ego is None:
                raise ValueError('Native ego spawn failed')
            lead_blueprint = world.get_blueprint_library().find(packet['lead_blueprint_id'])
            forward = (math.cos(math.radians(start['yaw_deg'])),
                       math.sin(math.radians(start['yaw_deg'])))
            with spawn_lead_traffic(world, ego, lead_blueprint,
                                    _transform(carla, packet['lead_spawn']),
                                    packet['road_id'], packet['lane_id'], forward) as traffic:
                lead = traffic['actor']
                ego_control = LongitudinalController(packet['ego_target_speed_mps'])
                lead_control = LongitudinalController(packet['lead_target_speed_mps'])
                gap = traffic['initial_longitudinal_body_gap_m']
                context = {'native_map_id': packet['native_map_id'],
                           'road_id': packet['road_id'], 'lane_id': packet['lane_id'],
                           'ego_actor_id': ego.id,
                           'road_surface_source': surface_review['source'],
                           'lane_width_source': 'original Native waypoint and road map',
                           'traffic_source': 'original Native actor body/velocity',
                           'weather_source': weather_receipt,
                           'weather_profile_source': weather_source,
                           'sight_source': 'original Native cast_ray and four cameras',
                           'curvature_source': 'original Native waypoint chain',
                           'braking_model_source': packet['braking_model_source'],
                           'diagnostic_reaction_time_s': packet['diagnostic_reaction_time_s'],
                           'diagnostic_braking_deceleration_mps2': packet['diagnostic_braking_deceleration_mps2'],
                           'legal_threshold_claimed': False}
                if narrow_survey is not None:
                    context['narrow_route_survey'] = narrow_survey
                (output / 'road_context.json').write_text(json.dumps(context, indent=2) + '\n')
                with source_cameras(world, ego, _camera_transforms(carla, start), config['cameras']) as sensors:
                    queues = {name: Queue() for name in CAMERAS}
                    for name, sensor in sensors.items():
                        sensor.listen(lambda image, name=name: queues[name].put(image))
                    with ExitStack() as stack:
                        for name, (width, height) in PROFILE.items():
                            encoders[name] = stack.enter_context(FFV1Writer(output / (name + '.mkv'), width, height))
                        mapping = stack.enter_context(FrameMap(output / 'video_frames.jsonl'))
                        history = stack.enter_context((output / 'condition_history.jsonl').open('x', buffering=1))
                        capture_helper = PipelineCapture(client, ego, output, config['selected_case_id'],
                                                         required_observations=config['required_atoms'])
                        try:
                            for _ in range(config['duration_s'] * config['rate_hz']):
                                ego_speed = ego.get_velocity()
                                lead_speed = lead.get_velocity()
                                ec = ego_control.step(math.sqrt(ego_speed.x**2 + ego_speed.y**2 + ego_speed.z**2),
                                                      lead_body_gap_m=gap)
                                lc = lead_control.step(math.sqrt(lead_speed.x**2 + lead_speed.y**2 + lead_speed.z**2))
                                ego.apply_control(carla.VehicleControl(throttle=ec['throttle'], brake=ec['brake']))
                                lead.apply_control(carla.VehicleControl(throttle=lc['throttle'], brake=lc['brake']))
                                world.tick()
                                snapshot = world.get_snapshot()
                                for name in CAMERAS:
                                    encoders[name].write(bytes(_sensor_frame(queues[name], snapshot.frame).raw_data))
                                capture_helper.capture(snapshot.frame, snapshot.timestamp.elapsed_seconds)
                                mapping.append(snapshot.frame, snapshot.timestamp.elapsed_seconds)
                                location = ego.get_location()
                                eye = carla.Location(x=location.x, y=location.y, z=location.z + 1.5)
                                direction = ego.get_transform().get_forward_vector()
                                row = sample_frame(world, ego, lead, snapshot, surface_review, eye,
                                                   (direction.x, direction.y, direction.z),
                                                   map_source='original Native waypoint',
                                                   ray_source='original Native cast_ray')
                                verify_observed_target(row, config['condition_target'])
                                history.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')
                                gap = row['surrounding_traffic'][0]['longitudinal_body_gap_m']
                                frames += 1
                        finally:
                            capture_helper.close()
                            capture_helper = None
    except BaseException as caught:
        error = caught
        raise
    finally:
        cleanup = []
        if capture_helper is not None:
            try:
                capture_helper.close(confirmed=False)
            except BaseException as caught:
                cleanup.append(str(caught))
        if ego is not None:
            try:
                ego.destroy()
            except BaseException as caught:
                cleanup.append(str(caught))
        restoration = restore(client, saved)
        if error is None and not cleanup:
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                         encoder_exit_codes={name: writer.exit_code for name, writer in encoders.items()},
                         context={'physical_acceptance_claimed': False,
                                  'surface_source_review': surface_review})
        if error is None and cleanup:
            raise ValueError('Native cleanup failed: ' + '; '.join(cleanup))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = validate_config(json.loads(Path(__file__).with_name('config.json').read_text()))
    if args.check:
        print(json.dumps({'case_id': config['selected_case_id'], 'cpu_check_passed': True,
                          'simulation_started': False}))
        return
    if not args.output_dir:
        raise ValueError('--output-dir required for Native capture')
    capture(args, config)


if __name__ == '__main__':
    main()
