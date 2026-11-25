"""Own a reviewed C125763 CARLA capture, including sensors and world restore.

The site packet supplies original map, device and highway evidence plus four
camera poses. This runner cannot turn a fixture into reviewed original evidence.
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import math
from pathlib import Path
from queue import Empty, Queue

from PIL import Image

from native_construction import control_step, reviewed_scene, spawn_pair
from native_history_capture import CAMERAS, capture, audit_media


CASES = ('entry_below', 'entry_inside', 'entry_above')


def _pose(carla, pose):
    if not isinstance(pose, dict) or set(pose) != {'x', 'y', 'z', 'pitch', 'yaw', 'roll'}:
        raise ValueError('reviewed six-axis camera pose required')
    if any(type(value) not in (int, float) or not math.isfinite(value)
           for value in pose.values()):
        raise ValueError('reviewed camera pose must be finite')
    return carla.Transform(
        carla.Location(x=pose['x'], y=pose['y'], z=pose['z']),
        carla.Rotation(pitch=pose['pitch'], yaw=pose['yaw'], roll=pose['roll']))


def _cameras(world, carla, scene):
    poses = scene.get('camera_poses')
    dimensions = scene.get('camera_dimensions')
    if not isinstance(poses, dict) or set(poses) != set(CAMERAS):
        raise ValueError('four reviewed original camera poses required')
    if not isinstance(dimensions, dict) or set(dimensions) != set(CAMERAS):
        raise ValueError('four reviewed original camera dimensions required')
    for name in CAMERAS:
        _pose(carla, poses[name])
        size = dimensions[name]
        if (not isinstance(size, list) or len(size) != 2 or
                any(type(n) is not int or n < 2 for n in size)):
            raise ValueError('reviewed original camera dimensions invalid')
    return poses, dimensions


def run(world, carla, packet_path, output, case, *, frame_count=900,
        diagnostic_fixture=False):
    """Run one case; publish no success receipt until resources are released."""
    if case not in CASES or type(frame_count) is not int or frame_count < 2:
        raise ValueError('known crossing timing case and frame count required')
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('fresh empty output directory required')
    scene = reviewed_scene(packet_path, world)
    if not diagnostic_fixture and scene.get('review_status') != 'reviewed_original':
        raise ValueError('reviewed original Native site packet required')
    poses, dimensions = _cameras(world, carla, scene)
    releases = scene.get('release_s')
    if (not isinstance(releases, dict) or set(releases) != set(CASES) or
            any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
                for value in releases.values())):
        raise ValueError('three reviewed release schedules required')
    saved = copy.copy(world.get_settings())
    target = copy.copy(saved)
    target.synchronous_mode = True
    target.fixed_delta_seconds = .05
    pair = ()
    sensors = []
    queues = {}
    failure = None
    receipt = None
    cleanup_errors = []
    try:
        world.apply_settings(target)
        observed = world.get_settings()
        if observed.synchronous_mode is not True or observed.fixed_delta_seconds != .05:
            raise ValueError('synchronous 20 Hz settings readback failed')
        pair = spawn_pair(world, carla, scene)
        for name in CAMERAS:
            width, height = dimensions[name]
            blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('sensor_tick', '.05')
            blueprint.set_attribute('fov', '90')
            sensor = world.spawn_actor(blueprint, _pose(carla, poses[name]))
            if sensor is None:
                raise RuntimeError('original camera spawn failed: ' + name)
            sensors.append(sensor)
            inbox = Queue(maxsize=2)
            sensor.listen(inbox.put_nowait)
            queues[name] = inbox

        def read_camera(name, frame):
            try:
                image = queues[name].get(timeout=5)
            except Empty as error:
                raise ValueError('original camera callback missing: ' + name) from error
            width, height = dimensions[name]
            if image.frame != frame or image.width != width or image.height != height:
                raise ValueError('original camera frame identity or dimensions differ: ' + name)
            snapshot = world.get_snapshot()
            if abs(float(image.timestamp) - float(snapshot.timestamp.elapsed_seconds)) > .001:
                raise ValueError('original camera timestamp differs: ' + name)
            raw = bytes(image.raw_data)
            if len(raw) != width * height * 4:
                raise ValueError('original camera BGRA bytes incomplete: ' + name)
            rgb = Image.frombytes('RGBA', (width, height), raw, 'raw', 'BGRA').convert('RGB')
            buffer = io.BytesIO()
            rgb.save(buffer, format='PNG')
            return {'frame': frame, 'png_bytes': buffer.getvalue()}

        readers = {name: lambda frame, name=name: read_camera(name, frame)
                   for name in CAMERAS}
        start = float(world.get_snapshot().timestamp.elapsed_seconds)

        def before_tick(index):
            now = start + index * .05
            control_step(carla, pair[0], scene['ego_route'], now,
                         float(scene.get('ego_release_s', 0)))
            control_step(carla, pair[1], scene['other_route'], now, releases[case])

        receipt = capture(world, packet_path, pair[0], pair[1], output, frame_count,
                          camera_readers=readers, camera_dimensions=dimensions,
                          before_tick=before_tick)
        audit_media(output, camera_dimensions=dimensions)
    except BaseException as error:
        failure = error
    finally:
        for sensor in reversed(sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except BaseException as error:
                cleanup_errors.append('sensor release: ' + str(error))
        for actor in reversed(pair):
            try:
                actor.destroy()
            except BaseException as error:
                cleanup_errors.append('vehicle release: ' + str(error))
        try:
            world.apply_settings(saved)
            observed = world.get_settings()
            if (observed.synchronous_mode != saved.synchronous_mode or
                    observed.fixed_delta_seconds != saved.fixed_delta_seconds):
                cleanup_errors.append('world settings restoration readback failed')
        except BaseException as error:
            cleanup_errors.append('world settings restore: ' + str(error))
    if cleanup_errors:
        raise RuntimeError('; '.join(cleanup_errors)) from failure
    if failure is not None:
        raise failure
    return receipt


def main():
    parser = argparse.ArgumentParser(description='Capture one reviewed C125763 timing case')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--packet', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--case', choices=CASES, required=True)
    args = parser.parse_args()
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    print(json.dumps(run(client.get_world(), carla, args.packet, args.output, args.case),
                     sort_keys=True))


if __name__ == '__main__':
    main()
