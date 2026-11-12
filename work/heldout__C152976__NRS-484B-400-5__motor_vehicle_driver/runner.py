"""CARLA-lazy original capture for the one-way to one-way left-turn cases."""
import argparse
import json
from pathlib import Path

from one_way_left import CASES
from one_way_native_site import survey
from one_way_turn_control import command, target_route_points
from one_way_native_capture import OneWayNativeCapture
from one_way_camera import CAMERAS, LosslessSourceSink, TurnCameraCapture


def check_config(config):
    branch = config.get('case_branch')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-400-5', 'C152976', 'motor_vehicle_driver'):
        raise ValueError('Wrong one-way left-turn law/cell/actor')
    if branch not in CASES or not config.get('selected_case_id', '').endswith('__'+branch):
        raise ValueError('Wrong selected exact one-way turn case')
    if config.get('rate_hz') != 20 or config.get('frames') != 160 or config.get('duration_s') != 8:
        raise ValueError('Exact one-way turn needs 160 original 20 Hz frames')
    if {x.get('name') for x in config.get('cameras', [])} != set(CAMERAS):
        raise ValueError('Four named original source cameras required')
    if (not config.get('site_source') or not config.get('vehicle_blueprint_id') or
            not .5 <= config.get('lateral_scale', 0) <= 1.2 or
            not 0 < config.get('speed_kp', 0) <= .5 or
            not 2 <= config.get('lookahead_m', 0) <= 5):
        raise ValueError('Source-bound site or bounded turn controller missing')
    return True


def run(output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    output = Path(output)
    cfg = json.loads((output/'config.json').read_text())
    check_config(cfg)
    client = carla.Client(host, port); client.set_timeout(30.)
    world = client.get_world(); original = world.get_settings()
    ego = survey_result = camera = pipeline = native = None
    sinks = {}; frames = []; errors = []
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True; settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        source = output/cfg['site_source']
        survey_result = survey(world.get_map(), source)
        case = CASES[cfg['case_branch']]
        route = target_route_points(survey_result, case,
                                    lateral_scale=cfg['lateral_scale'])
        blueprint = world.get_blueprint_library().find(cfg['vehicle_blueprint_id'])
        ego = world.try_spawn_actor(blueprint, survey_result['approach'].transform)
        if ego is None:
            raise ValueError('One-way turn Native actor spawn failed')
        for name in CAMERAS:
            sinks[name] = LosslessSourceSink(output, name)
        camera = TurnCameraCapture(world, carla, ego, sinks,
            overview_height_delta_m=cfg.get('overview_height_delta_m', 0))
        pipeline = PipelineCapture(client, ego, output, cfg['selected_case_id'],
                                   required_observations=cfg.get('required_atoms', []))
        native = OneWayNativeCapture(output, ego, world.get_map(), survey_result, source)
        start = None
        for index in range(cfg['frames']):
            command(ego, carla, route, target_mps=cfg.get('target_speed_mps', 5.),
                    speed_kp=cfg['speed_kp'], lookahead_m=cfg['lookahead_m'])
            frame = world.tick(); snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native turn snapshot/frame differs')
            if start is None: start = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds-start
            camera.wait_for_frame(frame)
            capture = pipeline.capture(frame, time_s)
            if (capture.get('frame'), capture.get('time_s')) != (frame, time_s):
                raise ValueError('Pipeline capture original turn frame differs')
            native.append(frame, time_s)
            frames.append(frame)
        camera.verify(frames)
    except BaseException as error:
        errors.append(str(error)); raise
    finally:
        if native is not None: native.close()
        if pipeline is not None: pipeline.close(confirmed=not errors)
        if camera is not None: camera.close()
        for sink in sinks.values(): sink.close()
        if ego is not None: ego.destroy()
        world.apply_settings(original)
        current = world.get_settings()
        if (current.synchronous_mode != original.synchronous_mode or
                current.fixed_delta_seconds != original.fixed_delta_seconds):
            raise ValueError('Native world settings restoration readback differs')
    if not frames:
        raise ValueError('No original turn frames')
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_frames': len(frames)})+'\n')
    seal_capture(output, frames=len(frames), restoration={'restored': True},
                 errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={'native_map_name': world.get_map().name,
                          'site_source_id': survey_result['site_source_id'],
                          'subject_actor_id': int(ego.id)})


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
