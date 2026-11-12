"""C149237 qualifying-truck gap capture; no CARLA import during CPU check."""
import argparse
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import SIZES, source_cameras
from truck_capture_sources import record_sample
from truck_construction import spawn_exact_gap_pair
from truck_follow_controller import apply_pair
from truck_site import GAP_TARGETS_M, ROAD, validate_site
from width_construction import CASES as WIDTH_CASES, spawn_width_control_pair
from two_lane_construction import spawn_two_lane_pair
from two_lane_site import ROAD as TWO_LANE_ROAD
from overtaking_site import ROAD as OVERTAKING_ROAD
from overtaking_construction import spawn_overtaking_pair
from overtaking_controller import PassingPolicy


ASSIGNMENT = 'testing__C149237__NRS-484B-127-2__heavy_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def validate_config(config):
    if config.get('law_id') != 'NRS-484B-127-2' or config.get('cell_id') != 'C149237' or config.get('actor') != 'heavy_vehicle_driver':
        raise ValueError('Wrong heavy-truck case identity')
    selected = config.get('selected_case_id', '')
    suffix=selected.removeprefix(ASSIGNMENT + '__')
    if (not selected.startswith(ASSIGNMENT + '__') or
            suffix not in GAP_TARGETS_M and suffix not in WIDTH_CASES and suffix not in ('two_same_direction_lanes','overtaking')):
        raise ValueError('Runner supports only authored gap, width, lane and passing cases')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('Truck capture requires 20 Hz for 45 seconds')
    cameras = config.get('cameras')
    if not isinstance(cameras, list) or [c.get('name') for c in cameras] != list(CAMERAS):
        raise ValueError('All four named source cameras required')
    if any((c.get('width'), c.get('height')) != SIZES[c['name']] for c in cameras):
        raise ValueError('Wrong source camera dimensions')
    if config.get('blueprint_ids') != ['vehicle.carlamotors.european_hgv', 'vehicle.carlamotors.carlacola']:
        raise ValueError('Truck blueprint IDs changed')
    if suffix in WIDTH_CASES and config.get('width_candidate_blueprint_ids') != [
            'vehicle.carlamotors.carlacola', 'vehicle.carlamotors.firetruck',
            'vehicle.tesla.cybertruck', 'vehicle.carlamotors.european_hgv']:
        raise ValueError('Width case needs the pinned truck candidate search')
    if config.get('required_atoms') is None or config.get('source_packets') is None:
        raise ValueError('Missing Core observation contract')
    validate_site()
    return config


def camera_transforms(carla):
    def static(x, y, z, yaw, pitch):
        return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw, pitch=pitch))
    return {'overview': static(450, -1.9, 90, 0, -75),
            'approach': static(60, -1.9, 8, 0, -18),
            'reference_corner': static(330, -34, 35, 90, -25),
            'driver_reference': static(1, 0, 1.8, 0, -6)}


def sensor_frame(queue, expected):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError('Missing source camera frame ' + str(expected)) from error
        if image.frame == expected:
            return image
        if image.frame > expected:
            raise ValueError('Source camera skipped frame ' + str(expected))
    raise ValueError('Source camera frame join failed')


