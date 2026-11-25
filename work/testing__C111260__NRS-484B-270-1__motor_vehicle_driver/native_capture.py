"""Own an exact bicycle encounter capture without choosing a legal outcome.

The source-reviewed site, camera builder and CARLA API are injected. Original
events, frame identities and PNGs are written once under a fresh local attempt.
"""
from __future__ import annotations

from copy import copy
import json
import math
from pathlib import Path
import queue
import shutil

from bicycle_encounter import ASSIGNMENT, CASE_VARIANTS, MODES, construct_native, require, verify_site
from encounter_control import command
from saved_attempt import VIEWS


SIZES = {'overview': (1920, 1080), 'approach': (1280, 720),
         'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def build_cameras(world, carla, site, actors):
    """Spawn source-specified four-view RGB sensors with local ownership."""
    poses = site.get('camera_poses')
    require(isinstance(poses, dict) and set(poses) == set(VIEWS),
            'four source-reviewed camera poses required')
    library = world.get_blueprint_library()
    sensors = {}
    try:
        for view, (width, height) in SIZES.items():
            pose = poses[view]
            require(pose.get('attachment') in ('world', 'ego') and
                    all(isinstance(pose.get(key), (int, float)) and
                        math.isfinite(pose[key]) for key in
                        ('x', 'y', 'z', 'pitch', 'yaw', 'roll', 'fov_deg')) and
                    0 < pose['fov_deg'] <= 180,
                    'invalid original camera pose: ' + view)
            blueprint = library.find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('sensor_tick', '.05')
            blueprint.set_attribute('fov', str(pose['fov_deg']))
            transform = carla.Transform(
                carla.Location(x=pose['x'], y=pose['y'], z=pose['z']),
                carla.Rotation(pitch=pose['pitch'], yaw=pose['yaw'], roll=pose['roll']))
            parent = actors[0] if pose['attachment'] == 'ego' else None
            sensor = world.spawn_actor(blueprint, transform, attach_to=parent)
            require(sensor is not None, 'original camera spawn failed: ' + view)
            sensors[view] = sensor
        return sensors
    except Exception:
        for sensor in sensors.values():
            try:
                sensor.stop()
            finally:
                sensor.destroy()
        raise


def _position(actor):
    loc = actor.get_location()
    xy = [float(loc.x), float(loc.y)]
    require(all(math.isfinite(value) for value in xy), 'nonfinite Native actor pose')
    return xy


def _speed(actor):
    vector = actor.get_velocity()
    value = math.hypot(float(vector.x), float(vector.y))
    require(math.isfinite(value), 'nonfinite Native rider speed')
    return value


def run(world, carla, site, site_root, attempt, mode, camera_builder=build_cameras,
        *, frames=900, camera_timeout_s=5.0, case_id=None):
    """Capture one original 20 Hz attempt; restore settings and owned actors.

    The caller must encode the saved PNGs, create the sealed source index and
    run saved delivery processing after this returns. `camera_builder` receives
    the verified site and actors and must return four new sensor actors.
    """
    require(mode in MODES, 'wrong exact encounter mode')
    require(isinstance(frames, int) and frames >= 3, 'invalid frame count')
    selected = case_id or ASSIGNMENT + '__' + mode
    suffix = selected.removeprefix(ASSIGNMENT + '__')
    require(suffix in CASE_VARIANTS and
            CASE_VARIANTS[suffix]['mode'] == mode and
            CASE_VARIANTS[suffix]['rider_kind'] == site.get('rider_kind') and
            site.get('case_id') == selected,
            'source site exact case or rider modality mismatch')
    require(isinstance(site.get('camera_poses'), dict) and
            set(site['camera_poses']) == set(VIEWS),
            'four source-reviewed camera poses required')
    require(isinstance(site.get('rider_throttle'), (int, float)) and
            0 < site['rider_throttle'] <= 1,
            'source-reviewed rider control missing')
    verify_site(site, site_root)
    attempt = Path(attempt)
    require(not attempt.exists(), 'new Native attempt directory required')
    original_settings = copy(world.get_settings())
    original_weather = world.get_weather()
    actors = []
    sensors = {}
    restored = False
    completed = False
    return_value = None
    try:
        settings = copy(original_settings)
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        built = construct_native(site, site_root, world, carla, mode)
        actors = built['actors']
        sensors = camera_builder(world, carla, site, actors)
        require(isinstance(sensors, dict) and set(sensors) == set(VIEWS) and
                len({sensor.id for sensor in sensors.values()}) == 4,
                'four distinct original camera sensors required')
        queues = {view: queue.Queue() for view in VIEWS}
        for view, sensor in sensors.items():
            sensor.listen(queues[view].put)
        attempt.mkdir(parents=True)
        from worker_exchange.native_output import FrameMap
        frame_writer = FrameMap(attempt / 'video_frames.jsonl')
        rows = []
        frame_map = []
        previous_frame = None
        first_time = None
        for number in range(frames):
            ego_xy = _position(actors[0])
            rider_xy = _position(actors[1])
            rider_speed = _speed(actors[1])
            action = command(site, site_root, mode, ego_xy, rider_xy,
                             rider_speed, number / 20)
            target = action['target_speed_mps']
            ego_speed = _speed(actors[0])
            throttle = .35 if target > ego_speed + .25 else 0.0
            brake = 1.0 if target == 0 else 0.0
            actors[0].apply_control(carla.VehicleControl(throttle=throttle,
                                                         brake=brake, steer=0.0))
            actors[1].apply_control(carla.VehicleControl(
                throttle=float(site['rider_throttle']), brake=0.0, steer=0.0))
            frame = int(world.tick())
            timestamp = float(world.get_snapshot().timestamp.elapsed_seconds)
            if first_time is None:
                first_time = timestamp
            elapsed = timestamp - first_time
            require((previous_frame is None or frame == previous_frame + 1) and
                    math.isfinite(elapsed) and abs(elapsed - number / 20) < 1e-4,
                    'Native original 20 Hz frame identity/time mismatch')
            previous_frame = frame
            for view, (width, height) in SIZES.items():
                try:
                    image = queues[view].get(timeout=camera_timeout_s)
                except queue.Empty as exc:
                    raise ValueError('original camera frame missing: ' + view) from exc
                require(image.frame == frame and
                        (image.width, image.height) == (width, height),
                        'original camera frame identity/dimensions mismatch: ' + view)
                path = attempt / 'camera-originals' / view / f'{frame:08d}.png'
                path.parent.mkdir(parents=True, exist_ok=True)
                image.save_to_disk(str(path))
                require(path.is_file() and path.stat().st_size > 0,
                        'original camera PNG save failed: ' + view)
            rows.append({'frame': frame, 'camera_frame': frame,
                         'ego_id': site['ego_actor_id'],
                         'rider_id': site['rider_actor_id'],
                         'ego_native_id': actors[0].id,
                         'rider_native_id': actors[1].id,
                         'ego_blueprint_id': site['ego_blueprint_id'],
                         'rider_blueprint_id': site['bicycle_blueprint_id'],
                         'mode_command': mode, 'command_source': 'controller_log',
                         'target_speed_mps': target,
                         'ego_speed_mps': _speed(actors[0]),
                         'rider_visual_present': False,
                         'ego_xy': _position(actors[0]),
                         'rider_xy': _position(actors[1]),
                         'legal_verdict': None})
            frame_map.append(frame_writer.append(frame, elapsed))
        frame_writer.close()
        (attempt / 'events.json').write_text(json.dumps(rows, separators=(',', ':')) + '\n',
                                             encoding='utf-8')
        (attempt / 'trace.jsonl').write_text(''.join(
            json.dumps({'frame': event['frame'], 'time_s': mapping['time_s'],
                        'position_m': event['ego_xy'],
                        'position': {'x': event['ego_xy'][0],
                                     'y': event['ego_xy'][1],
                                     'z': site['spawn_z_m']},
                        'heading_deg': site['ego_yaw_deg'],
                        'speed_mps': event['ego_speed_mps']},
                       separators=(',', ':')) + '\n'
            for event, mapping in zip(rows, frame_map)), encoding='utf-8')
        # Preserve the reviewed packet and its original references verbatim.
        source_root = Path(site_root).resolve()
        for ref in site['original_sources']:
            path = (source_root / ref['path']).resolve()
            require(path.is_relative_to(source_root), 'site source escapes root')
            destination = attempt / ref['path']
            require(not destination.exists(), 'duplicate site source path')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
        (attempt / 'site.json').write_text(json.dumps(site, indent=2) + '\n',
                                           encoding='utf-8')
        completed = True
        return_value = {'case_id': selected, 'frame_count': frames,
                        'first_native_frame': rows[0]['frame'],
                        'last_native_frame': rows[-1]['frame'],
                        'attempt': str(attempt), 'capture_complete': True}
    finally:
        if 'frame_writer' in locals():
            frame_writer.close()
        cleanup_errors = []
        for sensor in sensors.values():
            for method in ('stop', 'destroy'):
                try:
                    getattr(sensor, method)()
                except Exception as exc:
                    cleanup_errors.append(exc)
        for actor in reversed(actors):
            try:
                actor.destroy()
            except Exception as exc:
                cleanup_errors.append(exc)
        try:
            world.apply_settings(original_settings)
            world.set_weather(original_weather)
            readback = world.get_settings()
            restored = (readback.synchronous_mode == original_settings.synchronous_mode and
                        readback.fixed_delta_seconds == original_settings.fixed_delta_seconds and
                        world.get_weather() == original_weather)
            if not restored:
                raise ValueError('Native settings/weather restore readback differs')
        except Exception as exc:
            cleanup_errors.append(exc)
        if cleanup_errors and completed:
            raise RuntimeError('Native capture cleanup failed') from cleanup_errors[0]
    require(completed and restored and return_value is not None,
            'Native capture or restoration incomplete')
    return_value['restoration'] = {'restored': True,
                                    'settings_readback': 'synchronous mode and fixed delta verified',
                                    'weather_readback': 'original weather verified'}
    return return_value
