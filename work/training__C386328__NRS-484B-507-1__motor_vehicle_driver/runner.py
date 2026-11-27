"""Exact freight-zone Native acquisition entrypoint; CARLA imports remain lazy."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess

from freight_scene import CASES, CAMERAS, scene_request, validate_request
from native_construction import constructed_scene

AID = 'training__C386328__NRS-484B-507-1__motor_vehicle_driver'
FRAMES = 600
RATE = 20


def case_id(slug):
    if slug not in CASES:
        raise ValueError('unknown freight-zone exact case')
    return AID + '__' + slug


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')


def xyz(value):
    return [value.x, value.y, value.z]


def body(actor):
    return [xyz(p) for p in actor.bounding_box.get_world_vertices(actor.get_transform())]


def check():
    checked = [validate_request(scene_request(slug)) for slug in CASES]
    return {'case_ids': [case_id(slug) for slug in CASES], 'source_requests': checked,
            'camera_names': sorted(CAMERAS), 'planned_frames': FRAMES,
            'rate_hz': RATE, 'original_native_observed': False,
            'physical_or_legal_acceptance': False}


def controls(carla, scene, actors, index):
    ego = actors['ego']
    if index < 110:
        speed = ego.get_velocity().length()
        ego.apply_control(carla.VehicleControl(throttle=max(0, min(.4, .25 * (4 - speed))),
                                               brake=0, steer=0))
    elif index < 470:
        ego.apply_control(carla.VehicleControl(throttle=0, brake=1, steer=0, hand_brake=True))
    else:
        ego.apply_control(carla.VehicleControl(throttle=.35, brake=0, steer=0, hand_brake=False))
    passenger = actors['passenger']
    if passenger is not None:
        target = [0, -3.2, .5] if 170 <= index < 420 else [0, -6, .5]
        location = passenger.get_location()
        dx, dy = target[0] - location.x, target[1] - location.y
        distance = math.hypot(dx, dy)
        direction = carla.Vector3D(dx / distance, dy / distance, 0) if distance > .05 else carla.Vector3D(0, 0, 0)
        passenger.apply_control(carla.WalkerControl(direction=direction,
                                                    speed=1 if distance > .05 else 0))
    waiting = actors['waiting_vehicle']
    if waiting is not None:
        waiting.apply_control(carla.VehicleControl(throttle=0, brake=1, steer=0))
    if scene['material']['requested_activity'] == 'pickup_loading' and index == 260:
        actors['material'].set_transform(carla.Transform(carla.Location(
            *scene['material']['source_and_destination_xyz'][1])))


def capture(slug, output, host='127.0.0.1', port=2000):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot as world_snapshot, restore as world_restore

    scene = scene_request(slug)
    validate_request(scene)
    output = Path(output).resolve()
    if output.exists() and any((output / name).exists() for name in
                               ('video_frames.jsonl', 'freight_trace.jsonl', 'capture-seal.json')):
        raise ValueError('retain prior Native attempt; choose a fresh output')
    output.mkdir(parents=True, exist_ok=True)
    client = carla.Client(host, port)
    client.set_timeout(120)
    prior = world_snapshot(client)
    encoders = {}
    core = None
    restored = None
    try:
        with constructed_scene(client, carla, scene) as actors:
            world = actors['world']
            (output / 'road.xodr').write_text(actors['map_opendrive'])
            cameras = {}
            for spec in scene['cameras']:
                incoming = queue.Queue()
                actors['cameras'][spec['name']].listen(incoming.put)
                cameras[spec['name']] = incoming
                encoders[spec['name']] = subprocess.Popen(
                    ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'bgra',
                     '-video_size', f"{spec['size'][0]}x{spec['size'][1]}", '-framerate', '20',
                     '-i', '-', '-frames:v', '600', '-c:v', 'ffv1',
                     str(output / (spec['name'] + '.mkv'))], stdin=subprocess.PIPE)
            core = PipelineCapture(client, actors['ego'], output, case_id(slug),
                                   required_observations=[])
            first_elapsed = None
            civil_start = datetime(2026, 11, 23, scene['civil_time']['requested_minute_local'] // 60,
                                   scene['civil_time']['requested_minute_local'] % 60,
                                   tzinfo=timezone(timedelta(hours=-8)))
            with (output / 'video_frames.jsonl').open('x') as frames_file, \
                    (output / 'freight_trace.jsonl').open('x') as trace_file, \
                    (output / 'ego_body.jsonl').open('x') as body_file, \
                    (output / 'material_body.jsonl').open('x') as material_file, \
                    (output / 'passenger_body.jsonl').open('x') as passenger_file, \
                    (output / 'waiting_body.jsonl').open('x') as waiting_file:
                for index in range(FRAMES):
                    controls(carla, scene, actors, index)
                    native = world.tick()
                    snap = world.get_snapshot()
                    if snap.frame != native:
                        raise RuntimeError('original Native tick/snapshot mismatch')
                    if first_elapsed is None:
                        first_elapsed = snap.timestamp.elapsed_seconds
                    elapsed = snap.timestamp.elapsed_seconds - first_elapsed
                    if abs(elapsed - index / RATE) > .005:
                        raise RuntimeError('original 20 Hz frame join differs')
                    core.capture(native, elapsed, extra={'freight_source': {
                        'material_actor_id': actors['material'].id,
                        'passenger_actor_id': actors['passenger'].id if actors['passenger'] else None,
                        'waiting_actor_id': actors['waiting_vehicle'].id if actors['waiting_vehicle'] else None}})
                    source_cameras, hashes = {}, {}
                    for name, incoming in cameras.items():
                        image = incoming.get(timeout=30)
                        if image.frame != native:
                            raise RuntimeError('original source camera/Native frame mismatch: ' + name)
                        source_cameras[name] = image.frame
                        hashes[name] = hashlib.sha256(image.raw_data).hexdigest()
                        encoders[name].stdin.write(image.raw_data)
                    frame = {'video_frame': index, 'native_frame': native, 'carla_frame': native,
                             'time_s': index / RATE, 'native_elapsed_s': elapsed,
                             'source_cameras': source_cameras,
                             'camera_rgb_sha256': hashes}
                    frames_file.write(json.dumps(frame, allow_nan=False) + '\n')
                    ego, material = actors['ego'], actors['material']
                    velocity = ego.get_velocity()
                    trace_file.write(json.dumps({**frame, 'vehicle_id': ego.id,
                        'observed_speed_mps': velocity.length(), 'vehicle_xyz_m': xyz(ego.get_location()),
                        'material_xyz_m': xyz(material.get_location()),
                        'passenger_xyz_m': xyz(actors['passenger'].get_location()) if actors['passenger'] else None,
                        'waiting_vehicle_xyz_m': xyz(actors['waiting_vehicle'].get_location()) if actors['waiting_vehicle'] else None,
                        'civil_timestamp': (civil_start + timedelta(seconds=index / RATE)).isoformat(),
                        'requested_material_activity': scene['material']['requested_activity'],
                        'requested_passenger_activity': scene['passenger']['requested_activity'],
                        'original_material_or_passenger_transfer_verified': False,
                        'original_interference_verified': False}, allow_nan=False) + '\n')
                    body_file.write(json.dumps({'native_frame': native, 'actor_id': ego.id,
                                                'body_vertices_m': body(ego)}, allow_nan=False) + '\n')
                    material_file.write(json.dumps({'native_frame': native, 'actor_id': material.id,
                                                    'body_vertices_m': body(material)}, allow_nan=False) + '\n')
                    for actor, stream in ((actors['passenger'], passenger_file),
                                          (actors['waiting_vehicle'], waiting_file)):
                        stream.write(json.dumps({'native_frame': native, 'actor_id': actor.id if actor else None,
                                                 'body_vertices_m': body(actor) if actor else None},
                                                allow_nan=False) + '\n')
            for process in encoders.values():
                process.stdin.close()
                if process.wait(timeout=120) != 0:
                    raise RuntimeError('original source camera encoder failed')
            for name in CAMERAS:
                count = subprocess.check_output(
                    ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                     '-show_entries', 'stream=nb_read_frames', '-of', 'default=nokey=1:noprint_wrappers=1',
                     str(output / (name + '.mkv'))], text=True, timeout=120).strip()
                if count != '600':
                    raise ValueError('original source camera full decode differs: ' + name)
            core.close(confirmed=True)
            core = None
            source_names = ('road.xodr', 'freight_trace.jsonl', 'ego_body.jsonl',
                            'material_body.jsonl', 'passenger_body.jsonl', 'waiting_body.jsonl',
                            'video_frames.jsonl')
            write_json(output / 'freight_context.json', {
                'case_id': case_id(slug), 'source_kind': 'original_native_freight_zone_readback',
                'source_sha256': {name: sha(output / name) for name in source_names},
                'zone_authority_confirmed': False, 'actual_material_transfer_confirmed': False,
                'actual_passenger_transfer_confirmed': False, 'interference_confirmed': False,
                'physical_or_legal_acceptance': False})
        restored = world_restore(client, prior)
        write_json(output / 'acquisition-provenance.json', {
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'native_executed': True, 'physical_acceptance_claimed': False})
        seal_capture(output, frames=FRAMES, restoration=restored, errors=[],
                     encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                     context={'case_id': case_id(slug), 'physical_acceptance_claimed': False,
                              'original_activity_review_required': True})
        return {'case_id': case_id(slug), 'source_frames': FRAMES,
                'original_capture_saved': True, 'physical_or_legal_acceptance': False}
    except BaseException:
        if core is not None:
            core.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                process.kill()
                process.wait()
        if restored is None:
            world_restore(client, prior)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(), sort_keys=True))
    else:
        selected = json.loads(Path('config.json').read_text()).get('selected_case_id', '')
        slug = args.case or selected.rsplit('__', 1)[-1]
        if selected and selected != case_id(slug):
            parser.error('config selected case and requested Native case differ')
        if slug not in CASES or not args.output_dir:
            parser.error('selected case and --output-dir required')
        print(json.dumps(capture(slug, args.output_dir, args.host, args.port), sort_keys=True))
