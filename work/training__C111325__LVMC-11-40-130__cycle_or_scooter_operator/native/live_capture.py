"""Original Native bicycle capture proposal for the C111325 speed pair.

This code imports CARLA only inside execute. It must run against an authorized
exclusive local endpoint. Its returned traces still require saved processing,
independent physical/pixel audit and legal review.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess

from bicycle_control import apply as control_bicycle
from bicycle_setup import FRAMES, RATE_HZ as HZ, plan, setup
from survey import inspect as inspect_route

HERE = Path(__file__).resolve().parent
ROAD = HERE/'road.xodr'
NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check():
    from build_speed_road import check as check_road
    road = check_road(ROAD)
    plans = [plan(c) for c in ('condition_a', 'condition_b')]
    if (FRAMES != 600 or HZ != 20 or FRAMES/HZ != 30 or
            plans[0]['start_xyz_m'] != (-50.0, -1.75, 0.7) or
            [c['name'] for c in plans[0]['cameras']] != list(NAMES) or
            {k for k in plans[0] if plans[0][k] != plans[1][k]} !=
            {'condition', 'requested_peak_speed_mps'}):
        raise ValueError('Bicycle speed capture construction changed')
    return {'passed': True, 'road_sha256': sha(ROAD),
            'conditions': ['condition_a', 'condition_b'],
            'frames': FRAMES, 'rate_hz': HZ, 'cameras': list(NAMES),
            'original_native_executed': False,
            'legal_prudence_verdict': None}


def execute(condition, output_dir, host='127.0.0.1', port=2000, candidate='primary'):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore
    check()
    request = plan(condition, candidate)
    output = Path(output_dir).resolve()
    if output.exists():
        raise ValueError('Original attempt output must be fresh')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    original = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in original.get_actors()):
        raise ValueError('Exclusive idle asynchronous Native world required')
    owned, encoders, streams = [], {}, {}
    changed = False
    try:
        world = client.generate_opendrive_world(ROAD.read_text(),
            carla.OpendriveGenerationParameters(
                vertex_distance=.5, max_road_length=40, wall_height=0,
                additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1/HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        surveyed = inspect_route(world, carla)
        built = setup(world, carla, request, surveyed)
        owned.extend((built.bicycle, *built.cameras.values()))
        output.mkdir(parents=True)
        (output/'road.xodr').write_text(world.get_map().to_opendrive())
        (output/'route-survey.json').write_text(json.dumps(surveyed, indent=2)+'\n')
        (output/'capture-request.json').write_text(json.dumps(request, indent=2)+'\n')
        context = {'source_kind': 'original_native_actor_readback',
                   'cell_id': 'C111325', 'law_id': 'LVMC-11-40-130',
                   'actor': 'cycle_or_scooter_operator',
                   'bicycle_blueprint': built.bicycle.type_id,
                   'stop_sign_governs_route': surveyed['stop_sign_governs_route'],
                   'approach_lane_verified': surveyed['route_lane_verified'],
                   'municipal_jurisdiction_review_pending': True,
                   'fixed_conditions_id': 'c111325-dry-clear-stop-v1',
                   'legal_prudence_verdict': None,
                   'pedestrian_count': 0,
                   'clear_weather': surveyed['precipitation'] == 0,
                   'wetness': surveyed['wetness']}
        (output/'context.json').write_text(json.dumps(context, indent=2)+'\n')
        capture = output/'capture'
        graph_dir = capture/'native'/'graphs'/'base'
        graph_dir.mkdir(parents=True)
        cameras = {c['name']: c for c in request['cameras']}
        for name in NAMES:
            sensor = built.cameras[name]
            stream = queue.Queue()
            sensor.listen(stream.put)
            streams[name] = stream
            camera = cameras[name]
            path = output/(name+'.mkv')
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{camera['width']}x{camera['height']}", '-r', str(HZ),
                '-i', '-', '-frames:v', str(FRAMES), '-c:v', 'ffv1',
                '-level', '1', str(path)],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        prior, first_elapsed = None, None
        with FrameMap(output/'video_frames.jsonl') as frame_map, (
                output/'native-bicycle-trace.jsonl').open('x') as source_trace, (
                output/'trace.jsonl').open('x') as trace, (
                capture/'evidence.jsonl').open('x') as evidence, (
                capture/'native'/'frames.jsonl').open('x') as graph_frames:
            for index in range(FRAMES):
                control = control_bicycle(built.bicycle, carla, condition, prior)
                native_frame = world.tick()
                sample = world.get_snapshot()
                if sample.frame != native_frame:
                    raise ValueError('Original world frame mismatch')
                elapsed = sample.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed = elapsed
                time_s = elapsed-first_elapsed
                pose = built.bicycle.get_transform().location
                velocity = built.bicycle.get_velocity()
                speed = math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                vertices = built.bicycle.bounding_box.get_world_vertices(
                    built.bicycle.get_transform())
                body = [[v.x, v.y, v.z] for v in vertices]
                row = {'sample_index': index, 'native_frame': native_frame,
                       'time_s': time_s,
                       'source_kind': 'original_native_actor_readback',
                       'blueprint': built.bicycle.type_id,
                       'actor_id': built.bicycle.id, 'condition': condition,
                       'fixed_conditions_id': 'c111325-dry-clear-stop-v1',
                       'center_xy_m': [pose.x, pose.y],
                       'velocity_xy_mps': [velocity.x, velocity.y],
                       'requested_control': control, 'legal_verdict': None}
                frame_ids, raw_hashes = {}, {}
                for name in NAMES:
                    image = streams[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = streams[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise ValueError('Original camera/source frame mismatch: '+name)
                    encoders[name].stdin.write(image.raw_data)
                    frame_ids[name] = image.frame
                    raw_hashes[name] = hashlib.sha256(image.raw_data).hexdigest()
                frame_map.append(native_frame, time_s,
                    camera_native_frames=frame_ids, source_rgb_sha256=raw_hashes)
                source_trace.write(json.dumps(row, allow_nan=False)+'\n')
                trace.write(json.dumps({
                    'frame': native_frame, 'time_s': time_s,
                    'position': {'x': pose.x, 'y': pose.y, 'z': pose.z},
                    'position_m': [pose.x, pose.y, pose.z],
                    'heading_deg': built.bicycle.get_transform().rotation.yaw,
                    'speed_mps': speed, 'speed_mph': speed/.44704,
                    'velocity_mps': [velocity.x, velocity.y, velocity.z],
                    'control': control, 'bicycle_source': {
                        'sample_index': index, 'native_frame': native_frame}},
                    allow_nan=False)+'\n')
                evidence.write(json.dumps({
                    'original_frame': native_frame, 'replay_frame': native_frame,
                    'recording_time_s': time_s,
                    'replay_simulation_time_s': time_s,
                    'actor_id': built.bicycle.id,
                    'ego': {'position_m': [pose.x, pose.y, pose.z],
                            'heading_deg': built.bicycle.get_transform().rotation.yaw,
                            'speed_mps': speed, 'body_vertices_m': body,
                            'speed_provenance': 'original_trace_actor_get_velocity'},
                    'world': {'weather': {'cloudiness': world.get_weather().cloudiness,
                                          'precipitation': world.get_weather().precipitation,
                                          'wetness': world.get_weather().wetness,
                                          'fog_density': world.get_weather().fog_density},
                              'road_projection': {'road_id': 1, 'section_id': 0,
                                                  'lane_id': -1, 's_m': pose.x+222}}},
                    allow_nan=False)+'\n')
                graph_name = f'graphs/base/{native_frame:08d}.adapter.json'
                (graph_dir/f'{native_frame:08d}.adapter.json').write_text(
                    json.dumps({'attributes': {'frame': native_frame},
                                'nodes': [], 'edges': []})+'\n')
                graph_frames.write(json.dumps({
                    'abstract': graph_name, 'adapter_graph': graph_name,
                    'base': graph_name, 'edges': 0, 'frame': native_frame,
                    'nodes': 0, 'simulation_time': time_s, 'time_s': time_s})+'\n')
                prior = {'position_x_m': pose.x}
        for name, encoder in encoders.items():
            encoder.stdin.close()
            error = encoder.stderr.read()
            if encoder.wait(timeout=180):
                raise RuntimeError('Original camera encode failed '+name+': '+error.decode()[-300:])
        (capture/'manifest.json').write_text(json.dumps({
            'frames': FRAMES, 'extraction_confirmed': True,
            'synthetic_diagnostic': False,
            'sources': {'road.xodr': sha(output/'road.xodr'),
                        'trace.jsonl': sha(output/'trace.jsonl')},
            'required_observations': []}, indent=2)+'\n')
        (capture/'recorder_info.txt').write_text(
            'Original CARLA actor readback and synchronized RGB capture.\n'
            +f'Create {built.bicycle.id}: {built.bicycle.type_id} (0)\n')
        names = ['road.xodr', 'route-survey.json', 'capture-request.json',
                 'context.json', 'native-bicycle-trace.jsonl',
                 'trace.jsonl', 'capture/evidence.jsonl',
                 'capture/native/frames.jsonl', 'capture/manifest.json',
                 'video_frames.jsonl',
                 *(name+'.mkv' for name in NAMES)]
        (output/'source-hashes.json').write_text(json.dumps({
            name: sha(output/name) for name in names}, indent=2)+'\n')
        return {'condition': condition, 'frames': FRAMES,
                'original_sources_written': True,
                'saved_processing_pending': True,
                'physical_acceptance_claimed': False,
                'legal_prudence_verdict': None}
    finally:
        for encoder in encoders.values():
            if encoder.poll() is None:
                encoder.kill()
                encoder.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            restore(client, saved)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--condition', choices=('condition_a', 'condition_b'))
    parser.add_argument('--candidate', choices=('primary', 'fallback1'), default='primary')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    elif args.condition and args.output_dir:
        print(json.dumps(execute(args.condition, args.output_dir, args.host, args.port,
                                 args.candidate)))
    else:
        parser.error('Supply --check or --condition with --output-dir')


if __name__ == '__main__':
    main()
