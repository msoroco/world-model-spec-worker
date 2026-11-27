"""Original Native approach-to-curb speed capture; requested speed is not proof."""
import argparse
import json
import math
import queue
import subprocess
from pathlib import Path

from road_geometry import (DRIVING_LANE, DRIVING_Y_M, PARKING_LANE, PARKING_X_M,
                           PARKING_Y_M, ROAD_ID, check as check_road, road_xml)

AID = 'training__C229398__NRS-484B-600-1e__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SPEEDS = {'01': 75.0, '02': 79.5, '03': 85.0}
COUNT = 600
RATE = 20


def require(value, message):
    if not value:
        raise ValueError(message)


def check(config):
    case = config.get('case_id', '')
    require(case in {AID + '__probe_' + i for i in SPEEDS}, 'Wrong exact case')
    require((config.get('law_id'), config.get('cell_id'), config.get('actor')) ==
            ('NRS-484B-600-1e', 'C229398', 'motor_vehicle_driver'), 'Identity changed')
    require(config.get('frozen_cell') == {'layout': 'road', 'maneuver': 'park',
                                          'control': 'curb'}, 'Frozen cell changed')
    require((config.get('rate_hz'), config.get('duration_s'), config.get('frames')) ==
            (20, 30, 600), 'Original duration changed')
    require(config.get('requested_approach_speed_mph') == SPEEDS[case[-2:]],
            'Requested approach contrast changed')
    cameras = config.get('cameras', [])
    require([v.get('name') for v in cameras] == list(CAMERAS) and
            [(v.get('width'), v.get('height')) for v in cameras] ==
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)] and
            all(v.get('fov_deg') and v.get('pose_strategy') for v in cameras),
            'Four-camera capture contract changed')
    require(config.get('physical_acceptance_claimed') is False and
            config.get('legal_verdict') is None, 'Unobserved outcome claimed')
    check_road()
    return {'case_id': case, 'frames': COUNT, 'cameras': list(CAMERAS),
            'native_executed': False, 'physical_acceptance_claimed': False}


def control(speed_mps, target_mph, frame, x_m, y_m):
    """Engineering request: approach, curb entry, then parked hold."""
    require(0 <= frame < COUNT and math.isfinite(speed_mps), 'Bad control source')
    if frame < 400:
        target = target_mph / 2.2369362920544
        error = target - speed_mps
        return ('approach_driving', max(0.0, min(1.0, .35 + error * .15)),
                max(0.0, min(1.0, -error * .12)), 0.0)
    if frame < 520:
        lateral = PARKING_Y_M - y_m
        steer = max(-.28, min(.28, .05 * lateral))
        brake = .75 if speed_mps > 5 else .45
        return ('curb_parking', 0.0, brake, steer)
    return ('parked', 0.0, 1.0, 0.0)


def _pose(carla, x, y, z=1.0):
    return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=0))


def _sample(actor, mapping, carla):
    t = actor.get_transform()
    v = actor.get_velocity()
    waypoint = mapping.get_waypoint(t.location, project_to_road=False,
                                    lane_type=carla.LaneType.Any)
    return {'actor_id': actor.id, 'position_xyz_m': [t.location.x, t.location.y,
                                                     t.location.z],
            'velocity_xyz_mps': [v.x, v.y, v.z],
            'observed_speed_mph': math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)*2.2369362920544,
            'road_id': waypoint.road_id if waypoint else None,
            'lane_id': waypoint.lane_id if waypoint else None,
            'blueprint': actor.type_id}


