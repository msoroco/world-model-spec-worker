"""Exact straight green case entrypoint; original site sources are required for capture."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from native_scene import inside, source, verify_site
from saved_attempt import ASSIGNMENT, CASES
from delivery_audit import PRODUCTION_PROFILE, VIEWS


def load_case(path=None):
    case = json.loads(Path(path or Path(__file__).with_name('scene.json')).read_text())
    suffix = case.get('case_suffix')
    if (case.get('assignment_id') != ASSIGNMENT or suffix not in CASES or
            case.get('case_id') != ASSIGNMENT + '__' + suffix or
            case.get('cell_id') != 'C111125' or
            case.get('law_id') != 'NRS-484B-307-2a' or
            case.get('actor') != 'motor_vehicle_driver'):
        raise ValueError('wrong exact straight-green assignment or case')
    route = case.get('route_xy')
    zone = case.get('intersection_polygon_xy')
    crosswalk = case.get('adjacent_crosswalk_polygon_xy')
    if not isinstance(route, list) or len(route) < 3 or not any(
            inside(point, zone) for point in route[1:-1]):
        raise ValueError('straight route misses intersection')
    if any(abs(float(point[1]) - float(route[0][1])) > case['straight_tolerance_m']
           for point in route):
        raise ValueError('route turns outside straight cell')
    kind, region = CASES[suffix]
    if case.get('other_user_kind') != kind or case.get('other_user_region_at_exhibition') != region:
        raise ValueError('other user differs from exact case')
    if kind is not None:
        position = case.get('other_user_spawn_xy')
        if not isinstance(position, list) or len(position) != 2:
            raise ValueError('other user spawn geometry missing')
        in_zone = inside(position, zone)
        in_crosswalk = inside(position, crosswalk)
        actual = 'intersection' if in_zone else 'adjacent_crosswalk' if in_crosswalk else 'outside'
        if actual != region:
            raise ValueError('other user spawn does not construct exhibition region')
    if suffix == 'green_pedestrian_late':
        destination = case.get('other_user_destination_xy')
        if not isinstance(destination, list) or not inside(destination, crosswalk):
            raise ValueError('late pedestrian path does not enter adjacent crosswalk')
    if (case.get('official_signal_aspects') != ['circular_green'] or
            case.get('duration_frames') != 900 or case.get('rate_hz') != 20):
        raise ValueError('sole circular green and full duration required')
    return case


def check():
    case = load_case()
    print(json.dumps({'case_id': case['case_id'], 'offline_geometry_checked': True,
                      'original_site_required_at_capture': True}))


def sealed_ref(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('missing original source: ' + name)
    return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def original_signal_reader(world, site, root):
    """Bind an original asset survey to each Native light state readback."""
    original = json.loads(source({'path': site['signal_source_path'],
         'sha256': next(r['sha256'] for r in site['original_sources']
                        if r['path'] == site['signal_source_path'])}, root).read_text())
    if (original.get('official') is not True or original.get('head_id') != site['official_head_id']
            or original.get('facing_approach_id') != site['ego_approach_id']
            or original.get('illuminated_shape') != 'circular'
            or original.get('enabled_indications') != ['circular_green']):
        raise ValueError('reviewed official circular-only head source missing')
    light = world.get_actor(site['official_head_id'])
    if light is None or light.id != site['official_head_id']:
        raise ValueError('original official head absent from Native world')
    def read(snapshot, head_id):
        state = light.get_state()
        if head_id != light.id or getattr(state, 'name', str(state).split('.')[-1]).lower() != 'green':
            raise ValueError('original circular green state changed')
        return {'head_id': light.id, 'facing_approach_id': site['ego_approach_id'],
                'lit_aspects': ['circular_green'], 'observed_frame': snapshot.frame,
                'asset_source_sha256': sealed_ref(root, site['signal_source_path'])['sha256']}
    return read


def install_four_cameras(world, ego, site, carla):
    """Use four source-surveyed camera poses, preserving original image callbacks."""
    poses = site.get('camera_poses')
    if not isinstance(poses, dict) or set(poses) != set(VIEWS):
        raise ValueError('four source-surveyed camera poses required')
    sensors = {}
    try:
        for name in VIEWS:
            pose = poses[name]
            if (not isinstance(pose, dict) or set(pose) != {'x', 'y', 'z', 'pitch', 'yaw', 'roll', 'fov_deg'}
                    or not 30 <= float(pose['fov_deg']) <= 120):
                raise ValueError('source-surveyed camera transform/fov missing: ' + name)
            width, height = PRODUCTION_PROFILE[name]
            blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('fov', str(pose['fov_deg']))
            transform = carla.Transform(carla.Location(x=pose['x'], y=pose['y'], z=pose['z']),
                                        carla.Rotation(pitch=pose['pitch'], yaw=pose['yaw'], roll=pose['roll']))
            sensor = world.spawn_actor(blueprint, transform,
                                       attach_to=ego if name == 'driver_reference' else None)
            if sensor is None:
                raise ValueError('original camera spawn failed: ' + name)
            sensors[name] = sensor
        return sensors
    except BaseException:
        for sensor in reversed(list(sensors.values())):
            sensor.destroy()
        raise


def copy_reviewed_bundle(bundle, output):
    """Copy only a hash-listed site survey and required context into the attempt."""
    index = json.loads((bundle / 'bundle-index.json').read_text())
    refs = index.get('sources')
    if not isinstance(refs, list) or not refs:
        raise ValueError('reviewed original bundle source index missing')
    for ref in refs:
        original = source(ref, bundle)
        target = output / ref['path']
        if target.exists() or target.parent != output:
            raise ValueError('original source conflicts with materialized bundle')
        shutil.copyfile(original, target)
    for name in ('site.json', 'camera-profile.json', 'other-devices.json'):
        if name not in {ref['path'] for ref in refs}:
            raise ValueError('reviewed original source missing: ' + name)
    return index


def run_native(output, host, port):
    """Require a separately supplied original site bundle before any Native action.

    The location is set by the local operator after reviewing the Native map and
    signal head. Missing or stale sources stop before simulation. The full
    acquisition bridge owns original frames and media after that preflight.
    """
    import carla
    from native_session import capture_with_media
    from native_scene import construct_native
    from straight_control import command
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore
    case = load_case()
    bundle_value = os.environ.get('C111125_ORIGINAL_SITE_BUNDLE')
    if not bundle_value:
        raise ValueError('reviewed original site bundle required')
    bundle = Path(bundle_value).resolve()
    if not bundle.is_dir() or not (bundle / 'site.json').is_file():
        raise ValueError('reviewed original site bundle missing')
    site = json.loads((bundle / 'site.json').read_text())
    verify_site(site, bundle)
    config = json.loads((Path(__file__).with_name('config.json')).read_text())
    throttle_scale = config.get('native_throttle_scale', 1.0)
    if (type(throttle_scale) not in (int, float) or not 0.5 <= throttle_scale <= 1.0):
        raise ValueError('unsupported engineering throttle scale')
    control_site = dict(site)
    control_site['approach_throttle'] = site['approach_throttle'] * throttle_scale
    control_site['proceed_throttle'] = site['proceed_throttle'] * throttle_scale
    if (site['cell_id'], site['actor']) != (case['cell_id'], case['actor']):
        raise ValueError('original site differs from exact case')
    index = copy_reviewed_bundle(bundle, output)
    verify_site(site, output)
    site_ref = sealed_ref(output, 'site.json')
    camera_profile_ref = sealed_ref(output, 'camera-profile.json')
    other_devices_ref = sealed_ref(output, 'other-devices.json')
    if site.get('other_user_spawn_xy') != case.get('other_user_spawn_xy'):
        raise ValueError('original source does not construct exact other-user placement')
    client = carla.Client(host, int(port))
    client.set_timeout(30)
    saved = snapshot(client)
    world = client.get_world()
    actors = []
    sensors = {}
    pipeline = None
    frame_map = None
    phase = 'initializing'
    failures = []
    restored = False
    try:
        if world.get_map().name != site['native_map_name']:
            raise ValueError('Native map differs from original site')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        blueprints = world.get_blueprint_library()
        ego_bp = blueprints.find('vehicle.tesla.model3')
        other_bp = (blueprints.find('walker.pedestrian.0001') if case['other_user_kind'] == 'pedestrian'
                    else blueprints.find('vehicle.audi.tt') if case['other_user_kind'] else None)
        spawned = construct_native(site, bundle, world, carla, ego_bp, other_bp,
                                   case['other_user_kind'])
        actors = spawned['actors']
        ego = actors[0]
        other = actors[1] if len(actors) == 2 else None
        signal_reader = original_signal_reader(world, site, output)
        sensors = install_four_cameras(world, ego, site, carla)
        context = {'official_head_id': site['official_head_id'],
                   'ego_approach_id': site['ego_approach_id'],
                   'other_devices_ref': other_devices_ref,
                   'participant_context_refs': {}}
        other_context_ref = sealed_ref(output, 'other-context.json') if other else None
        if other:
            context['participant_context_refs'][str(other.id)] = other_context_ref
        (output / 'reviewed-context.json').write_text(json.dumps(context, sort_keys=True) + '\n')
        context_ref = sealed_ref(output, 'reviewed-context.json')
        pipeline = PipelineCapture(client, ego, output, case['case_id'])
        frame_map = FrameMap(output / 'video_frames.jsonl')
        def before_tick(index):
            if other is not None:
                if case['case_suffix'] == 'green_pedestrian_late' and index < 20:
                    other.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=0, y=0, z=0), speed=0))
                elif case['other_user_kind'] == 'pedestrian':
                    other.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=0, y=-1, z=0), speed=1))
                else:
                    other.apply_control(carla.VehicleControl(throttle=.18, brake=0, steer=0))
            current = world.get_snapshot()
            signal = signal_reader(current, site['official_head_id'])
            p = ego.get_location()
            users = []
            if other is not None:
                q = other.get_location()
                xy = [q.x, q.y]
                region = ('intersection' if inside(xy, site['intersection_polygon_xy']) else
                          'adjacent_crosswalk' if inside(xy, site['adjacent_crosswalk_polygon_xy']) else 'outside')
                users.append({'region': region, 'id': str(other.id), 'kind': case['other_user_kind']})
            policy = 'proceed_when_clear' if other is None else 'yield_to_present'
            directive = command(control_site, {'official_head_id': signal['head_id'],
                                       'facing_approach_id': signal['facing_approach_id'],
                                       'lit_aspects': signal['lit_aspects'],
                                       'frame': current.frame, 'ego_xy': [p.x, p.y],
                                       'other_users': users}, policy)
            ego.apply_control(carla.VehicleControl(throttle=directive['throttle'],
                              brake=directive['brake'], steer=0))
        def after_tick(snapshot, row):
            pipeline.capture(snapshot.frame, snapshot.timestamp.elapsed_seconds)
            frame_map.append(snapshot.frame, snapshot.timestamp.elapsed_seconds)
        phase = 'capturing'
        scratch = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')) / ('camera-scratch-' + output.name)
        if '.runtime-work' not in scratch.parts:
            raise ValueError('camera scratch must be under .runtime-work')
        scratch.mkdir(parents=True, exist_ok=False)
        session = capture_with_media(world, ego, other, site, site_ref,
                 case['case_suffix'], signal_reader, output, sensors, scratch,
                 camera_profile_ref, context_ref, other_context_ref,
                 before_tick=before_tick, after_tick=after_tick)
        sample_dir = output / 'source-frame-samples'
        sample_dir.mkdir(exist_ok=False)
        sample_refs = {}
        for view in VIEWS:
            sample_refs[view] = {}
            for index in (0, 450, 899):
                relative = f'source-frame-samples/{view}-{index:06d}.png'
                original = scratch / view / f'{index:06d}.png'
                if not original.is_file():
                    raise ValueError('original camera PNG sample missing')
                shutil.copyfile(original, output / relative)
                sample_refs[view][str(index)] = sealed_ref(output, relative)
        (output / 'source-frame-samples.json').write_text(
            json.dumps({'case_id': case['case_id'], 'samples': sample_refs}, sort_keys=True) + '\n')
        phase = 'closing'
        pipeline.close(); pipeline = None
        frame_map.close(); frame_map = None
        packet = session['packet']
        (output / 'original-green-packet.json').write_text(json.dumps(packet, sort_keys=True) + '\n')
        acquired = ('original-green-packet.json','site.json','original-events.json','video_frames.jsonl')
        (output / 'acquisition.json').write_text(json.dumps({name: {'kind':'original_native',
            'sha256':sealed_ref(output,name)['sha256']} for name in acquired}, sort_keys=True) + '\n')
        phase = 'sealed'
    finally:
        for resource in (pipeline, frame_map):
            if resource is not None:
                try: resource.close()
                except BaseException as exc: failures.append(repr(exc))
        for sensor in reversed(list(sensors.values())):
            try: sensor.destroy()
            except BaseException as exc: failures.append(repr(exc))
        for actor in reversed(actors):
            try: actor.destroy()
            except BaseException as exc: failures.append(repr(exc))
        try:
            restore(client, saved)
            restored = True
        except BaseException as exc:
            failures.append(repr(exc))
        if phase == 'sealed' and restored and not failures:
            seal_capture(output, frames=900, restoration={'restored':True,
                'settings_readback':'world_restore source readback'}, errors=[],
                encoder_exit_codes={name:0 for name in VIEWS},
                context={'straight_green': {'site_ref': site_ref, 'bundle_sources': index['sources']}})
        else:
            (output / 'native-run-status.json').write_text(json.dumps({
                'phase':phase, 'failures':failures, 'settings_restored':restored}) + '\n')
            if phase == 'sealed':
                raise RuntimeError('Native cleanup/restoration failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        check()
    else:
        if not args.output_dir:
            parser.error('--output-dir required')
        run_native(Path(args.output_dir), args.host, args.port)


if __name__ == '__main__':
    main()
