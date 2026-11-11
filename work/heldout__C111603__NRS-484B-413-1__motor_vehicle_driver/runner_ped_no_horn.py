"""CARLA-lazy exact pedestrian no-horn turn with source-bound participants."""
import argparse
import json
from pathlib import Path

from turn_native_route import select_left_turn, route_targets, control_step
from turn_deferred_audio import DeferredTurnSourceRecorder
from turn_listener_capture import ListenerCaptureProcess, require_microphone_device
import time
from turn_camera_capture import CAMERAS, LaneCameraCapture, LosslessSourceSink

CASE = 'heldout__C111603__NRS-484B-413-1__motor_vehicle_driver__ped_no_horn_audio'


def check_config(config):
    if (config.get('selected_case_id'), config.get('law_id'), config.get('cell_id'),
            config.get('actor')) != (CASE, 'NRS-484B-413-1', 'C111603', 'motor_vehicle_driver'):
        raise ValueError('Wrong exact turn-indicator construction identity')
    if (config.get('rate_hz'), config.get('frames'), config.get('duration_s')) != (20, 160, 8):
        raise ValueError('Exact turn needs 160 original frames at 20 Hz')
    cameras = config.get('cameras', [])
    if [(c.get('name'), c.get('width'), c.get('height'), c.get('fov_deg'))
            for c in cameras] != [(name, *spec[2], spec[3]) for name, spec in CAMERAS.items()]:
        raise ValueError('Exact turn four-camera profile differs')
    engineering = config.get('engineering', {})
    if set(engineering) - {'route_spacing_m', 'approach_steps', 'route_candidate_index',
                           'target_speed_mps', 'speed_gain', 'overview_x_m'}:
        raise ValueError('Unknown turn engineering control')
    if engineering.get('route_spacing_m', 2.) <= 0 or engineering.get('approach_steps', 6) < 4:
        raise ValueError('Invalid connected turn sampling')
    if not isinstance(config.get('case', {}).get('recording_description'), dict):
        raise ValueError('Missing exact recording description')
    return engineering


