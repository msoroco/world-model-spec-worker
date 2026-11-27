"""Capture original same-tick crossing, crossinger, driver and four-camera sources."""
from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess

from reviewed_site import load_review
from countdown_crossing import in_polygon, near

CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def _camera(world, carla, pose: dict, name: str, queue: Queue):
    width, height = CAMERAS[name]
    blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
    blueprint.set_attribute('image_size_x', str(width))
    blueprint.set_attribute('image_size_y', str(height))
    blueprint.set_attribute('sensor_tick', '0.05')
    xyz, pyr = pose['location_xyz_m'], pose['pitch_yaw_roll_deg']
    actor = world.try_spawn_actor(blueprint, carla.Transform(carla.Location(*xyz),
        carla.Rotation(pitch=pyr[0], yaw=pyr[1], roll=pyr[2])))
    if actor is None:
        raise RuntimeError('original countdown camera spawn failed: ' + name)
    actor.listen(lambda image: queue.put(image))
    return actor


def _encoder(path: Path, width: int, height: int):
    return subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'rawvideo', '-pixel_format', 'bgra', '-video_size', f'{width}x{height}',
        '-framerate', '20', '-i', 'pipe:0', '-c:v', 'ffv1', str(path)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _frame(queue: Queue, expected: int):
    try:
        image = queue.get(timeout=15)
    except Empty as error:
        raise RuntimeError('synchronized countdown camera frame missing') from error
    if image.frame != expected:
        raise ValueError('original countdown camera frame identity differs')
    return image


def _sample(sample: dict, frame: int, time_s: float, review: dict) -> dict:
    required = ('signal_form', 'illuminated', 'flashing', 'countdown_present',
                'countdown_value', 'signal_facing_direction',
                'pedestrian_xyz_m', 'observation_source',
                'signal_actor_id', 'pedestrian_pose_source_sha256',
                'signal_readback_source_sha256', 'exception_context')
    if not isinstance(sample, dict) or any(key not in sample for key in required):
        raise ValueError('original countdown adapter observation incomplete')
    if (sample['signal_form'] not in ('dont_walk', 'wait', 'upraised_hand', 'none') or
            sample['signal_facing_direction'] not in ('forward', 'reverse', 'both') or
            any(type(sample[key]) is not bool for key in
                ('illuminated', 'flashing', 'countdown_present')) or
            (sample['countdown_present'] and
                (type(sample['countdown_value']) is not int or sample['countdown_value'] < 0)) or
            (not sample['countdown_present'] and sample['countdown_value'] is not None)):
        raise ValueError('original signal form, flashing or numeric countdown readback invalid')
    if sample['signal_actor_id'] != review['sources']['pedestrian_signal']['actor_id'] or sample['observation_source'] != 'original_native_snapshot':
        raise ValueError('official original pedestrian signal actor readback differs')
    xyz = sample['pedestrian_xyz_m']
    if not isinstance(xyz, list) or len(xyz) != 3 or any(
            type(value) not in (int, float) or not math.isfinite(value) for value in xyz):
        raise ValueError('original pedestrian transform missing')
    if not sample['pedestrian_pose_source_sha256'] or not sample['signal_readback_source_sha256'] or not isinstance(sample['exception_context'], dict):
        raise ValueError('original countdown source provenance missing')
    return {'original_frame': frame, 'time_s': time_s,
            'position_m': xyz, 'pedestrian_xy': xyz[:2],
            'pedestrian_id': review['sources']['pedestrian_route']['pedestrian_actor_id'],
            'site_source_sha256': review['review']['sources']['pedestrian_signal']['sha256'],
            'source_sha256': sample['signal_readback_source_sha256'],
            'signal_readback_sha256': sample['signal_readback_source_sha256'],
            'pedestrian_pose_sha256': sample['pedestrian_pose_source_sha256'],
            **sample}


