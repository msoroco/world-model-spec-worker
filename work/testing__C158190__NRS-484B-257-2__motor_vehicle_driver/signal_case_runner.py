"""Signal-control exception capture for the C158190 signed intersection.

The case retains the stop sign and adds a governing signal. The requested green
phase is an engineering setup, never a legal exception verdict.
"""

import argparse
from contextlib import ExitStack, contextmanager
import json
from pathlib import Path
from queue import Queue

import runner as base
import signal_exception as signal


CASE_ID = base.PREFIX + 'signal_control_exception'


def validate_config(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-257-2', 'C158190', 'motor_vehicle_driver'):
        raise ValueError('Wrong signal exception assignment')
    if config.get('selected_case_id') != CASE_ID:
        raise ValueError('Wrong exact signal exception case')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 30:
        raise ValueError('Signal exception requires 20 Hz for 30 seconds')
    if config.get('target_signal_state') != 'Green':
        raise ValueError('Explicit green engineering target required')
    if [c.get('name') for c in config.get('cameras', ())] != list(base.CAMERAS):
        raise ValueError('Four named original source cameras required')
    if any((c.get('width'), c.get('height')) != base.SIZES[c['name']]
           or c.get('fov_deg') != 90 for c in config['cameras']):
        raise ValueError('Source camera profile differs')
    if 'dev.stop_sign' not in config.get('required_atoms', ()):
        raise ValueError('Stop-sign observation missing')
    signal.validate_signal_map(signal.authored_signal_map())
    return config


@contextmanager
def staged_actors(world, carla):
    """Reuse signed-route actor geometry after validating both Native controls."""
    site = base.validate_native_site(world, location_factory=carla.Location)
    native_light = signal.readback_governing_light(world)
    light = next(actor for actor in world.get_actors().filter('traffic.traffic_light*')
                 if actor.id == native_light['native_signal_id'])
    with base.stage_case(world, base.PREFIX + 'stop_other_inside',
                         location_factory=carla.Location) as staging:
        yield dict(staging, site=site, light=light, native_light=native_light)


class SignalStage:
    """Keep ego moving under a sourced green phase; no stop obligation inferred."""

    released = False

    def __init__(self, light):
        self.light = light

    def target(self, distance_to_reference_m, observed_speed_mps, *,
               before_reference, within_intersection, other_clear):
        state = str(self.light.get_state())
        if 'Green' not in state:
            raise ValueError('Governing Native signal left requested green phase')
        if not other_clear and distance_to_reference_m <= 18 and not within_intersection:
            return 0.0
        return 5.0 if distance_to_reference_m <= 18 or within_intersection else 8.0


def signal_source_row(world, staging, frame):
    if world.get_snapshot().frame != frame:
        raise ValueError('Signal source frame differs from Native snapshot')
    light = staging['light']
    affected = light.get_affected_lane_waypoints()
    if not any(wp.road_id == 158190 and wp.lane_id == -1 for wp in affected):
        raise ValueError('Native governing light changed affected lane')
    vertices = light.trigger_volume.get_world_vertices(light.get_transform())
    if len(vertices) < 4:
        raise ValueError('Native signal trigger geometry disappeared')
    return {'frame': frame, 'native_signal_id': light.id,
            'state': str(light.get_state()),
            'affected_ego_road_id': 158190, 'affected_ego_lane_id': -1,
            'trigger_vertices_m': [base._xyz(p) for p in vertices],
            'source': 'Native light actor, affected lane and frame join'}


def capture(args, config):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / 'construction.json').is_file():
        raise ValueError('Use runtime.py capture to materialize exact construction')
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = snapshot(client)
    encoders = {}
    helper = None
    frames = 0
    succeeded = False
    try:
        world = client.generate_opendrive_world(signal.authored_signal_map())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        with staged_actors(world, carla) as staging:
            light = staging['light']
            prior_state = light.get_state()
            light.freeze(True)
            try:
                light.set_state(carla.TrafficLightState.Green)
                world.tick()
                if light.get_state() != carla.TrafficLightState.Green:
                    raise ValueError('Native signal green-state readback failed')
                stage = SignalStage(light)
                context = {'native_map_id': world.get_map().name,
                           'intersection_id': 158191, 'ego_approach_road_id': 158190,
                           'ego_route_road_ids': [158190, 158192, 158193],
                           'native_stop_sign_id': staging['site']['native_stop_sign_id'],
                           'native_signal_id': light.id,
                           'sign_governance_source': 'Native_stop_trigger_and_authored_OpenDRIVE',
                           'entrance_inventory_source': 'Native_controls_and_camera_review_pending',
                           'stop_reference_source': 'authored_boundary_and_camera_review_pending',
                           'highway_status_source': 'authored_site_and_map_review_pending',
                           'non_through_highway': None, 'police_control': None,
                           'traffic_signal_control': None, 'ego_entrance_device': 'stop',
                           'entrances': [{'road_id': 158190, 'device': 'stop_and_signal'},
                                         {'road_id': 158194, 'device': 'unreviewed'},
                                         {'road_id': 158196, 'device': 'unreviewed'}]}
                (output / 'intersection_context.json').write_text(
                    json.dumps(context, indent=2) + '\n')
                with base.source_cameras(world, staging['ego'],
                                         base.camera_transforms(carla)) as cameras:
                    queues = {name: Queue() for name in base.CAMERAS}
                    for name, sensor in cameras.items():
                        sensor.listen(lambda image, name=name: queues[name].put(image))
                    with ExitStack() as stack:
                        for name in base.CAMERAS:
                            width, height = base.SIZES[name]
                            encoders[name] = stack.enter_context(
                                base.FFV1Writer(output / (name + '.mkv'), width, height))
                        helper = PipelineCapture(client, staging['ego'], output,
                                                 config['selected_case_id'],
                                                 required_observations=config['required_atoms'])
                        try:
                            with (output / 'entry_history.jsonl').open('x') as history, \
                                 (output / 'video_frames.jsonl').open('x') as frame_map, \
                                 (output / 'stop_control_inventory.jsonl').open('x') as controls, \
                                 (output / 'signal_control_inventory.jsonl').open('x') as signals:
                                for index in range(config['rate_hz'] * config['duration_s']):
                                    command = base.apply_motion(world, staging, stage, carla)
                                    world.tick()
                                    snap = world.get_snapshot()
                                    for name in base.CAMERAS:
                                        image = base.sensor_frame(queues[name], snap.frame)
                                        encoders[name].write(bytes(image.raw_data))
                                    helper.capture(snap.frame, snap.timestamp.elapsed_seconds,
                                                   extra={'signal_exception_control': command})
                                    controls.write(json.dumps(base.observe_stop_control(
                                        world, staging['site']['native_stop_sign_id'],
                                        frame=snap.frame), sort_keys=True) + '\n')
                                    signals.write(json.dumps(signal_source_row(
                                        world, staging, snap.frame), sort_keys=True) + '\n')
                                    row = base.source_row(world, staging, snap.frame,
                                                          snap.timestamp.elapsed_seconds, index)
                                    history.write(json.dumps(row, sort_keys=True) + '\n')
                                    frame_map.write(json.dumps({
                                        'video_frame': index, 'carla_frame': snap.frame,
                                        'time_s': snap.timestamp.elapsed_seconds},
                                        sort_keys=True) + '\n')
                                    frames += 1
                            succeeded = True
                        finally:
                            helper.close(confirmed=succeeded)
                            helper = None
            finally:
                light.set_state(prior_state)
                light.freeze(False)
    finally:
        if helper is not None:
            helper.close(confirmed=False)
        restoration = restore(client, saved)
    if succeeded:
        seal_capture(output, frames=frames, restoration=restoration, errors=[],
                     encoder_exit_codes={name: encoders[name].exit_code
                                         for name in base.CAMERAS},
                     context={'selected_case_id': CASE_ID,
                              'signal_governance_review_pending': True,
                              'stop_and_hazard_legal_review_pending': True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    config = validate_config(json.loads(Path('config.json').read_text()))
    if args.check:
        print(json.dumps({'case_id': CASE_ID, 'cpu_config_checked': True,
                          'signal_map_sha256': signal.validate_signal_map(
                              signal.authored_signal_map())['map_sha256'],
                          'simulation_started': False}))
        return
    if not args.output_dir:
        raise ValueError('Native capture requires --output-dir')
    capture(args, config)


if __name__ == '__main__':
    main()
