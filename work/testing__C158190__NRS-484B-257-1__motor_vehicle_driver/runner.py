"""C158190 Native runner draft for source-bound yield-sign capture.

The CPU --check path never imports CARLA or contacts a server. Native capture
requires a fresh attempt materialized by runtime.py and an operator-owned world.
No physical or legal acceptance is inferred by this runner.
"""

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import SIZES, source_cameras
from yield_capture_sources import ApproachSourceWriter
from yield_construction import stage_case
from yield_control_sources import ControlWriter, observe_controls
from yield_controller import PREFIX, Stage
from yield_interaction_sources import InteractionWriter, observe_interaction
from yield_motion import apply_motion
from yield_site import validate_authored_site

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SUFFIXES = ('yield_nearest_view_through_approaches',
            'yield_nearest_view_through_entered',
            'yield_nearest_view_clear', 'yield_nearest_view_no_slow')


def validate_config(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-257-1', 'C158190', 'motor_vehicle_driver'):
        raise ValueError('Wrong C158190 assignment identity')
    case_id = config.get('selected_case_id')
    if case_id not in {PREFIX + suffix for suffix in SUFFIXES}:
        raise ValueError('Unknown exact C158190 case')
    if config.get('supported_case_ids') != [PREFIX + suffix for suffix in SUFFIXES]:
        raise ValueError('Four exact case IDs required')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 30:
        raise ValueError('C158190 capture requires 20 Hz for 30 seconds')
    cameras = config.get('cameras')
    if not isinstance(cameras, list) or [c.get('name') for c in cameras] != list(CAMERAS):
        raise ValueError('Four named source cameras required')
    if any((c.get('width'), c.get('height')) != SIZES[c['name']]
           or c.get('fov_deg') != 90 for c in cameras):
        raise ValueError('Source camera profile differs')
    if not isinstance(config.get('required_atoms'), list) or not isinstance(config.get('source_packets'), list):
        raise ValueError('Missing source observation contract')
    validate_authored_site()
    Stage(case_id)
    return config


def camera_transforms(carla):
    def pose(x, y, z, yaw, pitch):
        return carla.Transform(carla.Location(x=x, y=y, z=z),
                               carla.Rotation(yaw=yaw, pitch=pitch))
    return {'overview': pose(-15, 0, 48, 0, -85),
            'approach': pose(-38, -16, 9, 30, -13),
            'reference_corner': pose(19, -25, 15, 135, -24),
            'driver_reference': pose(1.0, 0, 1.6, 0, -5)}


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
    from original_observations import visible_relation
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / 'construction.json').is_file():
        raise ValueError('Use runtime.py capture to materialize the exact construction')
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = snapshot(client)
    frames = 0
    encoders = {}
    helper = None
    writer = None
    succeeded = False
    try:
        world, site = __import__('yield_site').load_native_site(client)
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        with stage_case(world, config['selected_case_id']) as staging:
            ego, through = staging['ego'], staging['through']
            # Native map facts and original cameras must support these claims in
            # saved processing. Unknown is retained rather than invented absence.
            (output / 'road_context.json').write_text(json.dumps({
                'native_map_id': world.get_map().name,
                'intersection_id': 158191,
                'approach_road_id': 158190, 'approach_lane_id': -1,
                'through_highway_id': 158195,
                'native_yield_sign_id': site['native_yield_sign_id'],
                'sign_governance_source': 'native_yield_trigger_and_authored_opendrive',
                'marking_inventory_source': 'capture/native_map_facts.json_and_source_cameras_review_pending',
                'no_stop_line': None, 'no_near_crosswalk': None,
                'police_control': None, 'traffic_signal_control': None
            }, indent=2) + '\n')
            with source_cameras(world, ego, camera_transforms(carla)) as cameras:
                queues = {name: Queue() for name in CAMERAS}
                for name, sensor in cameras.items():
                    sensor.listen(lambda image, name=name: queues[name].put(image))
                with ExitStack() as stack:
                    for name, (width, height) in SIZES.items():
                        encoders[name] = stack.enter_context(
                            FFV1Writer(output / (name + '.mkv'), width, height))
                    writer = ApproachSourceWriter(output)
                    controls = ControlWriter(output)
                    interactions = InteractionWriter(output)
                    helper = PipelineCapture(client, ego, output, config['selected_case_id'],
                                             required_observations=config['required_atoms'])
                    try:
                        for index in range(config['rate_hz'] * config['duration_s']):
                            control = apply_motion(world, staging, control_factory=carla.VehicleControl)
                            world.tick()
                            snap = world.get_snapshot()
                            for name in CAMERAS:
                                image = sensor_frame(queues[name], snap.frame)
                                encoders[name].write(bytes(image.raw_data))
                            helper.capture(snap.frame, snap.timestamp.elapsed_seconds,
                                           extra={'yield_construction_control': control})
                            controls.add(observe_controls(world, site['native_yield_sign_id'],
                                                          frame=snap.frame))
                            interactions.add(observe_interaction(world, ego, through,
                                                                 snap.frame,
                                                                 snap.timestamp.elapsed_seconds))
                            ego_wp = world.get_map().get_waypoint(ego.get_location(), project_to_road=False)
                            if ego_wp is not None and ego_wp.road_id == 158190:
                                writer.add(world, ego, through, snap.frame,
                                           snap.timestamp.elapsed_seconds, index,
                                           location_factory=carla.Location,
                                           visible_relation=visible_relation)
                            else:
                                writer.add_nonapproach_frame(snap.frame,
                                                             snap.timestamp.elapsed_seconds, index)
                            frames += 1
                        succeeded = True
                    finally:
                        writer.close()
                        helper.close(confirmed=succeeded)
                        helper = None
    finally:
        if helper is not None:
            helper.close(confirmed=False)
        restoration = restore(client, saved)
    if succeeded:
        seal_capture(output, frames=frames, restoration=restoration, errors=[],
                     encoder_exit_codes={name: encoders[name].exit_code for name in CAMERAS},
                     context={'selected_case_id': config['selected_case_id'],
                              'sign_face_and_marking_review_pending': True,
                              'actual_yield_behavior_review_pending': True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    config = validate_config(json.loads(Path('config.json').read_text()))
    if args.check:
        print(json.dumps({'case_id': config['selected_case_id'],
                          'cpu_config_checked': True, 'simulation_started': False}))
        return
    if not args.output_dir:
        raise ValueError('Native capture requires --output-dir')
    capture(args, config)


if __name__ == '__main__':
    main()
