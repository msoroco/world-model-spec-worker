"""Unaccepted original-source capture for the staged signed-turn cells.

This module imports CARLA only when an operator launches an owned attempt.
The authored route controls the actor; saved Native pose and original pixels
remain the only possible evidence of realized movement and device visibility.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import traceback

from geometry import FRAMES, RATE_HZ
from native_plan import command_from_observation, make_controller, survey_governed_sign


CAMERAS = (
    ('overview', 1920, 1080, (0, 0, 42), (0, -17, 0), False),
    ('approach', 1280, 720, (0, -23, 9), (0, -26, 0), False),
    ('reference_corner', 1280, 720, (7, -23, 6), (0, -24, 1), False),
    ('driver_reference', 1280, 720, (1, 0, 1.6), None, True),
)


def _runtime_imports():
    for parent in Path(__file__).resolve().parents:
        runtime = parent / 'runtime'
        if (runtime / 'python/pipeline_capture.py').is_file() and (runtime / 'scenario_pipeline').is_dir():
            sys.path[:0] = [str(runtime / 'python'), str(runtime / 'scenario_pipeline')]
            from pipeline_capture import PipelineCapture
            from worker_exchange.world_restore import snapshot, restore
            from worker_exchange.native_output import FrameMap, seal_capture
            from worker_exchange.media import compose_four_views
            return PipelineCapture, snapshot, restore, FrameMap, seal_capture, compose_four_views
    raise RuntimeError('Pinned runtime capture helpers unavailable')


def _camera_pose(carla, xyz, aim):
    if aim is None:
        return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                               carla.Rotation(pitch=-6))
    dx, dy, dz = (aim[i] - xyz[i] for i in range(3))
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(yaw=yaw, pitch=pitch))


def _body(actor):
    return [[v.x, v.y, v.z] for v in actor.bounding_box.get_world_vertices(actor.get_transform())]


def _json_new(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def execute(output_dir, host, port):
    import carla
    import numpy as np
    (PipelineCapture, snapshot, restore, FrameMap, seal_capture,
     compose_four_views) = _runtime_imports()
    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output / 'config.json').is_file():
        raise ValueError('A fresh materialized exact-case output is required')
    config, _ = make_controller(output, 1.4, 35)
    if config['source_kind'] != 'authored_cpu_route_plan' or config['delivery_ready'] is not False:
        raise ValueError('Staged source identity or unselected status differs')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    prior = client.get_world()
    if saved['settings'].synchronous_mode or [a for a in prior.get_actors()
            if a.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))]:
        raise RuntimeError('Requires exclusive idle asynchronous CARLA world')
    actors, encoders, logs, camera_queues = [], {}, {}, {}
    capture, frame_map, changed, restored = None, None, False, None
    error, frames = None, 0
    try:
        world = client.generate_opendrive_world((output / 'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=50,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        survey = survey_governed_sign(mapping, carla, config)
        survey['native_map_sha256'] = hashlib.sha256(mapping.to_opendrive().encode()).hexdigest()
        _json_new(output / 'sign-survey.json', survey)
        shutil.copyfile(output / 'road.xodr', output / 'authored-road.xodr')
        blueprint = world.get_blueprint_library().find('vehicle.bh.crossbike')
        blueprint.set_attribute('role_name', 'c104538_staged_signed_turn')
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=0, y=-45, z=.7), carla.Rotation(yaw=90)))
        actors.append(ego)
        ego.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
        for _ in range(40):
            world.tick()
        wheels = ego.get_physics_control().wheels
        if len(wheels) < 2:
            raise RuntimeError('Native bicycle wheel geometry unavailable')
        wheelbase = (max(w.position.x for w in wheels) - min(w.position.x for w in wheels)) / 100
        max_steer = max(w.max_steer_angle for w in wheels)
        _, controller = make_controller(output, wheelbase, max_steer)
        _json_new(output / 'native-construction-context.json', {
            'case_id': config['case_id'], 'blueprint': ego.type_id,
            'wheelbase_m': wheelbase, 'max_steer_deg': max_steer,
            'authored_route_sha256': config['source_sha256'],
            'official_sign_authorization': 'unreviewed',
            'physical_turn': 'unreviewed'})
        for name, width, height, xyz, aim, attached in CAMERAS:
            camera_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 90), ('sensor_tick', 0)):
                camera_bp.set_attribute(key, str(value))
            camera = world.spawn_actor(camera_bp, _camera_pose(carla, xyz, aim),
                                       attach_to=ego if attached else None)
            actors.append(camera)
            camera_queues[name] = queue.Queue()
            camera.listen(camera_queues[name].put)
            logs[name] = (output / (name + '.encoder.log')).open('x')
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                '-r', str(RATE_HZ), '-i', 'pipe:0', '-an', '-c:v', 'ffv1',
                '-level', '1', str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=logs[name])
        capture = PipelineCapture(client, ego, output, config['case_id'],
                                  visibility=False, required_observations=[])
        frame_map = FrameMap(output / 'video_frames.jsonl')
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / 'native_samples.jsonl').open('x') as native_stream, \
             (output / 'rider_native_samples.jsonl').open('x') as rider_stream, \
             (output / 'body_history.jsonl').open('x') as body_stream:
            for index in range(FRAMES):
                before = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                command = command_from_observation(controller,
                    [before.location.x, before.location.y], before.rotation.yaw, speed)
                ego.apply_control(carla.VehicleControl(throttle=command['throttle'],
                    brake=command['brake'], steer=command['steer'],
                    hand_brake=command['hand_brake']))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = ego.get_transform()
                lane = mapping.get_waypoint(pose.location, project_to_road=False,
                                            lane_type=carla.LaneType.Driving)
                if lane is None:
                    raise RuntimeError('Native rider lane readback missing')
                body = _body(ego)
                sample = {'native_frame': frame, 'time_s': time_s,
                          'native_center_xy_m': [pose.location.x, pose.location.y],
                          'native_heading_deg': pose.rotation.yaw,
                          'native_road_id': lane.road_id, 'native_lane_id': lane.lane_id,
                          'native_body_vertices_m': body,
                          'controller_request': command}
                capture.capture(frame, time_s, extra={'staged_signed_turn_native': sample})
                native_stream.write(json.dumps(sample, allow_nan=False) + '\n')
                rider_stream.write(json.dumps({'frame': index, 'time_s': time_s,
                    'actor_id': ego.id, 'machine_class': 'bicycle',
                    'mounted': None, 'posture_source': 'original_pixel_review_pending',
                    'observed_turn': None, 'turn_source': 'saved_geometry_review_pending',
                    'sign_id': survey['landmark_id']}, allow_nan=False) + '\n')
                body_stream.write(json.dumps({'frame': frame, 'time_s': time_s,
                    'body_vertices_m': body}, allow_nan=False) + '\n')
                for name, width, height, *_ in CAMERAS:
                    image = camera_queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = camera_queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera/Native frame join failed')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                frame_map.append(frame, time_s)
                frames += 1
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        if frame_map is not None:
            frame_map.close()
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        encoder_codes = {}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                encoder_codes[name] = encoder.wait(timeout=180)
                if encoder_codes[name] != 0:
                    raise RuntimeError('Lossless camera encoder failed: ' + name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            logs[name].close()
        for actor in reversed(actors):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'actor_cleanup_error': str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {'world_restore_error': str(exc)}
        if error is None and frames == FRAMES:
            try:
                cameras = {name: output / (name + '.mkv') for name, *_ in CAMERAS}
                composed = compose_four_views(cameras, output / 'video_frames.jsonl',
                                              output / 'raw.mkv')
                _json_new(output / 'four-view-receipt.json', composed)
                seal_capture(output, frames=frames, restoration=restored, errors=[],
                             encoder_exit_codes=encoder_codes,
                             context={'case_id': config['case_id'],
                                      'physical_acceptance_claimed': False})
            except BaseException as exc:
                error = {'seal_or_composition_error': str(exc)}
        _json_new(output / 'native-capture-report.json', {
            'case_id': config['case_id'], 'frames': frames, 'expected_frames': FRAMES,
            'camera_encoder_exit_codes': encoder_codes, 'restoration': restored,
            'error': error, 'accepted': False, 'sign_authorization': 'unreviewed',
            'original_pixel_review': 'pending', 'saved_processing': 'pending'})
    if error:
        raise RuntimeError('Native attempt failed; see native-capture-report.json')
