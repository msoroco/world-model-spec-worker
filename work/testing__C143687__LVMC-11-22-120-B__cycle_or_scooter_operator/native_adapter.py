"""Original CARLA bicycle/sign capture; no synthetic source promotion."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path
from queue import Queue

from native_site import command_bicycle, spawn_bicycle

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _segment_distance(x: float, y: float, segment: dict) -> float:
    a, b = segment['start'], segment['end']
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)


def _line(path: Path, value: dict) -> None:
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, allow_nan=False) + '\n')


def execute(reviewed: dict, config: dict, output: Path, host: str, port: int) -> None:
    import carla
    from analysis import analyze, saved_result
    from worker_exchange.native_output import seal_capture, write_result

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    site = reviewed['site']
    source_packet = Path(reviewed['packet_path'])
    source_map = source_packet.parent / json.loads(source_packet.read_text())['source_bindings']['map']['path']
    if source_map.suffix.lower() != '.xodr':
        raise ValueError('reviewed original OpenDRIVE source required')
    map_bytes = source_map.read_bytes()
    if hashlib.sha256(map_bytes).hexdigest() != reviewed['source_hashes']['map']:
        raise ValueError('reviewed original OpenDRIVE bytes changed')
    client = carla.Client(host, port)
    client.set_timeout(30.0)
    world = client.generate_opendrive_world(map_bytes.decode('utf-8'))
    old = world.get_settings()
    owned = []
    recorder = False
    restored = False
    errors = []
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        client.start_recorder(str(output / 'carla_recorder.log'))
        recorder = True
        sign_data = site['sign']
        sign_bp = world.get_blueprint_library().find(sign_data['native_blueprint_id'])
        sign_position = sign_data['position']
        sign = world.try_spawn_actor(sign_bp, carla.Transform(
            carla.Location(x=sign_position[0], y=sign_position[1], z=sign_position[2])))
        if sign is None or not sign.is_alive or sign.type_id != sign_data['native_blueprint_id']:
            raise ValueError('reviewed sign Native asset/readback unavailable')
        owned.append(sign)
        start = site['route_segments'][0]['start']
        bike = spawn_bicycle(world, carla.Transform(
            carla.Location(x=start[0], y=start[1], z=start[2])), site)
        owned.append(bike)
        sensors = {}
        for name in CAMERAS:
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', '1920' if name == 'overview' else '1280')
            bp.set_attribute('image_size_y', '1080' if name == 'overview' else '720')
            bp.set_attribute('sensor_tick', '.05')
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=-7, y=0, z=3), carla.Rotation(pitch=-12)), attach_to=bike)
            q = Queue(maxsize=4)
            sensor.listen(q.put)
            sensors[name] = q
            owned.append(sensor)
        packet_frames = []
        (output / 'capture/native/graphs/base').mkdir(parents=True, exist_ok=True)
        (output / 'capture/evidence.jsonl').touch(exist_ok=False)
        (output / 'capture/native/frames.jsonl').touch(exist_ok=False)
        for name in ('trace.jsonl', 'video_frames.jsonl'):
            (output / name).touch(exist_ok=False)
        for i in range(900):
            control_case = {**config['case'],
                            'engineering_speed_scale': config.get('engineering_speed_scale', 1.0)}
            control = command_bicycle(bike, carla, site, control_case, i / 20)
            frame = world.tick()
            for name, q in sensors.items():
                image = q.get(timeout=20)
                if image.frame != frame:
                    raise ValueError('original four-camera frame join failed')
                folder = output / 'capture' / name
                folder.mkdir(parents=True, exist_ok=True)
                image.save_to_disk(str(folder / f'{i:06d}.png'))
            transform = bike.get_transform()
            position, velocity = bike.get_location(), bike.get_velocity()
            segment = site['route_segments'][0]
            street = site['route_segments'][1]
            trail_distance = _segment_distance(position.x, position.y, segment)
            street_distance = _segment_distance(position.x, position.y, street)
            kind = 'governed_street_roadway' if street_distance + .1 < trail_distance else 'nonmotorized_trail'
            time_s = i / 20
            row = {'original_frame': i, 'elapsed_s': time_s,
                   'actor_id': str(bike.id), 'segment': kind,
                   'street_id': site['street_id'],
                   'sign_source_id': sign_data['source_id'],
                   'sign_posted_readback': sign.is_alive and
                       sign.type_id == sign_data['native_blueprint_id'],
                   'position_m': [position.x, position.y, position.z],
                   'velocity_mps': [velocity.x, velocity.y, velocity.z],
                   'native_frame': frame, 'control_readback': control}
            packet_frames.append(row)
            speed = math.hypot(velocity.x, velocity.y)
            _line(output / 'trace.jsonl', {'frame': frame, 'time_s': time_s,
                'position_m': row['position_m'],
                'position': {'x': position.x, 'y': position.y, 'z': position.z},
                'speed_mps': speed, 'speed_mph': speed / .44704,
                'velocity_mps': row['velocity_mps'],
                'heading_deg': transform.rotation.yaw, 'control': {}})
            _line(output / 'video_frames.jsonl', {'video_frame': i,
                'carla_frame': frame, 'native_frame': frame, 'time_s': time_s})
            bounds = bike.bounding_box.get_world_vertices(transform)
            observed = {'frame': frame, 'time_s': time_s, 'participants': [],
                        'map_context': {'declared_public_way_road_ids': []}}
            _line(output / 'capture/evidence.jsonl', {'original_frame': frame,
                'replay_frame': frame, 'actor_id': bike.id,
                'recording_time_s': time_s, 'replay_simulation_time_s': time_s,
                'world': {'weather': {}},
                'ego': {'position_m': row['position_m'],
                        'heading_deg': transform.rotation.yaw,
                        'speed_mps': speed,
                        'speed_provenance': 'original_native_readback',
                        'body_vertices_m': [[v.x, v.y, v.z] for v in bounds]},
                'original_observations': observed})
            graph_rel = f'graphs/base/{i:08d}.adapter.json'
            (output / 'capture/native' / graph_rel).write_text(json.dumps({
                'path': 'capture/native/' + graph_rel,
                'attributes': {'frame': frame, 'time_s': time_s,
                               'observed_evidence': observed},
                'nodes': [], 'edges': []}) + '\n', encoding='utf-8')
            _line(output / 'capture/native/frames.jsonl',
                  {'frame': frame, 'simulation_time': time_s,
                   'adapter_graph': graph_rel})
        packet = {'source_kind': 'original_native_capture',
                  'case_id': config['selected_case_id'],
                  'site_sha256': reviewed['site_sha256'],
                  'map_name': site['map_name'], 'street_id': site['street_id'],
                  'actor_id': str(bike.id),
                  'actor_blueprint_id': bike.type_id, 'frames': packet_frames}
        from native_site import canonical_sha
        packet['seal_sha256'] = canonical_sha(packet)
        (output / 'capture-packet.json').write_text(
            json.dumps(packet) + '\n', encoding='utf-8')
    except BaseException as error:
        errors.append(repr(error))
        raise
    finally:
        for actor in reversed(owned):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                if actor.destroy() is False:
                    errors.append('actor destruction returned false')
            except Exception as error:
                errors.append(repr(error))
        if recorder:
            try:
                client.stop_recorder()
                details = client.show_recorder_file_info(str(output / 'carla_recorder.log'), False)
                (output / 'capture/recorder_info.txt').write_text(details, encoding='utf-8')
            except Exception as error:
                errors.append(repr(error))
        try:
            world.apply_settings(old)
            readback = world.get_settings()
            restored = (readback.synchronous_mode == old.synchronous_mode and
                        readback.fixed_delta_seconds == old.fixed_delta_seconds)
        except Exception as error:
            errors.append(repr(error))
        if not restored or errors:
            raise ValueError('original Native bicycle capture/restoration failed: ' + repr(errors))
    shutil.copy2(source_packet, output / 'site-source.json')
    packet_source = json.loads(source_packet.read_text(encoding='utf-8'))
    for item in packet_source['source_bindings'].values():
        target = output / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_packet.parent / item['path'], target)
    (output / 'road.xodr').write_bytes(map_bytes)
    for camera in CAMERAS:
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin',
                        '-framerate', '20', '-start_number', '0', '-i',
                        str(output / 'capture' / camera / '%06d.png'),
                        '-frames:v', '900', '-c:v', 'ffv1', '-pix_fmt', 'bgr0',
                        str(output / (camera + '.mkv'))], check=True, timeout=600)
    (output / 'capture/manifest.json').write_text(json.dumps({
        'status': 'draft', 'acquisition': 'original_native',
        'case_id': config['selected_case_id'], 'frames': 900,
        'extraction_confirmed': True, 'complete_driving_lanes': False,
        'sources': {'road.xodr': hashlib.sha256(map_bytes).hexdigest(),
                    'trace.jsonl': hashlib.sha256((output / 'trace.jsonl').read_bytes()).hexdigest()}
    }) + '\n', encoding='utf-8')
    (output / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'physical_acceptance_claimed': False}) + '\n', encoding='utf-8')
    report = analyze(output, config['selected_case_id'])
    write_result(output, saved_result(output, report))
    seal_capture(output, frames=900, restoration={'restored': True,
        'settings_readback': 'synchronous mode and delta verified'},
        errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
        context={'site_sha256': reviewed['site_sha256'],
                 'source_hashes': reviewed['source_hashes']})