def run(output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture

    output = Path(output_dir)
    config = json.loads((output / 'config.json').read_text())
    engineering = check_config(config)
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    prior_settings = world.get_settings()
    ego = pedestrian = affected_vehicle = None
    cameras = pipeline = recorder = frame_map = capture = None
    sinks = {}
    frames = []
    errors = []
    restored = False
    previous_lights = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        scene = select_left_turn(world.get_map(),
                                 spacing_m=engineering.get('route_spacing_m', 2.),
                                 approach_steps=engineering.get('approach_steps', 6),
                                 candidate_index=engineering.get('route_candidate_index', 0))
        targets = route_targets(scene)
        library = world.get_blueprint_library()
        ego = world.try_spawn_actor(library.find('vehicle.tesla.model3'), scene['approach'][0].transform)
        if ego is None:
            raise ValueError('Native turn ego spawn failed')
        distant_exit = carla.Transform(scene['exit'].transform.location + carla.Location(x=50, y=50), scene['exit'].transform.rotation)
        affected_vehicle = world.try_spawn_actor(library.find('vehicle.audi.tt'), distant_exit)
        if affected_vehicle is None:
            raise ValueError('Affected Native vehicle spawn failed')
        ped_location = scene['approach'][0].transform.location + carla.Location(x=6, y=2, z=.5)
        pedestrian = world.try_spawn_actor(library.find('walker.pedestrian.0001'),
                                           carla.Transform(ped_location, scene['approach'][0].transform.rotation))
        if pedestrian is None:
            raise ValueError('Native pedestrian listener spawn failed')
        affected_vehicle.apply_control(carla.VehicleControl(hand_brake=True))
        previous_lights = ego.get_light_state()
        ego.set_light_state(carla.VehicleLightState(0))
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        cameras = LaneCameraCapture(world, carla, ego, sinks)
        pipeline = PipelineCapture(client, ego, output, CASE,
                                   required_observations=config.get('required_atoms', []))
        context = {
            'pedestrian_may_be_affected': True,
            'pedestrian_may_be_affected_source': 'Native pedestrian near selected connected left-turn corridor',
            'vehicle_may_be_affected': False,
            'vehicle_may_be_affected_source': 'Native vehicle displaced from selected left-turn corridor',
            'participant_types': {'ped_listener': 'pedestrian', 'affected_vehicle': 'vehicle'},
            'listener_position_source': 'original Native pedestrian transform',
            'participant_geometry_source': 'original Native actor transforms and bounding-box extents',
        }
        recorder = DeferredTurnSourceRecorder(output, ego,
                                      {'ped_listener': pedestrian, 'affected_vehicle': affected_vehicle},
                                      'ped_listener', context,
                                      int(carla.VehicleLightState.LeftBlinker),
                                      int(carla.VehicleLightState.RightBlinker))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        capture = ListenerCaptureProcess(output / 'listener.wav', device=require_microphone_device())
        capture.start()
        wall_start = time.monotonic()
        start = None
        for index in range(config['frames']):
            target = targets[min(1 + index // 16, len(targets)-1)]
            transform = ego.get_transform()
            location = transform.location
            forward = transform.get_forward_vector()
            velocity = ego.get_velocity()
            command = control_step((location.x, location.y), (forward.x, forward.y),
                                   (velocity.x, velocity.y), target,
                                   target_speed_mps=engineering.get('target_speed_mps', 5.),
                                   speed_gain=engineering.get('speed_gain', .25))
            ego.apply_control(carla.VehicleControl(**command))
            delay = wall_start + index * .05 - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native turn snapshot frame differs')
            if start is None:
                start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - start
            cameras.wait_for_frame(frame)
            pipeline.capture(frame, time_s)
            recorder.append(frame, time_s)
            frame_map.append(frame, time_s)
            frames.append(frame)
        cameras.verify(frames)
        recorder.close_raw()
        remaining_audio_s = wall_start + config['duration_s'] + .1 - time.monotonic()
        if remaining_audio_s > 0:
            time.sleep(remaining_audio_s)
        audio_provenance = capture.stop()
        capture = None
        recorder.finalize_audio(output / 'listener.wav', source_start_time_s=0.,
                                capture_provenance=audio_provenance)
    except BaseException as error:
        errors.append(str(error))
        raise
    finally:
        if frame_map is not None:
            frame_map.close()
        if capture is not None:
            capture.stop()
        if recorder is not None and not recorder.stream.closed:
            recorder.stream.close()
        if pipeline is not None:
            pipeline.close(confirmed=not errors)
        if cameras is not None:
            cameras.close()
        for sink in sinks.values():
            sink.close()
        if ego is not None:
            if previous_lights is not None:
                ego.set_light_state(previous_lights)
            ego.destroy()
        for actor in (affected_vehicle, pedestrian):
            if actor is not None:
                actor.destroy()
        world.apply_settings(prior_settings)
        current = world.get_settings()
        restored = (current.synchronous_mode == prior_settings.synchronous_mode and
                    current.fixed_delta_seconds == prior_settings.fixed_delta_seconds)
        if not restored:
            raise ValueError('Native turn world restoration differs')
    if errors or len(frames) != config['frames']:
        raise ValueError('Native turn capture incomplete')
    (output / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_frames': len(frames), 'audio_status': 'original_listener_pcm'}) + '\n')
    seal_capture(output, frames=len(frames), restoration={'restored': restored}, errors=[],
                 encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={'native_map_name': world.get_map().name,
                          'connected_left_route': True,
                          'pedestrian_may_be_affected': True,
                          'vehicle_may_be_affected': False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        check_config(json.loads(Path('config.json').read_text()))
        return
    if not args.output_dir:
        parser.error('--output-dir required for Native capture')
    run(args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
