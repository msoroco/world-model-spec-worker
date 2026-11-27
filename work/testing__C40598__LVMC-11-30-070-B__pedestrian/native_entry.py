"""Capture a complete source-gated business-district pedestrian crossing."""
from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
from pathlib import Path
from queue import Empty, Queue
import shutil
import subprocess

from crosswalk_site import classify_body, load_review, point_in_polygon

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
        raise RuntimeError('original business-district camera spawn failed: ' + name)
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
    required = ('pedestrian_on_roadway', 'pedestrian_xyz_m',
                'body_polygon_xy_m', 'curb_side', 'observation_source')
    if not isinstance(sample, dict) or any(key not in sample for key in required):
        raise ValueError('original pedestrian body adapter observation incomplete')
    if type(sample['pedestrian_on_roadway']) is not bool:
        raise ValueError('original pedestrian roadway state missing')
    if sample['observation_source'] != 'original_native_snapshot':
        raise ValueError('original Native snapshot readback required')
    if sample['curb_side'] not in ('start', 'roadway', 'opposite'):
        raise ValueError('original pedestrian curb-side readback missing')
    pedestrian_xyz = sample['pedestrian_xyz_m']
    if (not isinstance(pedestrian_xyz, list) or len(pedestrian_xyz) != 3
            or any(type(value) not in (int, float) or not math.isfinite(value)
                   for value in pedestrian_xyz)):
        raise ValueError('original pedestrian transform missing')
    body = sample['body_polygon_xy_m']
    if (not isinstance(body, list) or len(body) < 3 or
            any(not isinstance(vertex, list) or len(vertex) != 2 or
                any(type(value) not in (int, float) or not math.isfinite(value)
                    for value in vertex) for vertex in body)):
        raise ValueError('original pedestrian body polygon missing')
    roadway = review['sources']['roadway']['roadway_polygon_xy_m']
    if sample['pedestrian_on_roadway'] is not any(
            point_in_polygon(vertex, roadway) for vertex in body):
        raise ValueError('original roadway occupancy differs from full body')
    categories = classify_body(body, review['sources']['crosswalk_inventory'])
    return {'frame': frame, 'time_s': time_s,
            'actor_id': review['sources']['pedestrian_route']['pedestrian_actor_id'],
            **sample, 'crosswalk_body_overlap': categories}


def run_native(packet, source_root, adapter_module, case_id, output_dir, speed,
               *, host='127.0.0.1', port=2000):
    """Require reviewed district sources before mutation and seal 900 rows."""
    output = Path(output_dir).resolve()
    forbidden = {'trace.jsonl', 'video_frames.jsonl', 'original-crossing-observations.json',
                 'original-crossing-receipt.json', 'result.json'}
    if not output.is_dir() or any((output / name).exists() for name in forbidden):
        raise ValueError('fresh materialized crossing attempt directory required')
    reviewed = load_review(packet, source_root, case_id)
    spec = json.loads((output / 'case-spec.json').read_text())
    if (spec.get('case_id') != case_id or
            reviewed['sources']['district_frontage'].get('selected_alternative') !=
            spec.get('district_frontage_review')):
        raise ValueError('reviewed original district frontage alternative differs')
    category = spec.get('crosswalk_category')
    if category not in ('marked', 'unmarked', 'outside'):
        raise ValueError('exact crosswalk category missing')
    inventory = reviewed['sources']['crosswalk_inventory']
    point = reviewed['sources']['pedestrian_route']['crossing_point_xy_m']
    point_categories = classify_body(
        [[point[0] - .01, point[1] - .01], [point[0] + .01, point[1] - .01],
         [point[0] + .01, point[1] + .01], [point[0] - .01, point[1] + .01]],
        inventory)
    if ((category == 'marked') != point_categories['marked'] or
            (category == 'unmarked') != point_categories['unmarked']):
        raise ValueError('reviewed original crossing point category differs')
    shutil.copy2(packet, output / 'reviewed-site.json')
    source_copy_root = output / 'reviewed-sources'
    for item in reviewed['review']['sources'].values():
        target = source_copy_root / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(source_root) / item['path'], target)
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
            raise ValueError('original business-district Native map readback differs')
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
        district = reviewed['sources']['district_frontage']
        roadway = reviewed['sources']['roadway']
        packet_data = {'assignment_id': reviewed['review']['assignment_id'],
            'case_id': case_id, 'original_trace_id': 'Native:' + sha(output / 'trace.jsonl'),
            'pedestrian_actor_id': route['pedestrian_actor_id'],
            'diagnostic_fixture': False,
            'site_source_sha256': reviewed['packet_sha256'],
            'site': {'roadway_id': route['roadway_id'],
                'approach_xy_m': route['approach_xy_m'],
                'crossing_exit_xy_m': route['exit_xy_m'],
                'roadway_polygon_xy_m': roadway['roadway_polygon_xy_m'],
                'start_curb_zone_polygon_xy_m': roadway['start_curb_zone_polygon_xy_m'],
                'opposite_curb_zone_polygon_xy_m': roadway['opposite_curb_zone_polygon_xy_m'],
                'crosswalk_inventory': inventory,
                'district_type': district['district_type'],
                'highway_span_ft': district['highway_span_ft'],
                'district_source_sha256': reviewed['review']['sources']['district_frontage']['sha256'],
                'controls_source_sha256': reviewed['review']['sources']['governing_controls']['sha256']},
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
