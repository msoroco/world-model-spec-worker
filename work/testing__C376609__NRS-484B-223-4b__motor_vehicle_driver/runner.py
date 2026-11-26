"""Source-gated original CARLA capture for the nine exact 4(b) probes."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from queue import Queue
import shutil
import subprocess
import tempfile

AID = 'testing__C376609__NRS-484B-223-4b__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
ROLES = ('map', 'public_highway', 'roadway_boundary', 'lane_design',
         'exclusive_turn_control', 'intersection_type', 'intersection_boundary',
         'straight_route', 'right_turn_route', 'sightline_obstruction',
         'driver_identity', 'motor_vehicle', 'independent_route_intent')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sealed_site(path, case):
    path = Path(path).resolve()
    site = json.loads(path.read_text())
    config = json.loads((Path(__file__).parent / 'config.json').read_text())
    target = config['case']
    if case != target['case_id'] or site.get('assignment_id') != AID or site.get('case_id') != case:
        raise ValueError('exact source/case identity differs')
    if site.get('reviewed_original_native_site') is not True or site.get('source_kind') != 'original_native_map_geometry':
        raise ValueError('reviewed original Native site required')
    refs = site.get('source_refs')
    if not isinstance(refs, list) or set(ROLES) - {r.get('role') for r in refs}:
        raise ValueError('reviewed highway, lane, route and sightline source refs required')
    for ref in refs:
        source = (path.parent / ref['path']).resolve()
        if not source.is_relative_to(path.parent) or not source.is_file() or sha(source) != ref.get('sha256'):
            raise ValueError('reviewed source bytes differ: ' + ref.get('role', 'unknown'))
    if site.get('map_sha256') != next(r['sha256'] for r in refs if r['role'] == 'map'):
        raise ValueError('Native map source differs')
    if (site.get('lane_design'), site.get('ego_lane_request'), site.get('route_request'),
            site.get('intersection_type'), site.get('sightline_request')) != (
            target['lane_design_request'], target['ego_lane_request'], target['route_request'],
            target['intersection_request'], target['sightline_request']):
        raise ValueError('reviewed site differs from selected probe')
    for key in ('map_name', 'map_sha256', 'native_spawn', 'trajectory_xy', 'approach_lane_ids',
                'right_turn_lane_id', 'intersection_entry_station_m', 'intersection_exit_station_m',
                'station_origin_xy', 'station_axis_xy', 'source_context'):
        if not site.get(key):
            raise ValueError('missing reviewed Native fact: ' + key)
    if site['right_turn_lane_id'] not in site['approach_lane_ids']:
        raise ValueError('reviewed right turn lane identity absent')
    if len(site['station_axis_xy']) != 2 or abs(math.hypot(*site['station_axis_xy']) - 1) > .001:
        raise ValueError('reviewed unit station axis required')
    if site['intersection_exit_station_m'] <= site['intersection_entry_station_m']:
        raise ValueError('reviewed intersection stations out of order')
    if len(site['trajectory_xy']) < 3 or any(len(x) != 2 for x in site['trajectory_xy']):
        raise ValueError('reviewed connected route trajectory required')
    context = site['source_context']
    if any(not context.get(x + '_source') for x in ROLES if x != 'map'):
        raise ValueError('measurement source context incomplete')
    if context.get('independent_route_intent') != target['route_request']:
        raise ValueError('independent route intent differs')
    return site


def capture(site, case, host, port, output):
    import carla
    from PIL import Image
    output = Path(output).resolve()
    if not output.is_dir() or '.runtime-work' not in output.parts or (output / 'capture-seal.json').exists():
        raise ValueError('materialized unsealed attempt under .runtime-work required')
    stage = Path(tempfile.mkdtemp(prefix='c376609-native-', dir=output.parent))
    client = carla.Client(host, int(port))
    client.set_timeout(20)
    world = client.get_world()
    original_settings = world.get_settings()
    owned = []
    pipeline = None
    try:
        native_map = world.get_map()
        if native_map.name != site['map_name'] or hashlib.sha256(native_map.to_opendrive().encode()).hexdigest() != site['map_sha256']:
            raise ValueError('Native original map differs from reviewed source')
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        bp = world.get_blueprint_library().find(site['native_spawn']['blueprint_id'])
        pose = site['native_spawn']['pose_xyz_ypr']
        if len(pose) != 6:
            raise ValueError('reviewed spawn pose required')
        ego = world.try_spawn_actor(bp, carla.Transform(carla.Location(x=pose[0], y=pose[1], z=pose[2]),
                                                    carla.Rotation(pitch=pose[3], yaw=pose[4], roll=pose[5])))
        if ego is None:
            raise ValueError('source-pose Native spawn failed')
        owned.append(ego)
        cameras = {}
        offsets = ((-18, 0, 20), (-9, 3, 5), (3, 4, 5), (0, 0, 2))
        for i, name in enumerate(CAMERAS):
            sensor_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            sensor_bp.set_attribute('image_size_x', str(1920 if i == 0 else 1280))
            sensor_bp.set_attribute('image_size_y', str(1080 if i == 0 else 720))
            sensor_bp.set_attribute('sensor_tick', '0.05')
            xyz = offsets[i]
            sensor = world.spawn_actor(sensor_bp, carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2])), attach_to=ego)
            q = Queue()
            sensor.listen(q.put)
            owned.append(sensor)
            cameras[name] = q
            (stage / ('frames-' + name)).mkdir()
        from pipeline_capture import PipelineCapture
        pipeline = PipelineCapture(client, ego, output, case)
        rows, frame_map = [], []
        path_index = 0
        prior = None
        for i in range(900):
            loc = ego.get_location()
            path = site['trajectory_xy']
            while path_index < len(path) - 1 and math.hypot(loc.x - path[path_index][0], loc.y - path[path_index][1]) < 4:
                path_index += 1
            target = path[path_index]
            desired = math.degrees(math.atan2(target[1] - loc.y, target[0] - loc.x))
            delta = (desired - ego.get_transform().rotation.yaw + 180) % 360 - 180
            velocity = ego.get_velocity()
            speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
            stop = site['route_request'] == 'stop_before' and (loc.x - site['station_origin_xy'][0]) * site['station_axis_xy'][0] + (loc.y - site['station_origin_xy'][1]) * site['station_axis_xy'][1] >= site['intersection_entry_station_m'] - 4
            ego.apply_control(carla.VehicleControl(throttle=0 if stop else max(0, min(.5, (8 - speed) * .18)),
                                                   brake=1 if stop else max(0, min(.7, (speed - 8) * .2)),
                                                   steer=max(-.7, min(.7, delta * float(site.get('control_profile', {}).get('steer_gain', .025))))))
            frame = world.tick()
            pipeline.capture(frame, i / 20)
            stamp = world.get_snapshot().timestamp.elapsed_seconds
            if prior is not None and (frame != prior[0] + 1 or abs(stamp - prior[1] - .05) > .002):
                raise ValueError('Native frame/time discontinuity')
            prior = frame, stamp
            loc = ego.get_location()
            wp = native_map.get_waypoint(loc, project_to_road=False)
            if wp is None:
                raise ValueError('original lane waypoint absent')
            station = (loc.x - site['station_origin_xy'][0]) * site['station_axis_xy'][0] + (loc.y - site['station_origin_xy'][1]) * site['station_axis_xy'][1]
            row = {'frame': i, 'native_frame': frame, 'time_s': i / 20, 'lane_id': str(wp.lane_id),
                   'ego_station_m': station, 'speed_mps': speed, 'connected_route': site['route_request'] if site['route_request'] != 'stop_before' else 'none',
                   'position_xyz_m': [loc.x, loc.y, loc.z], 'position_m': [loc.x, loc.y], 'road_id': wp.road_id,
                   'junction_id': wp.get_junction().id if wp.is_junction else None}
            rows.append(row)
            hashes = {}
            for name, q in cameras.items():
                image = q.get(timeout=10)
                if image.frame != frame:
                    raise ValueError('original camera frame differs')
                rgba = Image.frombytes('RGBA', (image.width, image.height), bytes(image.raw_data), 'raw', 'BGRA')
                frame_path = stage / ('frames-' + name) / f'{i:04d}.png'
                rgba.convert('RGB').save(frame_path)
                hashes[name] = sha(frame_path)
            frame_map.append({'video_frame': i, 'carla_frame': frame, 'native_frame': frame, 'time_s': i / 20, 'camera_png_sha256': hashes})
        pipeline.close()
        context = dict(site['source_context'])
        context.update({'case_id': case, 'map_sha256': site['map_sha256'], 'lane_design': site['lane_design'],
                        'intersection_type': site['intersection_type'], 'independent_route_intent': site['route_request'],
                        'approach_lane_ids': site['approach_lane_ids'], 'right_turn_lane_id': site['right_turn_lane_id'],
                        'intersection_entry_station_m': site['intersection_entry_station_m'],
                        'intersection_exit_station_m': site['intersection_exit_station_m']})
        (stage / 'context.json').write_text(json.dumps(context, sort_keys=True) + '\n')
        (stage / 'original-trace.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
        (stage / 'video_frames.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in frame_map))
        videos = {}
        for name in CAMERAS:
            video = stage / (name + '.mkv')
            subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-framerate', '20', '-i', str(stage / ('frames-' + name) / '%04d.png'), '-frames:v', '900', '-c:v', 'ffv1', str(video)], check=True)
            videos[name] = {'path': video.name, 'sha256': sha(video), 'frame_count': 900}
            shutil.rmtree(stage / ('frames-' + name))
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(stage / 'overview.mkv'),
                        '-i', str(stage / 'approach.mkv'), '-i', str(stage / 'reference_corner.mkv'),
                        '-i', str(stage / 'driver_reference.mkv'), '-filter_complex',
                        '[0:v]scale=960:540[a];[1:v]scale=960:540[b];[2:v]scale=960:540[c];[3:v]scale=960:540[d];'
                        '[a][b][c][d]xstack=inputs=4:layout=0_0|960_0|0_540|960_540[v]',
                        '-map', '[v]', '-frames:v', '900', '-c:v', 'ffv1', str(stage / 'raw.mkv')], check=True)
        receipt = {'assignment_id': AID, 'case_id': case, 'source_kind': 'original_native_capture',
                   'diagnostic_fixture': False, 'fps': 20, 'frame_count': 900,
                   'context_sha256': sha(stage / 'context.json'), 'trace_sha256': sha(stage / 'original-trace.jsonl'),
                   'frame_map_sha256': sha(stage / 'video_frames.jsonl'), 'reviewed_site_sha256': site['site_sha256'],
                   'cameras': videos, 'physical_acceptance': False, 'legal_verdict': None}
        (stage / 'receipt.json').write_text(json.dumps(receipt, sort_keys=True) + '\n')
        (stage / 'acquisition-provenance.json').write_text(json.dumps({'provenance_kind': 'native', 'diagnostic_fixture': False}, sort_keys=True) + '\n')
        for source in stage.iterdir():
            destination = output / source.name
            if destination.exists():
                raise ValueError('capture output collision: ' + source.name)
            os.replace(source, destination)
        stage.rmdir()
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        if pipeline is not None:
            pipeline.close(confirmed=False)
        if owned:
            try:
                owned[0].apply_control(carla.VehicleControl(brake=1))
            except Exception:
                pass
        for actor in reversed(owned):
            try:
                actor.destroy()
            except Exception:
                pass
        world.apply_settings(original_settings)
    from worker_exchange.native_output import seal_capture
    seal_capture(output, frames=900, restoration={'restored': True}, errors=[],
                 encoder_exit_codes={name: 0 for name in CAMERAS})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--site')
    parser.add_argument('--host')
    parser.add_argument('--port')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    config = json.loads((Path(__file__).parent / 'config.json').read_text())
    case = config['case']['case_id']
    if args.case not in (None, case):
        raise ValueError('selected case differs')
    if args.check:
        print('source-gated nine-case Native runner static check passed: ' + case)
        return
    site_path = args.site or os.environ.get('C376609_REVIEWED_SITE')
    if not all((site_path, args.host, args.port, args.output_dir)):
        raise ValueError('reviewed site, Native host/port and fresh output required')
    site = sealed_site(site_path, case)
    site['site_sha256'] = sha(site_path)
    site['control_profile'] = config.get('control_profile', {})
    capture(site, case, args.host, args.port, args.output_dir)


if __name__ == '__main__':
    main()
