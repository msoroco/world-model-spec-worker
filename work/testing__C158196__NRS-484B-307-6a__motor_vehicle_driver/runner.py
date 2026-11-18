"""Exact yellow/red Native capture entrypoint; --check uses CPU sources only."""
import argparse
import json
from pathlib import Path

from signal_control import CAMERAS, CAMERA_SIZES, construct_signal_comparison
from validate_signal_site import SITE, select_native_governing_head, validate as validate_site
from yellow_red_capture import run as run_capture
from yellow_red_policy import CASES, DURATION_FRAMES, RATE_HZ

PREFIX = 'testing__C158196__NRS-484B-307-6a__motor_vehicle_driver__'


def validate_config(config):
    site = validate_site(SITE)
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-307-6a', 'C158196', 'motor_vehicle_driver'):
        raise ValueError('Wrong exact yellow/red assignment')
    case_id = config.get('selected_case_id')
    if case_id not in {PREFIX + case for case in CASES}:
        raise ValueError('Wrong exact yellow/red case')
    if config.get('rate_hz') != RATE_HZ or config.get('duration_s') * RATE_HZ != DURATION_FRAMES:
        raise ValueError('Full-duration 20 Hz yellow/red capture required')
    if not isinstance(config.get('required_atoms'), list) or not isinstance(config.get('source_packets'), list):
        raise ValueError('Core source contract required')
    if config.get('site', {}).get('xodr_sha256') != site['site_sha256']:
        raise ValueError('Authored signal site hash differs')
    if (config['site'].get('native_map_id') != 'OpenDriveMap' or
            config['site'].get('approach_lanes') != {'ego': [158190, -1], 'through': [158194, -1]}):
        raise ValueError('Selected Native approach lanes differ')
    context = config.get('signal_context', {})
    if (context.get('native_map_id') != 'OpenDriveMap' or
            context.get('intersection_id') != site['junction_id'] or
            [context.get('ego_road_id'), context.get('ego_lane_id')] != [158190, -1] or
            context.get('native_signal_id') is not None or
            context.get('ego_route_lanes', [None])[0] != [158190, -1] or
            context.get('through_route_lanes', [None])[0] != [158194, -1] or
            config.get('signal_selector', {}).get('affected_lane') != [158190, -1] or
            not context.get('signal_head_video_source') or
            not context.get('affected_lane_source') or
            not context.get('intersection_polygon_xy_m')):
        raise ValueError('Selected signal context lacks exact Native governance source')
    cameras = config.get('cameras')
    if (not isinstance(cameras, list) or [c.get('name') for c in cameras] != list(CAMERAS) or
            any((c.get('width'), c.get('height')) != CAMERA_SIZES[c['name']] or
                c.get('fov_deg') != 90 for c in cameras)):
        raise ValueError('Four named original camera profiles required')
    if set(config.get('camera_mounts', {})) != set(CAMERAS):
        raise ValueError('Four exact camera mounts required')
    for name, mount in config['camera_mounts'].items():
        if mount.get('attach_to') not in (None, 'ego', 'through') or not mount.get('pose'):
            raise ValueError('Invalid original camera mount: ' + name)
    if set(config.get('actor_transforms', {})) != {'ego', 'through'} or set(config.get('actor_blueprints', {})) != {'ego', 'through'}:
        raise ValueError('Exact actor pair required')
    return config


def transform(carla, pose):
    return carla.Transform(carla.Location(**pose['location']), carla.Rotation(**pose['rotation']))


def capture(config, output_dir, host, port):
    import carla
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output / 'construction.json').is_file():
        raise ValueError('Materialize exact construction before Native capture')
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved = snapshot(client)
    failure = None
    summary = None
    try:
        world = client.generate_opendrive_world(SITE.read_text())
        if world.get_map().name != config['site']['native_map_id']:
            raise ValueError('Generated Native map name differs from authored site')
        light = select_native_governing_head(world)
        context = dict(config['signal_context'], native_signal_id=light.id)
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        blueprints = {}
        for role in ('ego', 'through'):
            blueprint = library.find(config['actor_blueprints'][role])
            blueprint.set_attribute('role_name', 'c158196_307_6a_' + role)
            blueprints[role] = blueprint
        camera_blueprints = {}
        for item in config['cameras']:
            camera = library.find('sensor.camera.rgb')
            camera.set_attribute('image_size_x', str(item['width']))
            camera.set_attribute('image_size_y', str(item['height']))
            camera.set_attribute('fov', str(item['fov_deg']))
            camera_blueprints[item['name']] = camera
        mounts = {name: {'transform': transform(carla, mount['pose']),
                         'attach_to': mount['attach_to']}
                  for name, mount in config['camera_mounts'].items()}
        actor_transforms = {role: transform(carla, pose)
                            for role, pose in config['actor_transforms'].items()}
        with construct_signal_comparison(world, config['site'], blueprints,
                                         actor_transforms, carla.TrafficLightState,
                                         'Green', light.id, True) as built:
            summary = run_capture(world, client, output, built, context,
                                  camera_blueprints, mounts, carla,
                                  config['selected_case_id'], config['required_atoms'])
    except Exception as error:
        failure = error
    try:
        restored = restore(client, saved)
    except Exception as error:
        (output / 'native-run-status.json').write_text(json.dumps({
            'case_id': config['selected_case_id'], 'errors': [str(error)],
            'capture_sealed': False}) + '\n')
        raise
    if failure is not None:
        (output / 'native-run-status.json').write_text(json.dumps({
            'case_id': config['selected_case_id'], 'errors': [str(failure)],
            'capture_sealed': False}) + '\n')
        raise failure
    seal_capture(output, frames=DURATION_FRAMES, restoration=restored, errors=[],
                 encoder_exit_codes=summary['encoder_exit_codes'],
                 context={'selected_case_id': config['selected_case_id'],
                          'original_head_visibility_review_pending': True})


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
                          'site_sha256': validate_site(SITE)['site_sha256'],
                          'source_frames': DURATION_FRAMES,
                          'cpu_config_checked': True, 'simulation_started': False}))
        return
    if not args.output_dir:
        raise ValueError('Native capture requires --output-dir')
    capture(config, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