def run_native(packet, source_root, adapter_module, case_id, output_dir, speed,
               *, host='127.0.0.1', port=2000):
    """Require reviewed sources before world mutation and seal 900 original rows."""
    output = Path(output_dir).resolve()
    forbidden = {'trace.jsonl', 'video_frames.jsonl', 'original-countdown-observations.json',
                 'original-countdown-receipt.json', 'result.json'}
    if not output.is_dir() or any((output / name).exists() for name in forbidden):
        raise ValueError('fresh materialized crossing attempt directory required')
    reviewed = load_review(packet, source_root, case_id)
    adapter = importlib.import_module(adapter_module)
    for name in ('validate_review', 'configure', 'sample', 'teardown'):
        if not callable(getattr(adapter, name, None)):
            raise ValueError('original countdown adapter protocol missing: ' + name)
    adapter.validate_review(reviewed, case_id)
    if 'SCENARIO_PIPELINE_OUTPUT_ROOT' not in os.environ:
        os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(output.parent / 'pipeline-output')
    import carla
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    client = carla.Client(host, port)
    client.set_timeout(30)
    prior = snapshot(client)
    cameras, encoders, queues = {}, {}, {}
    frame_map = None
    handle = None
    failure = None
    restored = False
    try:
        world = client.generate_opendrive_world(reviewed['sources']['opendrive'])
        map_sha = hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
        if map_sha != reviewed['review']['sources']['opendrive']['sha256']:
            raise ValueError('original crossing Native map readback differs')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        handle = adapter.configure(world, reviewed, case_id, speed)
        for name, dimensions in CAMERAS.items():
            queues[name] = Queue()
            cameras[name] = _camera(world, carla, reviewed['sources']['cameras'][name],
                                    name, queues[name])
            encoders[name] = _encoder(output / (name + '.mkv'), *dimensions)
        frame_map = FrameMap(output / 'video_frames.jsonl')
        observations = []
        entered = False
        direction = 'reverse' if case_id.endswith('_reverse') else 'forward'
        target = reviewed['site']['crossing_routes'][direction]['waypoints_xy'][-1]
        with (output / 'trace.jsonl').open('x', buffering=1) as trace:
            for _ in range(900):
                frame = world.tick()
                time_s = float(world.get_snapshot().timestamp.elapsed_seconds)
                frame_map.append(frame, time_s)
                raw = adapter.sample(world, handle, frame, time_s)
                observation = _sample(raw, frame, time_s, reviewed)
                inside = in_polygon(observation['pedestrian_xy'],
                    reviewed['site']['highway_polygon_xy'])
                entered = entered or inside
                observation['in_highway'] = inside
                observation['crossing_complete'] = (entered and not inside and
                    near(observation['pedestrian_xy'], target))
                observations.append(observation)
                trace.write(json.dumps({'frame': frame, 'time_s': time_s,
                    'actor_id': reviewed['sources']['pedestrian_route'].get('pedestrian_actor_id'),
                    'position_m': raw.get('pedestrian_xyz_m')}, allow_nan=False) + '\n')
                for name in CAMERAS:
                    encoders[name].stdin.write(bytes(_frame(queues[name], frame).raw_data))
        for process in encoders.values():
            process.stdin.close()
            if process.wait(timeout=120) != 0:
                raise RuntimeError('four-view crossing encoder failed')
        frame_map.close()
        packet_data = {'assignment_id': reviewed['review']['assignment_id'],
            'case_id': case_id, 'original_trace_id': 'Native:' + sha(output / 'trace.jsonl'),
            'pedestrian_actor_id': reviewed['sources']['pedestrian_route'].get('pedestrian_actor_id'),
            'crossing_id': reviewed['sources']['crossing']['crossing_id'],
            'signal_actor_id': reviewed['sources']['pedestrian_signal']['actor_id'],
            'site': reviewed['site'],
            'site_source_sha256': reviewed['review']['sources']['highway']['sha256'],
            'signal_source_sha256': reviewed['review']['sources']['pedestrian_signal']['sha256'],
            'diagnostic_fixture': False,
            'frames': observations}
        _write(output / 'original-countdown-observations.json', packet_data)
        _write(output / 'original-countdown-receipt.json', {'case_id': case_id,
            'fps': 20, 'frame_count': 900, 'diagnostic_fixture': False,
            'source_sha256': sha(output / 'original-countdown-observations.json'),
            'review_sha256': reviewed['packet_sha256']})
    except BaseException as error:
        failure = error
    finally:
        if frame_map is not None and not frame_map.stream.closed:
            frame_map.close()
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for camera in cameras.values():
            try:
                camera.stop()
            finally:
                camera.destroy()
        if handle is not None:
            try:
                adapter.teardown(handle)
            except BaseException as error:
                failure = failure or error
        try:
            restored = bool(restore(client, prior)['restored'])
        except BaseException as error:
            failure = failure or error
    _write(output / 'native-run-status.json', {'restored': restored,
        'capture_complete': failure is None, 'errors': [repr(failure)] if failure else []})
    if failure or not restored:
        raise RuntimeError('original countdown capture or restoration failed') from failure
    _write(output / 'acquisition-provenance.json', {'provenance_kind': 'native',
        'diagnostic_fixture': False, 'case_id': case_id,
        'review_sha256': reviewed['packet_sha256']})
    seal_capture(output, frames=900, restoration={'restored': True}, errors=[],
        encoder_exit_codes={name: 0 for name in CAMERAS},
        context={'case_id': case_id, 'review_sha256': reviewed['packet_sha256'],
                 'legal_verdict_claimed': False})
    return {'case_id': case_id, 'frame_count': 900, 'restored': True,
            'original_crossing_source_sha256': sha(output / 'original-countdown-observations.json'),
            'physical_acceptance': False}
