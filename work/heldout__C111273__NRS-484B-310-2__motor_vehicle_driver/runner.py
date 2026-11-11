"""Native entrypoint for original flashing-yellow intersection capture."""
import argparse
import json
from math import atan2, cos, hypot, radians, sin
from pathlib import Path

from flashing_yellow import CASES
from native_signal import FlashController, construct_native
from signal_camera_capture import CAMERAS, FFmpegSourceSink, SignalCameraCapture
from signal_capture_session import SignalCaptureSession


def check_config(config):
    name = config.get('case_branch')
    if name not in CASES or not config.get('selected_case_id', '').endswith('__'+name):
        raise ValueError('runner requires one exact C111273 case')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-310-2', 'C111273', 'motor_vehicle_driver'):
        raise ValueError('runner law/cell/actor mismatch')
    if config.get('rate_hz') != 20 or config.get('frames') != 160 or config.get('duration_s') != 8:
        raise ValueError('runner requires 160 original 20 Hz frames')
    if {x.get('name') for x in config.get('cameras', [])} != set(CAMERAS):
        raise ValueError('four named source cameras required')
    if not config.get('official_control_source'):
        raise ValueError('official-control premise source required')
    if config.get('flash_period_s', .5) <= 0:
        raise ValueError('flash period must be positive')
    if config.get('target_speed_mps') != CASES[name].approach_target_mps:
        raise ValueError('case target speed differs from exact construction')
    return True


def _lane_control(world_map, actor, target_mps, carla, desired_yaw):
    """Track a through lane across the junction using a heading constrained lookahead."""
    if actor is None or not actor.is_alive:
        raise ValueError('controlled participant absent')
    transform = actor.get_transform()
    wp = world_map.get_waypoint(transform.location)
    if wp is None:
        raise ValueError('controlled participant left mapped road')
    choices = wp.next(6.0)
    candidates = []
    for successor in choices:
        diff = radians(float(successor.transform.rotation.yaw)-desired_yaw)
        alignment = cos(diff)
        if alignment >= .75:
            candidates.append((alignment, successor))
    if not candidates:
        raise ValueError('no forward through-lane lookahead')
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    target = candidates[0][1].transform.location
    heading = atan2(target.y-transform.location.y, target.x-transform.location.x)
    yaw = radians(transform.rotation.yaw)
    steering_error = atan2(sin(heading-yaw), cos(heading-yaw))
    velocity = actor.get_velocity()
    speed = hypot(velocity.x, velocity.y)
    error = target_mps-speed
    actor.apply_control(carla.VehicleControl(
        throttle=min(.6, max(0., .22*error)),
        brake=min(.8, max(0., -.3*error)),
        steer=min(.45, max(-.45, steering_error/.6))))


def run(output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    output = Path(output)
    config = json.loads((output/'config.json').read_text())
    check_config(config)
    case = CASES[config['case_branch']]
    client = carla.Client(host, port); client.set_timeout(30.)
    world = client.get_world(); original = world.get_settings()
    scene = None; camera = None; pipeline = None; session = None
    sinks = {}; frames = []; errors = []; restored = False
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True; settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        scene = construct_native(world, case, config['official_control_source'])
        for name in CAMERAS:
            sinks[name] = FFmpegSourceSink(output, name)
        camera = SignalCameraCapture(world, carla, scene['ego'], sinks)
        pipeline = PipelineCapture(client, scene['ego'], output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        selected = scene['selected']
        context = {'official_control_source': config['official_control_source'],
                   'selected_direction': selected.direction,
                   'opendrive_id': selected.opendrive_id,
                   'junction_id': selected.junction_id,
                   'flash_period_s': config.get('flash_period_s', .5),
                   'lens_pixel_visibility': 'requires original-camera review',
                   'legal_caution_judgment': 'unresolved'}
        session = SignalCaptureSession(output, pipeline, scene, context)
        yaw = selected.waypoint.transform.rotation.yaw
        cross_yaw = (scene['crossing_route']['start'].rotation.yaw
                     if scene['crossing_route'] is not None else None)
        with FlashController(scene['light'], carla.TrafficLightState,
                             period_s=config.get('flash_period_s', .5)) as flash:
            start = None
            for index in range(config['frames']):
                # State is set before the tick whose source pixels are retained.
                flash_row = flash.set_at(index*.05)
                _lane_control(world.get_map(), scene['ego'], case.approach_target_mps,
                              carla, yaw)
                if scene['crossing'] is not None:
                    _lane_control(world.get_map(), scene['crossing'], 6., carla, cross_yaw)
                frame = world.tick(); snapshot = world.get_snapshot()
                if snapshot.frame != frame:
                    raise ValueError('Native snapshot differs from completed tick')
                if str(scene['light'].get_state()) != flash_row['native_light_state']:
                    raise ValueError('flashing-yellow post-tick readback mismatch')
                if start is None:
                    start = snapshot.timestamp.elapsed_seconds
                time_s = snapshot.timestamp.elapsed_seconds-start
                camera.wait_for_frame(frame)
                session.capture(frame, time_s, flash_row)
                frames.append(frame)
        camera.verify_frames(frames)
    except BaseException as error:
        errors.append(str(error)); raise
    finally:
        if session is not None: session.close()
        if pipeline is not None: pipeline.close(confirmed=not errors)
        if camera is not None: camera.close()
        for sink in sinks.values(): sink.close()
        if scene is not None:
            for actor in reversed(scene['owned']): actor.destroy()
        world.apply_settings(original)
        current = world.get_settings()
        restored = (current.synchronous_mode == original.synchronous_mode
                    and current.fixed_delta_seconds == original.fixed_delta_seconds)
        if not restored:
            raise ValueError('Native world settings restoration readback differs')
    if errors or not frames:
        raise ValueError('Native capture did not finish')
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_frames': len(frames)})+'\n')
    seal_capture(output, frames=len(frames), restoration={'restored': restored},
                 errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={'native_map_name': world.get_map().name,
                          'junction_id': scene['selected'].junction_id,
                          'opendrive_id': scene['selected'].opendrive_id,
                          'light_actor_id': int(scene['light'].id)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        candidate = Path('config.json')
        if candidate.exists(): check_config(json.loads(candidate.read_text()))
        return
    if not args.output_dir: parser.error('--output-dir required')
    run(args.output_dir, args.host, args.port)


if __name__ == '__main__': main()
