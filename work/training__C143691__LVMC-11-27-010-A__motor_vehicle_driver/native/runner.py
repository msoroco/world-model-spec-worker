"""Original Native trail-access acquisition draft; administrative facts need sources."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, open_drive
from route import CASE_LATERAL_M, FRAMES, RATE_HZ, target

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def select_subject_blueprint(library, exception_kind):
    """Choose a Native asset without treating its role name as legal identity."""
    patterns = {
        'none': ('vehicle.*',),
        'emergency_vehicle': ('vehicle.*ambulance*', 'vehicle.*firetruck*'),
        'right_of_way_maintenance': ('vehicle.*utility*', 'vehicle.*truck*'),
        'mobility_device': ('vehicle.*wheelchair*', 'vehicle.*mobility*'),
    }
    for pattern in patterns[exception_kind]:
        matches = sorted(library.filter(pattern), key=lambda item: item.id)
        if matches:
            return matches[0]
    raise RuntimeError('Native subject blueprint unavailable for ' + exception_kind)


def select_sign_blueprint(library):
    """A visible prop is a marker; its wording/authority needs independent review."""
    matches = sorted(library.filter('static.prop.*sign*'), key=lambda item: item.id)
    if not matches:
        raise RuntimeError('Native sign marker blueprint unavailable')
    return matches[0]


def check(config):
    geometry = geometry_check()
    if (config['cell_id'], config['law_id'], config['actor']) != (
            'C143691', 'LVMC-11-27-010-A', 'motor_vehicle_driver'):
        raise ValueError('exact assignment identity changed')
    variants = {'outside', 'all_present', 'no_designation', 'no_dedication',
                'no_posting', 'emergency', 'maintenance', 'mobility_device'}
    if config['route_case'] not in CASE_LATERAL_M or config['case_id'].rsplit('__', 1)[-1] not in variants:
        raise ValueError('unknown trail route case')
    source = config.get('source_context_request', {})
    if set(source) != {'official_designation', 'city_dedication',
                       'appropriate_posting', 'exception_kind'}:
        raise ValueError('trail prerequisite and exception request absent')
    if source['exception_kind'] not in {'none', 'emergency_vehicle',
                                        'right_of_way_maintenance', 'mobility_device'}:
        raise ValueError('unsupported trail exception request')
    if config['rate_hz'] != RATE_HZ or config['duration_s'] != FRAMES / RATE_HZ:
        raise ValueError('30-second 20-Hz recording required')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS:
        raise ValueError('four source cameras required')
    return {'geometry': geometry, 'frames': FRAMES, 'camera_names': CAMERAS,
            'native_imported': False, 'physical_acceptance_claimed': False}


def survey(carla, mapping):
    observations = []
    for x in (-50, 0, 8, 50):
        for y, expected_lane in ((6, -1), (2, -2)):
            wp = mapping.get_waypoint(carla.Location(x=x, y=y, z=1.4),
                                      project_to_road=True, lane_type=carla.LaneType.Any)
            if wp is None or wp.road_id != 1 or wp.lane_id != expected_lane or abs(wp.transform.location.x - x) > 1:
                raise RuntimeError('Native road/trail lane survey failed')
            observations.append({'x_m': x, 'y_m': y, 'road_id': wp.road_id,
                                 'lane_id': wp.lane_id, 'native_xyz_m': [
                                     wp.transform.location.x, wp.transform.location.y,
                                     wp.transform.location.z]})
    return observations


def control(config, frame, location, velocity):
    requested = target(config['route_case'], frame)
    speed = math.hypot(velocity.x, velocity.y)
    lateral_error = requested['y_m'] - location.y
    throttle = max(0.0, min(.4, .22 + .08 * (requested['target_speed_mps'] - speed)))
    brake = 0.0 if speed < requested['target_speed_mps'] + .5 else .2
    steer = max(-.25, min(.25, .09 * lateral_error))
    return {'throttle': throttle, 'brake': brake, 'steer': steer,
            'requested_x_m': requested['x_m'], 'requested_y_m': requested['y_m'],
            'requested_speed_mps': requested['target_speed_mps']}


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.saved_processing import record_native_exit
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'vehicle-poses.jsonl').exists():
        raise ValueError('new materialized attempt required')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    prior_world = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in prior_world.get_actors()):
        raise RuntimeError('exclusive idle Native world required')
    owned, encoders, camera_queues = [], {}, {}
    encoder_exits = {}
    capture = None
    changed = False
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=25, wall_height=0, additional_width=0,
            smooth_junctions=False, enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        readback = survey(carla, world.get_map())
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        (output / 'trail-inventory.json').write_text(json.dumps({
            'source_kind': 'native_saved_sample', 'cell_id': 'C143691',
            'native_lane_survey': readback,
            'trail_right_of_way_m': geometry_check()['trail_right_of_way_m'],
            'official_trails_plan_source': None, 'city_dedication_source': None,
            'posted_prohibition_source': None, 'exception_source': None,
            'administrative_prerequisites_verified': False,
            'source_context_request': config['source_context_request']}, indent=2) + '\n')
        library = world.get_blueprint_library()
        source_request = config['source_context_request']
        bp = select_subject_blueprint(library, source_request['exception_kind'])
        bp.set_attribute('role_name', 'c143691_motorized_subject')
        initial_y = CASE_LATERAL_M[config['route_case']]
        vehicle = world.spawn_actor(bp, carla.Transform(
            carla.Location(x=-50, y=initial_y, z=2), carla.Rotation(yaw=0)))
        owned.append(vehicle)
        if source_request['appropriate_posting']:
            sign_bp = select_sign_blueprint(library)
            sign = world.spawn_actor(sign_bp, carla.Transform(
                carla.Location(x=-6, y=2.6, z=1.1), carla.Rotation(yaw=180)))
            owned.append(sign)
            inventory = json.loads((output / 'trail-inventory.json').read_text())
            inventory['sign_marker_actor_id'] = sign.id
            inventory['sign_marker_blueprint_id'] = sign_bp.id
            inventory['sign_marker_native_readback'] = True
            inventory['sign_wording_and_authority_verified'] = False
            (output / 'trail-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
        barrier_choices = sorted(library.filter('static.prop.streetbarrier*'), key=lambda item: item.id)
        if not barrier_choices:
            raise RuntimeError('Native street-barrier prop blueprint unavailable')
        barrier_bp = barrier_choices[0]
        barriers = []
        for y in (-4.0, 4.0):
            barrier = world.spawn_actor(barrier_bp, carla.Transform(
                carla.Location(x=8, y=y, z=1.1), carla.Rotation(yaw=0)))
            owned.append(barrier)
            barriers.append(barrier)
        lower_top = barriers[0].get_transform().location.y + barriers[0].bounding_box.extent.y
        upper_bottom = barriers[1].get_transform().location.y - barriers[1].bounding_box.extent.y
        measured_gap = upper_bottom - lower_top
        vehicle_width = 2 * vehicle.bounding_box.extent.y
        if measured_gap < vehicle_width:
            raise RuntimeError('Native barrier opening lacks vehicle clearance')
        inventory = json.loads((output / 'trail-inventory.json').read_text())
        inventory['barrier_blueprint_id'] = barrier_bp.id
        inventory['barrier_clear_gap_m'] = measured_gap
        inventory['vehicle_width_m'] = vehicle_width
        inventory['barrier_gap_native_readback'] = True
        inventory['subject_blueprint_id'] = bp.id
        (output / 'trail-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
        (output / 'trail-authority-context.json').write_text(json.dumps({
            'source_kind': 'original_native', 'request': source_request,
            'official_record_reviewed': False, 'official_plan_source': None,
            'city_record_reviewed': False, 'city_dedication_source': None,
            'sign_wording_and_authority_reviewed': False,
            'emergency_identity_reviewed': False,
            'this_right_of_way_use_reviewed': False, 'maintenance_source': None,
            'device_design_reviewed': False,
            'impaired_person_use_reviewed': False,
            'original_documents_attached': False,
            'legal_verdict_claimed': False}, indent=2) + '\n')
        mounts = {'overview': (8, -26, 24, -35),
                  'approach': (-22, -8, 8, -15),
                  'reference_corner': (9, -12, 10, -15),
                  'driver_reference': (25, 11, 10, -20)}
        for name in CAMERAS:
            x, y, z, pitch = mounts[name]
            spec = next(c for c in config['cameras'] if c['name'] == name)
            cbp = library.find('sensor.camera.rgb')
            cbp.set_attribute('image_size_x', str(spec['width']))
            cbp.set_attribute('image_size_y', str(spec['height']))
            cbp.set_attribute('sensor_tick', str(1 / RATE_HZ))
            camera = world.spawn_actor(cbp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            camera_queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', str(RATE_HZ), '-i', '-',
                '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        capture = PipelineCapture(client, vehicle, output, config['case_id'],
                                  required_observations=[])
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'vehicle-poses.jsonl').open('x') as poses, \
                (output / 'camera-frames.jsonl').open('x') as image_rows:
            initial_time = None
            for index in range(FRAMES):
                vt, vv = vehicle.get_transform(), vehicle.get_velocity()
                request = control(config, index, vt.location, vv)
                vehicle.apply_control(carla.VehicleControl(
                    throttle=request['throttle'], brake=request['brake'], steer=request['steer']))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native snapshot/frame mismatch')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                camera_frames = {}
                for name, q in camera_queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('source camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                    image_rows.write(json.dumps({'frame': index, 'camera': name,
                        'native_frame': native_frame,
                        'rgb_sha256': hashlib.sha256(image.raw_data).hexdigest()}) + '\n')
                frame_map.append(native_frame, time_s, camera_native_frames=camera_frames)
                vt, vv = vehicle.get_transform(), vehicle.get_velocity()
                extent = vehicle.bounding_box.extent
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'vehicle_id': vehicle.id,
                    'vehicle_blueprint_id': vehicle.type_id,
                    'vehicle_xyz_m': [vt.location.x, vt.location.y, vt.location.z],
                    'vehicle_yaw_deg': vt.rotation.yaw,
                    'bbox_half_length_m': extent.x, 'bbox_half_width_m': extent.y,
                    'observed_speed_mps': math.hypot(vv.x, vv.y),
                    'requested_control': request, 'camera_native_frames': camera_frames,
                    'barrier_physical_clearance_verified': False}) + '\n')
                capture.capture(native_frame, time_s, extra={'c143691_trail': {
                    'vehicle_id': vehicle.id, 'source_context_request': source_request,
                    'camera_native_frames': camera_frames}})
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            encoder_exits[name] = process.wait(timeout=180)
            if encoder_exits[name] or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('source video encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        capture.close(confirmed=True)
        capture = None
        return {'frames': FRAMES, 'source_cameras': list(CAMERAS),
                'administrative_prerequisites_verified': False,
                'physical_acceptance_claimed': False}
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
        if changed:
            restored = restore(client, saved)
            if capture is None and len(encoder_exits) == len(CAMERAS):
                seal_capture(output, frames=FRAMES, restoration=restored, errors=[],
                             encoder_exit_codes=encoder_exits,
                             context={'case_id': config['case_id']})
                record_native_exit(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        if not args.output_dir:
            raise SystemExit('--output-dir required')
        print(json.dumps(execute(config, args.output_dir, args.host, args.port)))
