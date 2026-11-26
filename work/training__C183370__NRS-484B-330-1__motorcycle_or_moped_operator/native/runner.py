"""Prospective Native flagger capture. CPU --check does not import CARLA."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import shutil
import subprocess

from check_requests import check_pair, read_case


CAMERA_POSES = {
    'overview': (-2, -22, 27, -45, 70),
    'approach': (-30, -14, 7, -15, 35),
    'flagger': (7, -13, 7, -15, 150),
    'rear': (25, -13, 8, -15, 190),
}

REVIEW_COPIES = {
    'authority_source_path': 'original-authority-source',
    'zone_designation_source_path': 'original-zone-source',
    'signal_asset_source_path': 'original-signal-source',
}


def check():
    root = Path(__file__).resolve().parent
    proof = check_pair(base=root)
    check_pair(base=root, pair=('probe_c', 'probe_d'))
    selected = root / 'selected-case.json'
    if selected.is_file():
        suffix = json.loads(selected.read_text()).get('suffix')
        config, _ = read_case(suffix, base=root)
        proof['selected_case_id'] = config['case_id']
    return proof


def _read_review(path, library, zone_basis='designated_temporary_zone'):
    """Require locally reviewed assets; a walker label is not a flagger signal."""
    if not path.is_file():
        raise ValueError('Original flagger authority and visible signal asset review missing')
    review = json.loads(path.read_text())
    for key in ('authority_source_path', 'zone_designation_source_path',
                'signal_asset_source_path'):
        source = Path(review.get(key, ''))
        if not source.is_file() or source.stat().st_size == 0:
            raise ValueError('Original flagger review source missing: ' + key)
        expected = review.get(key.replace('_path', '_sha256'))
        if not isinstance(expected, str) or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError('Original flagger review source hash differs: ' + key)
    for key in ('stop_signal_blueprint', 'release_signal_blueprint',
                'zone_entry_marker_blueprint', 'zone_exit_marker_blueprint'):
        blueprint_id = review.get(key)
        if not isinstance(blueprint_id, str) or not blueprint_id:
            raise ValueError('Source-reviewed flagger or zone marker blueprint missing')
        library.find(blueprint_id)
    if zone_basis == 'clearly_marked_construction_or_maintenance_area':
        for key in ('work_area_barrier_blueprint', 'work_activity_blueprint'):
            blueprint_id = review.get(key)
            if not isinstance(blueprint_id, str) or not blueprint_id:
                raise ValueError('Source-reviewed work-area asset missing: ' + key)
            library.find(blueprint_id)
    elif zone_basis != 'designated_temporary_zone':
        raise ValueError('Unknown statutory location basis')
    if review.get('governs_approach') is not True:
        raise ValueError('Flagger signal governance source missing')
    for key, name in REVIEW_COPIES.items():
        source = Path(review[key])
        copied = path.parent / name
        shutil.copyfile(source, copied)
        if hashlib.sha256(copied.read_bytes()).hexdigest() != review[key.replace('_path', '_sha256')]:
            raise ValueError('Copied flagger review source hash differs: ' + key)
    return review


def _spawn_zone_markers(world, library, carla, review, owned):
    """Place both reviewed boundary markers beside the authored shoulder."""
    markers = []
    for name, x in (('entry', -25.0), ('exit', 25.0)):
        blueprint = library.find(review['zone_' + name + '_marker_blueprint'])
        marker = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=x, y=-6.5, z=1.0), carla.Rotation(yaw=90)))
        owned.append(marker)
        markers.append(marker)
    return markers


def _spawn_work_area(world, library, carla, review, owned):
    """Construct reviewed work-area barriers and work-activity prop off-lane."""
    assets = []
    for key, x, y in (('work_area_barrier_blueprint', 5.0, -7.0),
                      ('work_area_barrier_blueprint', 15.0, -7.0),
                      ('work_activity_blueprint', 10.0, -8.0)):
        blueprint = library.find(review[key])
        actor = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=x, y=y, z=1.0), carla.Rotation(yaw=90)))
        owned.append(actor)
        assets.append(actor)
    return assets


def _cleanup_capture(pipeline, encoders, owned, client, prior, changed,
                     complete, restore_world):
    """Attempt world restoration even when capture finalization fails."""
    cleanup_error = None
    if pipeline is not None:
        try:
            pipeline.close(confirmed=complete)
        except Exception as error:
            cleanup_error = error
    for process in encoders.values():
        try:
            if process.poll() is None:
                process.kill()
                process.wait()
        except Exception as error:
            if cleanup_error is None:
                cleanup_error = error
    for actor in reversed(owned):
        try:
            if hasattr(actor, 'stop'):
                actor.stop()
            actor.destroy()
        except Exception:
            pass
    restoration = (restore_world(client, prior) if changed else
                   {'restored': True, 'world_unchanged': True})
    if cleanup_error is not None:
        raise cleanup_error
    return restoration


def capture(output_dir, suffix, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    root = Path(__file__).resolve().parent
    config, requests = read_case(suffix, base=root)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'native-rows.jsonl').exists():
        raise ValueError('Fresh Native attempt directory required')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = snapshot(client)
    old_world = client.get_world()
    if prior['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))
            for actor in old_world.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned, encoders, camera_queues = [], {}, {}
    pipeline = None
    changed = complete = False
    try:
        world = client.generate_opendrive_world(
            (root / suffix / 'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.5,
                max_road_length=10, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=True))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        (output / 'road.xodr').write_text(mapping.to_opendrive())
        driving = mapping.get_waypoint(carla.Location(x=-20, y=-1.75, z=1),
            project_to_road=False, lane_type=carla.LaneType.Driving)
        shoulder = mapping.get_waypoint(carla.Location(x=-20, y=-4.75, z=1),
            project_to_road=False, lane_type=carla.LaneType.Shoulder)
        if (driving is None or shoulder is None or driving.lane_id != -1 or
                shoulder.lane_id != -2 or driving.road_id != shoulder.road_id):
            raise RuntimeError('Native paved shoulder and supported driving lane absent')
        library = world.get_blueprint_library()
        review = _read_review(output / 'original-flagger-review.json', library,
                              config.get('zone_basis', 'designated_temporary_zone'))
        zone_markers = _spawn_zone_markers(world, library, carla, review, owned)
        work_area = (_spawn_work_area(world, library, carla, review, owned)
                     if config.get('zone_basis') ==
                     'clearly_marked_construction_or_maintenance_area' else [])
        motorcycle_bp = library.find('vehicle.kawasaki.ninja')
        motorcycle_bp.set_attribute('role_name', 'c183370_motorcycle_subject')
        motorcycle = world.spawn_actor(motorcycle_bp, carla.Transform(
            carla.Location(x=-40, y=-1.75, z=1), carla.Rotation(yaw=0)))
        owned.append(motorcycle)
        wheels = motorcycle.get_physics_control().wheels
        if len(wheels) != 2:
            raise RuntimeError('Native motor-powered two-wheel motorcycle absent')
        walkers = sorted(library.filter('walker.pedestrian.*'), key=lambda bp: bp.id)
        if not walkers:
            raise RuntimeError('Native flagger person blueprint unavailable')
        flagger_bp = walkers[0]
        flagger_bp.set_attribute('role_name', 'c183370_flagger_identity_pending')
        flagger = world.spawn_actor(flagger_bp, carla.Transform(
            carla.Location(x=0, y=-7, z=1), carla.Rotation(yaw=90)))
        owned.append(flagger)
        signal_actors = {}
        for name, x in (('stop', 0.0), ('release', 0.0)):
            signal_bp = library.find(review[name + '_signal_blueprint'])
            signal = world.spawn_actor(signal_bp, carla.Transform(
                carla.Location(x=x, y=-7.3, z=1.5 if name == 'stop' else -20),
                carla.Rotation(yaw=90)))
            owned.append(signal)
            signal_actors[name] = signal
        pipeline = PipelineCapture(client, motorcycle, output, config['case_id'],
            visibility=False, required_observations=['kin.velocity'])
        for name, spec in config['cameras'].items():
            bp = library.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(spec['width']))
            bp.set_attribute('image_size_y', str(spec['height']))
            bp.set_attribute('fov', str(spec['fov']))
            bp.set_attribute('sensor_tick', '.05')
            x, y, z, pitch, yaw = CAMERA_POSES[name]
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z),
                carla.Rotation(pitch=pitch, yaw=yaw)))
            owned.append(sensor)
            stream = queue.Queue()
            sensor.listen(stream.put)
            camera_queues[name] = stream
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', '20', '-i', '-',
                '-frames:v', '600', '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        first_time = None
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'native-rows.jsonl').open('x') as rows:
            for index, request in enumerate(requests):
                desired = request['requested_center_x_m']
                pose = motorcycle.get_transform()
                dx = desired - pose.location.x
                velocity_request = max(0, min(8, dx * 3))
                motorcycle.set_target_velocity(carla.Vector3D(x=velocity_request))
                signal = request['signal']
                signal_actors['stop'].set_transform(carla.Transform(
                    carla.Location(x=0, y=-7.3, z=1.5 if signal == 'stop' else -20),
                    carla.Rotation(yaw=90)))
                signal_actors['release'].set_transform(carla.Transform(
                    carla.Location(x=0, y=-7.3, z=1.5 if signal == 'release' else -20),
                    carla.Rotation(yaw=90)))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native frame mismatch')
                if first_time is None:
                    first_time = snap.timestamp.elapsed_seconds - .05
                time_s = (index + 1) / 20
                if abs(snap.timestamp.elapsed_seconds - first_time - time_s) > .001:
                    raise RuntimeError('Native 20 Hz timing differs')
                pipeline.capture(native_frame, time_s)
                camera_frames = {}
                for name, stream in camera_queues.items():
                    image = stream.get(timeout=30)
                    while image.frame < native_frame:
                        image = stream.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Native camera/frame join differs')
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s,
                    camera_native_frames=camera_frames)
                pose = motorcycle.get_transform()
                speed = motorcycle.get_velocity()
                body = motorcycle.bounding_box.get_world_vertices(pose)
                row = {'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'source_kind': 'original_native',
                    'motorcycle_actor_id': motorcycle.id,
                    'motorcycle_blueprint': motorcycle.type_id,
                    'motorcycle_xyz_m': [pose.location.x, pose.location.y,
                                         pose.location.z],
                    'motorcycle_body_vertices_m': [[v.x, v.y, v.z] for v in body],
                    'motorcycle_speed_mps': math.sqrt(
                        speed.x**2 + speed.y**2 + speed.z**2),
                    'flagger_actor_id': flagger.id,
                    'zone_entry_marker_actor_id': zone_markers[0].id,
                    'zone_exit_marker_actor_id': zone_markers[1].id,
                    'work_area_actor_ids': [actor.id for actor in work_area],
                    'flagger_xyz_m': [flagger.get_location().x,
                                      flagger.get_location().y,
                                      flagger.get_location().z],
                    'requested_signal': signal,
                    'stop_signal_actor_id': signal_actors['stop'].id,
                    'release_signal_actor_id': signal_actors['release'].id,
                    'signal_governance_and_visibility_review': 'pending',
                    'zone_designation_and_authority_review': 'pending',
                    'source_cameras': camera_frames}
                rows.write(json.dumps(row, allow_nan=False) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            if process.wait(timeout=180):
                raise RuntimeError('Original camera encoding failed: ' + name +
                                   ': ' + error.decode()[-300:])
        source_names = ['road.xodr', 'native-rows.jsonl',
                        'video_frames.jsonl', 'original-flagger-review.json']
        source_names.extend(REVIEW_COPIES.values())
        source_names.extend(name + '.mkv' for name in config['cameras'])
        (output / 'captured-source-hashes.json').write_text(json.dumps({
            'source_kind': 'original_native_capture',
            'case_id': config['case_id'],
            'sha256': {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                       for name in source_names},
            'original_signal_pixels_reviewed': False,
            'physical_or_legal_outcome_claimed': False}, indent=2) + '\n')
        complete = True
        return {'frames': 600, 'camera_names': list(camera_queues),
                'flagger_authority_and_visibility_verified': False,
                'physical_or_legal_outcome_claimed': False}
    finally:
        restoration = _cleanup_capture(pipeline, encoders, owned, client, prior,
                                       changed, complete, restore)
        if complete:
            seal_capture(output, frames=600, restoration=restoration, errors=[],
                encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                context={'case_id': config['case_id'],
                         'candidate_id': config['candidate_id'],
                         'flagger_authority_review': 'pending'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case', choices=('probe_a', 'probe_b'))
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    else:
        selected = Path(__file__).resolve().parent / 'selected-case.json'
        suffix = json.loads(selected.read_text())['suffix'] if selected.is_file() else None
        if args.case and suffix and args.case != suffix:
            raise SystemExit('Native request selected another exact case')
        suffix = suffix or args.case
        if not suffix or not args.output_dir:
            raise SystemExit('Original capture requires selected case and attempt directory')
        print(json.dumps(capture(args.output_dir, suffix, args.host, args.port)))
