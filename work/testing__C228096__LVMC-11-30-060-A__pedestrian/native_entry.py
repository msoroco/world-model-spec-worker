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
        raise RuntimeError('original crossing camera spawn failed: ' + name)
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
        raise RuntimeError('synchronized crossing camera frame missing') from error
    if image.frame != expected:
        raise ValueError('original crossing camera frame identity differs')
    return image


def _sample(sample: dict, frame: int, time_s: float, review: dict) -> dict:
    required = ('pedestrian_on_roadway', 'pedestrian_yield_observed',
                'vehicles_on_roadway', 'pedestrian_xyz_m',
                'vehicle_positions_xyz_m', 'observation_source')
    if not isinstance(sample, dict) or any(key not in sample for key in required):
        raise ValueError('original crossing adapter observation incomplete')
    if any(type(sample[key]) is not bool for key in required[:2]):
        raise ValueError('original crossing adapter boolean readback missing')
    if (not isinstance(sample['vehicles_on_roadway'], list)
            or any(not isinstance(actor, str) or not actor for actor in sample['vehicles_on_roadway'])
            or not set(sample['vehicles_on_roadway']) <= set(
                review['sources']['vehicle_routes']['vehicle_actor_ids'])):
        raise ValueError('original roadway vehicle inventory differs')
    if sample['observation_source'] != 'original_native_snapshot':
        raise ValueError('original Native snapshot readback required')
    pedestrian_xyz = sample['pedestrian_xyz_m']
    if (not isinstance(pedestrian_xyz, list) or len(pedestrian_xyz) != 3
            or any(type(value) not in (int, float) or not math.isfinite(value)
                   for value in pedestrian_xyz)):
        raise ValueError('original pedestrian transform missing')
    positions = sample['vehicle_positions_xyz_m']
    if (not isinstance(positions, dict) or
            any(actor_id not in positions for actor_id in sample['vehicles_on_roadway'])):
        raise ValueError('original roadway vehicle trajectories missing')
    for xyz in positions.values():
        if (not isinstance(xyz, list) or len(xyz) != 3 or
                any(type(value) not in (int, float) or not math.isfinite(value) for value in xyz)):
            raise ValueError('original vehicle transform invalid')
    return {'frame': frame, 'time_s': time_s, **sample}


def run_native(packet, source_root, adapter_module, case_id, output_dir, speed,
               *, host='127.0.0.1', port=2000):
    """Require reviewed sources before world mutation and seal 900 original rows."""
    output = Path(output_dir).resolve()
    forbidden = {'trace.jsonl', 'video_frames.jsonl', 'original-crossing-observations.json',
                 'original-crossing-receipt.json', 'result.json'}
    if not output.is_dir() or any((output / name).exists() for name in forbidden):
        raise ValueError('fresh materialized crossing attempt directory required')
    reviewed = load_review(packet, source_root, case_id)
    spec = json.loads((output / 'case-spec.json').read_text())
    if reviewed['sources']['prohibited_place']['prohibited_place_under_11_30_070'] is not spec[
            'requested_prohibited_place_under_11_30_070']:
        raise ValueError('reviewed original prohibited-place status differs from selected case')
    adapter = importlib.import_module(adapter_module)
    for name in ('validate_review', 'configure', 'sample', 'teardown'):
        if not callable(getattr(adapter, name, None)):
            raise ValueError('original crossing adapter protocol missing: ' + name)
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
        with (output / 'trace.jsonl').open('x', buffering=1) as trace:
            for _ in range(900):
                frame = world.tick()
                time_s = float(world.get_snapshot().timestamp.elapsed_seconds)
                frame_map.append(frame, time_s)
                raw = adapter.sample(world, handle, frame, time_s)
                observation = _sample(raw, frame, time_s, reviewed)
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
        route = reviewed['sources']['pedestrian_route']
        packet_data = {'assignment_id': reviewed['review']['assignment_id'],
            'case_id': case_id, 'original_trace_id': 'Native:' + sha(output / 'trace.jsonl'),
            'pedestrian_actor_id': route['pedestrian_actor_id'],
            'site_source_sha256': reviewed['packet_sha256'],
            'site': {'roadway_id': route['roadway_id'],
                'crossing_point_id': route['crossing_point_id'],
                'within_marked_crosswalk': False,
                'within_unmarked_intersection_crosswalk': False,
                'prohibited_place_under_11_30_070': reviewed['sources']['prohibited_place'][
                    'prohibited_place_under_11_30_070']},
            'frames': observations}
        _write(output / 'original-crossing-observations.json', packet_data)
        _write(output / 'original-crossing-receipt.json', {'case_id': case_id,
            'fps': 20, 'frame_count': 900, 'diagnostic_fixture': False,
            'source_sha256': sha(output / 'original-crossing-observations.json'),
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
        raise RuntimeError('original crossing capture or restoration failed') from failure
    _write(output / 'acquisition-provenance.json', {'provenance_kind': 'native',
        'diagnostic_fixture': False, 'case_id': case_id,
        'review_sha256': reviewed['packet_sha256']})
    seal_capture(output, frames=900, restoration={'restored': True}, errors=[],
        encoder_exit_codes={name: 0 for name in CAMERAS},
        context={'case_id': case_id, 'review_sha256': reviewed['packet_sha256'],
                 'legal_verdict_claimed': False})
    return {'case_id': case_id, 'frame_count': 900, 'restored': True,
            'original_crossing_source_sha256': sha(output / 'original-crossing-observations.json'),
            'physical_acceptance': False}