def execute(config, output_dir, host, port):
    check(config)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore
    output = Path(output_dir)
    require(output.is_dir() and not (output / 'native-speed.jsonl').exists(),
            'Use a fresh materialized exact attempt')
    client = carla.Client(host, port)
    client.set_timeout(120)
    saved = snapshot(client)
    world = client.get_world()
    actors, cameras, encoders = [], {}, {}
    writer = None
    restored, encoder_codes = None, {}
    try:
        require(not saved['settings'].synchronous_mode,
                'Exclusive asynchronous world required')
        world = client.generate_opendrive_world(road_xml())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1/RATE
        world.apply_settings(settings)
        mapping = world.get_map()
        ego = world.try_spawn_actor(world.get_blueprint_library().find(config['ego_blueprint']),
                                    _pose(carla, -300, DRIVING_Y_M))
        require(ego is not None, 'Native vehicle spawn failed')
        actors.append(ego)
        first_sample = _sample(ego, mapping, carla)
        require((first_sample['road_id'], first_sample['lane_id']) ==
                (ROAD_ID, DRIVING_LANE), 'Original driving lane readback differs')
        for item in config['cameras']:
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(item['width']))
            bp.set_attribute('image_size_y', str(item['height']))
            bp.set_attribute('fov', str(item['fov_deg']))
            bp.set_attribute('sensor_tick', str(1/RATE))
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(*item['location_xyz_m']),
                carla.Rotation(*item['rotation_pyr_deg'])), attach_to=ego)
            actors.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            cameras[item['name']] = q
            encoders[item['name']] = subprocess.Popen(
                ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'rawvideo',
                 '-pix_fmt', 'bgra', '-s', f"{item['width']}x{item['height']}",
                 '-r', str(RATE), '-i', '-', '-frames:v', str(COUNT), '-c:v',
                 'ffv1', str(output / (item['name'] + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        writer = PipelineCapture(client, ego, output, config['case_id'],
                                 required_observations=config.get('required_atoms', []))
        first_time = None
        with FrameMap(output/'video_frames.jsonl') as fmap, \
                (output/'native-speed.jsonl').open('x') as trace:
            for i in range(COUNT):
                before = _sample(ego, mapping, carla)
                phase, throttle, brake, steer = control(
                    before['observed_speed_mph']/2.2369362920544,
                    config['requested_approach_speed_mph'], i,
                    before['position_xyz_m'][0], before['position_xyz_m'][1])
                ego.apply_control(carla.VehicleControl(throttle=throttle,
                                                       brake=brake, steer=steer))
                native = world.tick()
                stamp = world.get_snapshot().timestamp.elapsed_seconds
                if first_time is None:
                    first_time = stamp
                elapsed = stamp-first_time
                writer.capture(native, elapsed, extra={'phase': phase})
                camera_frames = {}
                for name, q in cameras.items():
                    image = q.get(timeout=30)
                    require(image.frame == native, 'Camera/native frame mismatch')
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                fmap.append(native, elapsed, camera_native_frames=camera_frames)
                trace.write(json.dumps({'frame': i, 'native_frame': native,
                    't_s': elapsed, 'source_kind': 'original_native_observation',
                    'phase': phase, 'requested_speed_mph': config['requested_approach_speed_mph'],
                    'sample': _sample(ego, mapping, carla),
                    'parking_target_xyz_m': [PARKING_X_M, PARKING_Y_M, 0]})+'\n')
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            encoder_codes[name] = process.wait(timeout=180)
            require(encoder_codes[name] == 0, 'Camera encode failed: '+name+' '+error.decode()[-200:])
        writer.close(confirmed=True)
    finally:
        if writer is not None and not writer.closed:
            writer.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(actors):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        restored = restore(client, saved)
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'native','diagnostic_fixture':False,
        'native_executed':True},indent=2)+'\n')
    seal_capture(output, frames=COUNT, restoration=restored, errors=[],
                 encoder_exit_codes=encoder_codes,
                 context={'case_id':config['case_id'],'original_phase_review_required':True})
    return {'case_id':config['case_id'],'original_frames':COUNT,
            'capture_sealed':True,'physical_acceptance_claimed':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads((Path(__file__).resolve().parent/'config.json').read_text())
    print(json.dumps(check(config) if args.check else
                     execute(config,args.output_dir,args.host,args.port)))
