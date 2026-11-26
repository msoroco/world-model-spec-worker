"""Capture original same-tick railroad, ego/other vehicle and four cameras."""
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
        raise RuntimeError('original railroad parking camera spawn failed: ' + name)
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
        raise RuntimeError('synchronized railroad parking camera frame missing') from error
    if image.frame != expected:
        raise ValueError('original railroad parking camera frame identity differs')
    return image


def _sample(sample: dict, frame: int, time_s: float, review: dict) -> dict:
    required = ('vehicle_action', 'vehicle_footprint_m', 'ego_xyz_m',
                'ego_speed_mps', 'other_vehicle_xyz_m', 'other_vehicle_speed_mps',
                'other_vehicle_actor_id', 'observation_source')
    if not isinstance(sample, dict) or any(key not in sample for key in required):
        raise ValueError('original railroad parking adapter observation incomplete')
    if sample['vehicle_action'] not in ('approach', 'stop', 'stand', 'park'):
        raise ValueError('original vehicle action missing')
    if sample['observation_source'] != 'original_native_snapshot':
        raise ValueError('original Native snapshot readback required')
    if sample['other_vehicle_actor_id'] != review['sources']['other_vehicle_plan']['vehicle_actor_id']:
        raise ValueError('distinct other vehicle identity differs')
    for xyz in (sample['ego_xyz_m'], sample['other_vehicle_xyz_m']):
        if (not isinstance(xyz, list) or len(xyz) != 3 or
                any(type(value) not in (int, float) or not math.isfinite(value) for value in xyz)):
            raise ValueError('original vehicle transform invalid')
    for name in ('ego_speed_mps', 'other_vehicle_speed_mps'):
        if type(sample[name]) not in (int, float) or not math.isfinite(sample[name]):
            raise ValueError('original vehicle speed invalid')
    from reviewed_site import nearest_distance
    nearest_distance(sample['vehicle_footprint_m'],
                     review['sources']['rail_inventory']['rail_polylines_m'])
    return {'frame': frame, 'time_s': time_s, **sample}


def run_native(packet, source_root, adapter_module, case_id, output_dir, speed,
               target_m, traffic_status,
               *, host='127.0.0.1', port=2000):
    """Require reviewed sources before world mutation and seal 900 original rows."""
    output = Path(output_dir).resolve()
    forbidden = {'trace.jsonl', 'video_frames.jsonl', 'original-rail-observations.json',
                 'original-rail-receipt.json', 'result.json'}
    if not output.is_dir() or any((output / name).exists() for name in forbidden):
        raise ValueError('fresh materialized railroad parking attempt directory required')
    reviewed = load_review(packet, source_root, case_id, target_m)
    spec = json.loads((output / 'case-spec.json').read_text())
    if (spec['requested_nearest_vehicle_to_rail_m'] != target_m or
            spec['requested_traffic_conflict_necessity_status'] != traffic_status or
            reviewed['sources']['exception_review']['traffic_conflict_necessity'] != traffic_status):
        raise ValueError('reviewed original rail/exception status differs from selected case')
    adapter = importlib.import_module(adapter_module)
    for name in ('validate_review', 'configure', 'sample', 'teardown'):
        if not callable(getattr(adapter, name, None)):
            raise ValueError('original railroad parking adapter protocol missing: ' + name)
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
            raise ValueError('original railroad parking Native map readback differs')
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
                    'actor_id': reviewed['sources']['ego_plan'].get('ego_actor_id'),
                    'position_m': raw.get('ego_xyz_m')}, allow_nan=False) + '\n')
                for name in CAMERAS:
                    encoders[name].stdin.write(bytes(_frame(queues[name], frame).raw_data))
        for process in encoders.values():
            process.stdin.close()
            if process.wait(timeout=120) != 0:
                raise RuntimeError('four-view railroad parking encoder failed')
        frame_map.close()
        ego = reviewed['sources']['ego_plan']
        packet_data = {'assignment_id': reviewed['review']['assignment_id'],
            'case_id': case_id, 'original_trace_id': 'Native:' + sha(output / 'trace.jsonl'),
            'vehicle_actor_id': ego['ego_actor_id'], 'vehicle_action': 'park',
            'vehicle_footprint_m': observations[-1]['vehicle_footprint_m'],
            'rail_polylines_m': reviewed['sources']['rail_inventory']['rail_polylines_m'],
            'exception_context': {key: reviewed['sources']['exception_review'][key]
                for key in ('traffic_conflict_necessity', 'law_compliance',
                            'officer_direction', 'official_device_direction')},
            'site_source_sha256': reviewed['packet_sha256'],
            'site': {'railroad_identity': reviewed['sources']['rail_inventory']['railroad_identity'],
                'carrier_provenance': reviewed['sources']['rail_inventory']['carrier_provenance'],
                'other_vehicle_actor_id': reviewed['sources']['other_vehicle_plan']['vehicle_actor_id']},
            'frames': observations}
        _write(output / 'original-rail-observations.json', packet_data)
        _write(output / 'original-rail-receipt.json', {'case_id': case_id,
            'fps': 20, 'frame_count': 900, 'diagnostic_fixture': False,
            'source_sha256': sha(output / 'original-rail-observations.json'),
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
        raise RuntimeError('original railroad parking capture or restoration failed') from failure
    _write(output / 'acquisition-provenance.json', {'provenance_kind': 'native',
        'diagnostic_fixture': False, 'case_id': case_id,
        'review_sha256': reviewed['packet_sha256']})
    seal_capture(output, frames=900, restoration={'restored': True}, errors=[],
        encoder_exit_codes={name: 0 for name in CAMERAS},
        context={'case_id': case_id, 'review_sha256': reviewed['packet_sha256'],
                 'legal_verdict_claimed': False})
    return {'case_id': case_id, 'frame_count': 900, 'restored': True,
            'original_rail_source_sha256': sha(output / 'original-rail-observations.json'),
            'physical_acceptance': False}
