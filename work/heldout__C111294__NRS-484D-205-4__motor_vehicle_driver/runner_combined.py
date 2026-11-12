"""Lazy Native entrypoint for original C111294 backup-lamp capture."""
import argparse
import json
from math import hypot
from pathlib import Path

from lamp_scene import drive_through, set_backup_lamp
from combined_lamp_asset import construct_combined, verify_combined_capture
from lamp_source_capture import LampSourceRecorder
from lamp_camera_capture import CAMERAS, FFmpegSourceSink, LampCameraCapture


CASES = {'forward_combined_backup_lamp_off': (1, False)}


def check_config(config):
    branch = config.get('case_branch')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484D-205-4', 'C111294', 'motor_vehicle_driver'):
        raise ValueError('Incorrect law/cell/actor')
    if branch not in CASES or not config.get('selected_case_id', '').endswith('__'+branch):
        raise ValueError('Unknown exact backup-lamp case')
    count, lamp_on = CASES[branch]
    if (config.get('installed_backup_lamp_count'), config.get('command_backup_lamp_on')) != (count, lamp_on) or config.get('lamp_arrangement') != 'combined':
        raise ValueError('Exact combined case equipment or lamp setting differs')
    if config.get('rate_hz') != 20 or config.get('frames') != 160 or config.get('duration_s') != 8:
        raise ValueError('Exact case requires 160 frames at 20 Hz')
    if {camera['name'] for camera in config.get('cameras', [])} != set(CAMERAS):
        raise ValueError('Four named original cameras required')
    if (not config.get('ego_blueprint_id') or not config.get('other_blueprint_id')
            or not config.get('equipment_inventory') or
            not 30 <= config.get('approach_m', 0) <= 60 or
            not 25 <= config.get('exit_m', 0) <= 50 or
            not .1 <= config.get('speed_gain', 0) <= .3):
        raise ValueError('Missing sourced vehicle and intersection setup')
    return True


def _participant(actor):
    if not actor.is_alive:
        raise ValueError('Other vehicle disappeared during capture')
    p = actor.get_transform().location
    v = actor.get_velocity()
    return {'actor_id': int(actor.id), 'center_xy_m': [float(p.x), float(p.y)],
            'speed_mps': hypot(v.x, v.y)}


def run(output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    output = Path(output)
    config = json.loads((output/'config.json').read_text())
    check_config(config)
    client = carla.Client(host, port); client.set_timeout(30.)
    world = client.get_world(); original = world.get_settings()
    scene = camera = pipeline = recorder = frame_map = None
    sinks = {}; participant_stream = None; frames = []; errors = []
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True; settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        scene = construct_combined(world, carla, config, output/config['equipment_inventory'])
        for name in CAMERAS:
            sinks[name] = FFmpegSourceSink(output, name)
        camera = LampCameraCapture(world, carla, scene['ego'], sinks)
        pipeline = PipelineCapture(client, scene['ego'], output,
                                   config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        recorder = LampSourceRecorder(output, scene['ego'], scene['equipment'],
                                      int(carla.VehicleLightState.Reverse))
        frame_map = FrameMap(output/'video_frames.jsonl')
        participant_stream = (output/'other_vehicle.jsonl').open('x')
        (output/'intersection_context.json').write_text(json.dumps(scene['context'])+'\n')
        start = None
        for index in range(config['frames']):
            set_backup_lamp(scene['ego'], carla, config['command_backup_lamp_on'])
            drive_through(scene['ego'], world.get_map(), carla, scene['ego_route'],
                          speed_mps=config.get('ego_speed_mps', 5.),
                          gain=config['speed_gain'])
            drive_through(scene['other'], world.get_map(), carla, scene['other_route'],
                          speed_mps=config.get('other_speed_mps', 4.),
                          gain=config['speed_gain'])
            frame = world.tick(); snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Original snapshot/frame identity differs')
            if start is None: start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds-start
            camera.wait_for_frame(frame)
            pipeline_row = pipeline.capture(frame, time_s)
            if (pipeline_row.get('frame'), pipeline_row.get('time_s')) != (frame, time_s):
                raise ValueError('Pipeline capture original frame differs')
            recorder.append(frame, time_s)
            other = _participant(scene['other'])
            other.update(frame=frame, time_s=time_s)
            participant_stream.write(json.dumps(other)+'\n'); participant_stream.flush()
            frame_map.append(frame, time_s)
            frames.append(frame)
        camera.verify_frames(frames)
        verify_combined_capture(output/'equipment.json', config['ego_blueprint_id'])
    except BaseException as error:
        errors.append(str(error)); raise
    finally:
        if participant_stream is not None: participant_stream.close()
        if frame_map is not None: frame_map.close()
        if recorder is not None: recorder.close()
        if pipeline is not None: pipeline.close(confirmed=not errors)
        if camera is not None: camera.close()
        for sink in sinks.values(): sink.close()
        if scene is not None:
            for actor in reversed(scene['owned']): actor.destroy()
        world.apply_settings(original)
        restored = world.get_settings()
        if (restored.synchronous_mode != original.synchronous_mode or
                restored.fixed_delta_seconds != original.fixed_delta_seconds):
            raise ValueError('Native world settings restoration readback differs')
    if not frames:
        raise ValueError('No original Native frames')
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_frames': len(frames)})+'\n')
    seal_capture(output, frames=len(frames), restoration={'restored': True},
                 errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={'native_map_name': world.get_map().name,
                          'junction_id': scene['context']['junction_id'],
                          'ego_actor_id': int(scene['ego'].id),
                          'other_vehicle_actor_id': int(scene['other'].id)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check: return
    if not args.output_dir: parser.error('--output-dir required')
    run(args.output_dir, args.host, args.port)


if __name__ == '__main__': main()