def capture(args, config):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output/'construction.json').is_file():
        raise ValueError('Use runtime.py capture to materialize the exact construction')
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = snapshot(client)
    helper = None
    encoders = {}
    frames = 0
    errors = []
    restoration = None
    try:
        selected_case=config['selected_case_id'].removeprefix(ASSIGNMENT + '__')
        authored_road=(TWO_LANE_ROAD if selected_case=='two_same_direction_lanes' else
                       OVERTAKING_ROAD if selected_case=='overtaking' else ROAD)
        client.generate_opendrive_world(authored_road.read_text())
        world = client.get_world()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        mapping = world.get_map()
        bp = world.get_blueprint_library()
        ego_bp, lead_bp = (bp.find(identifier) for identifier in config['blueprint_ids'])
        ego_bp.set_attribute('role_name', 'NRS-484B-127-2-heavy-ego')
        lead_bp.set_attribute('role_name', 'NRS-484B-127-2-heavy-lead')
        transform_at = lambda x,y,heading: carla.Transform(
            carla.Location(x=x,y=y,z=.5), carla.Rotation(yaw=heading))
        if selected_case in GAP_TARGETS_M:
            pair_context=spawn_exact_gap_pair(world,ego_bp,lead_bp,selected_case,transform_at)
        elif selected_case=='two_same_direction_lanes':
            pair_context=spawn_two_lane_pair(world,ego_bp,lead_bp,transform_at)
        elif selected_case=='overtaking':
            pair_context=spawn_overtaking_pair(world,ego_bp,lead_bp,transform_at)
        else:
            varied=[bp.find(identifier) for identifier in config['width_candidate_blueprint_ids']]
            pair_context=spawn_width_control_pair(world,selected_case,ego_bp,varied,transform_at)
        with pair_context as pair:
            ego, lead = pair['ego'], pair['lead']
            context = {'native_map_id': mapping.name, 'road_id': pair['site']['road_id'],
                       'lane_id': pair['site']['lane_id'],
                       'same_direction_lane_count': pair['site']['same_direction_lane_count'],
                       'lane_forward_xy': [1.0, 0.0],
                       'lane_count_source': 'authored OpenDRIVE '+str(pair['site']['same_direction_lane_count'])+' same-direction driving lanes; per-frame Native actor lane identity only',
                       'authored_road_sha256': pair['site']['road_sha256'],
                       'native_opendrive_sha256': hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
                       'legal_highway_status': 'source review required',
                       'overall_width_limit': 'single vehicles; Native bounding boxes, no trailer claim'}
            if selected_case=='overtaking':
                context['passing_lane_id']=pair['site']['passing_lane_id']
            (output/'road_context.json').write_text(json.dumps(context,indent=2)+'\n')
            with source_cameras(world, ego, camera_transforms(carla)) as cameras:
                queues = {name: Queue() for name in CAMERAS}
                for name, sensor in cameras.items():
                    sensor.listen(lambda image, name=name: queues[name].put(image))
                with ExitStack() as stack:
                    for name, (width, height) in SIZES.items():
                        encoders[name] = stack.enter_context(FFV1Writer(output/(name+'.mkv'),width,height))
                    frame_map = stack.enter_context(FrameMap(output/'video_frames.jsonl'))
                    history = stack.enter_context((output/'truck_history.jsonl').open('x',buffering=1))
                    helper = PipelineCapture(client, ego, output, config['selected_case_id'],
                                             required_observations=config['required_atoms'])
                    passing_policy=PassingPolicy() if selected_case=='overtaking' else None
                    try:
                        for _ in range(config['rate_hz'] * config['duration_s']):
                            if passing_policy is None:
                                apply_pair(ego, lead, carla.VehicleControl)
                            else:
                                passing_policy.apply(ego, lead, carla.VehicleControl)
                            world.tick()
                            snap = world.get_snapshot()
                            for name in CAMERAS:
                                image = sensor_frame(queues[name], snap.frame)
                                encoders[name].write(bytes(image.raw_data))
                            helper.capture(snap.frame, snap.timestamp.elapsed_seconds)
                            ego_wp = mapping.get_waypoint(ego.get_location(), project_to_road=False)
                            lead_wp = mapping.get_waypoint(lead.get_location(), project_to_road=False)
                            record_sample(frame_map, history, snap, ego, lead, ego_wp, lead_wp)
                            frames += 1
                    finally:
                        helper.close()
                        helper = None
    except BaseException as error:
        errors.append(str(error))
        raise
    finally:
        if helper is not None:
            helper.close(confirmed=False)
        restoration = restore(client, saved)
        if not errors:
            seal_capture(output,frames=frames,restoration=restoration,errors=[],
                         encoder_exit_codes={name: encoders[name].exit_code for name in CAMERAS},
                         context={'actual_truck_motion': 'source review required',
                                  'authored_one_way_site': True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    config = validate_config(json.loads(Path('config.json').read_text()))
    if args.check:
        print(json.dumps({'case_id': config['selected_case_id'], 'cpu_config_checked': True,
                          'simulation_started': False}))
        return
    if not args.output_dir:
        raise ValueError('Native capture requires --output-dir')
    capture(args,config)


if __name__ == '__main__':
    main()
