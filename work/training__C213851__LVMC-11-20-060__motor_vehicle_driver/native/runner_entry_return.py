"""Prospective Native exit-and-return capture; --check never imports CARLA."""

import argparse
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from check_entry_return import check, read
from check_road import check as check_road
from runner import CAMERA_POSES, _camera, _review_site


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_all():
    return {'requests': check(), 'road': check_road(),
            'carla_started': False, 'physical_completion_claimed': False}


def capture(output_dir, policy, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    root = Path(__file__).resolve().parent
    config, requests = read(policy)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'native-rows.jsonl').exists():
        raise ValueError('Fresh Native attempt directory required')
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = snapshot(client)
    old_world = client.get_world()
    if prior['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))
            for actor in old_world.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned, encoders, camera_queues = [], {}, {}
    pipeline = None
    changed = complete = False
    try:
        road_path = root / 'road/road.xodr'
        check_road(road_path)
        world = client.generate_opendrive_world(
            road_path.read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.5,
                max_road_length=10, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=True))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        (output / 'road.xodr').write_text(mapping.to_opendrive())
        road_lane = mapping.get_waypoint(carla.Location(x=-6.25, y=-1.75, z=1),
            project_to_road=False, lane_type=carla.LaneType.Driving)
        sidewalk = mapping.get_waypoint(carla.Location(x=-6.25, y=-4.5, z=1),
            project_to_road=False, lane_type=carla.LaneType.Sidewalk)
        driveway = mapping.get_waypoint(carla.Location(x=0, y=-9, z=1),
            project_to_road=False, lane_type=carla.LaneType.Driving)
        if (road_lane is None or sidewalk is None or driveway is None or
                road_lane.road_id != 1 or sidewalk.road_id != 1 or
                driveway.road_id != 2):
            raise RuntimeError('Native road, sidewalk or driveway geometry absent')
        _review_site(output, road_path)
        entry_review_path = output / 'original-entry-site-review.json'
        if not entry_review_path.is_file():
            raise ValueError('Original roadway-entry and traffic site review missing')
        entry_review = json.loads(entry_review_path.read_text())
        if (entry_review.get('source_kind') != 'original_entry_site_review' or
                entry_review.get('authored_road_sha256') != sha(road_path) or
                entry_review.get('district') != 'residence' or
                entry_review.get('approaching_vehicle_lane_y_m') != -1.75 or
                entry_review.get('roadway_entry_reference_y_m') != -3.5 or
                entry_review.get('roadway_connection_reviewed') is not True or
                entry_review.get('approaching_vehicle_lane_reviewed') is not True):
            raise ValueError('Original roadway-entry site review incomplete')
        library = world.get_blueprint_library()
        vehicle_bp = library.find('vehicle.tesla.model3')
        vehicle_bp.set_attribute('role_name', 'c213851_driver')
        ego = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=-6.25, y=-1.75, z=1), carla.Rotation(yaw=0)))
        owned.append(ego)
        traffic_bp = library.find('vehicle.audi.tt')
        traffic_bp.set_attribute('role_name', 'c213851_approaching')
        traffic = world.spawn_actor(traffic_bp, carla.Transform(
            carla.Location(x=40.1, y=-1.75, z=1), carla.Rotation(yaw=180)))
        owned.append(traffic)
        pedestrians = sorted(library.filter('walker.pedestrian.*'), key=lambda bp: bp.id)
        if not pedestrians:
            raise RuntimeError('Separate Native pedestrian blueprint unavailable')
        pedestrian = world.spawn_actor(pedestrians[0], carla.Transform(
            carla.Location(x=8, y=-4.5, z=1), carla.Rotation(yaw=180)))
        owned.append(pedestrian)
        pipeline = PipelineCapture(client, ego, output, config['case_id'],
            visibility=False, required_observations=['kin.velocity'])
        cameras = json.loads((output / 'config.json').read_text())['cameras']
        if (len(cameras) != 4 or
                {spec['name'] for spec in cameras} != set(CAMERA_POSES) or
                json.loads((output / 'config.json').read_text())['duration_s'] != 60):
            raise ValueError('Exact 60-second four-camera profile missing')
        for spec in cameras:
            name = spec['name']
            sensor = _camera(world, library, carla, name, spec, ego)
            owned.append(sensor)
            stream = queue.Queue()
            sensor.listen(stream.put)
            camera_queues[name] = stream
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', '20', '-i', '-',
                '-frames:v', '1200', '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        first_time = None
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'native-rows.jsonl').open('x') as rows:
            for index, request in enumerate(requests):
                pose = ego.get_transform()
                target_x, target_y = request['requested_ego_world_xy_m']
                dx = target_x - pose.location.x
                dy = target_y - pose.location.y
                desired_speed = request['requested_ego_speed_mps']
                norm = max(math.hypot(dx, dy), .001)
                ego.set_target_velocity(carla.Vector3D(
                    x=desired_speed * dx / norm,
                    y=desired_speed * dy / norm))
                traffic.set_target_velocity(carla.Vector3D(x=-1.0, y=0, z=0))
                pedestrian.apply_control(carla.WalkerControl(
                    direction=carla.Vector3D(x=-1, y=0, z=0), speed=.5))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native frame differs')
                if first_time is None:
                    first_time = snap.timestamp.elapsed_seconds - .05
                time_s = (index + 1) / 20
                if abs(snap.timestamp.elapsed_seconds - first_time - time_s) > .001:
                    raise RuntimeError('Native 20 Hz time join differs')
                pipeline.capture(native_frame, time_s)
                camera_frames = {}
                for name, stream in camera_queues.items():
                    image = stream.get(timeout=30)
                    while image.frame < native_frame:
                        image = stream.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Native camera/frame join differs')
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s,
                    camera_native_frames=camera_frames)
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                pedestrian_pose = pedestrian.get_transform()
                traffic_pose = traffic.get_transform()
                traffic_velocity = traffic.get_velocity()
                row = {
                    'source_kind': 'original_native',
                    'native_frame': native_frame, 'video_frame': index,
                    'time_s': time_s, 'source_cameras': camera_frames,
                    'vehicle_actor_id': ego.id,
                    'pedestrian_actor_id': pedestrian.id,
                    'vehicle_xy_m': [pose.location.x, pose.location.y],
                    'vehicle_world_xy_m': [pose.location.x, pose.location.y],
                    'vehicle_half_extent_m': max(ego.bounding_box.extent.x,
                                                 ego.bounding_box.extent.y),
                    'vehicle_speed_mps': math.hypot(velocity.x, velocity.y),
                    'pedestrian_xy_m': [pedestrian_pose.location.x, 1.0],
                    'pedestrian_world_xy_m': [pedestrian_pose.location.x,
                                               pedestrian_pose.location.y],
                    'approaching_actor_id': traffic.id,
                    'approaching_world_xy_m': [traffic_pose.location.x,
                                                traffic_pose.location.y],
                    'approaching_speed_mps': math.hypot(
                        traffic_velocity.x, traffic_velocity.y),
                    'requested_ego_world_xy_m': request['requested_ego_world_xy_m'],
                    'requested_ego_speed_mps': desired_speed,
                    'requested_approaching_world_xy_m':
                        request['requested_approaching_world_xy_m'],
                    'phase': request['phase'],
                }
                rows.write(json.dumps(row, allow_nan=False) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            if process.wait(timeout=180):
                raise RuntimeError('Native camera encoding failed: ' + name +
                                   ': ' + error.decode()[-300:])
        from measure_sidewalk import SOURCE_FILES
        extra_sources = ('original-entry-site-review.json',)
        (output / 'captured-source-hashes.json').write_text(json.dumps({
            'format': 'original-native-sidewalk-source-seal',
            'source_kind': 'original_native_capture',
            'case_id': config['case_id'],
            'sha256': {name: sha(output / name) for name in
                       (*SOURCE_FILES, *extra_sources)},
            'physical_or_legal_outcome_claimed': False,
        }, indent=2) + '\n')
        complete = True
        return {'frames': 1200, 'camera_names': list(camera_queues),
                'physical_or_legal_outcome_claimed': False}
    finally:
        cleanup_error = None
        if pipeline is not None:
            try:
                pipeline.close(confirmed=complete)
            except Exception as error:
                cleanup_error = error
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        restoration = (restore(client, prior) if changed else
                       {'restored': True, 'world_unchanged': True})
        if complete:
            seal_capture(output, frames=1200, restoration=restoration,
                errors=[] if cleanup_error is None else [str(cleanup_error)],
                encoder_exit_codes={name: process.returncode
                                    for name, process in encoders.items()},
                context={'case_id': config['case_id'],
                         'candidate_id': 'primary',
                         'original_site_review': 'required'})
        if cleanup_error is not None:
            raise cleanup_error


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--case', choices=('yield_to_approaching',
                                           'enter_without_yield'))
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check_all()))
    else:
        suffix = args.case
        if not suffix or not args.output_dir:
            raise SystemExit('Original capture requires exact case and attempt directory')
        print(json.dumps(capture(args.output_dir, suffix, args.host, args.port)))
