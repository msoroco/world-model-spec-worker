"""Source-gated original C129731 reversal acquisition."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text())
    raw = (root / 'case-plan.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != config['plan_sha256']:
        raise ValueError('Exact reversal case plan changed')
    plan = json.loads(raw)
    matching = [row for row in plan['cases'] if row['case_id'] == config['selected_case_id']]
    if len(matching) != 1 or config['assignment_id'] != plan['assignment_id']:
        raise ValueError('Exact reversal case absent')
    if (config['law_id'] != 'NRS-484B-407' or config['cell_id'] != 'C129731' or
            config['actor'] != 'motor_vehicle_driver' or
            config['selected_case_id'] != config['assignment_id'] + '__' + config['suffix']):
        raise ValueError('Exact reversal identity changed')
    from native_case_constructor import DISTANCE_TARGETS_FT
    if (config['target_first_turn_distance_ft'] != DISTANCE_TARGETS_FT[config['suffix']] or
            config['rate_hz'] != 20 or config['frame_count'] != 900 or
            config['duration_s'] != 45 or [camera['name'] for camera in config['cameras']] !=
            ['overview', 'approach', 'reference_corner', 'driver_reference']):
        raise ValueError('Exact reversal distance or capture profile changed')
    return config['selected_case_id']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--site')
    parser.add_argument('--site-sha256')
    parser.add_argument('--output-dir')
    parser.add_argument('--carla-host', default='127.0.0.1')
    parser.add_argument('--carla-port', type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print('source-gated reversal bundle passed: ' + case)
        return
    if not args.site or not args.site_sha256 or not args.output_dir:
        raise ValueError('Reviewed original mountain-road site and output required')
    output_root = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
    if not output_root or not Path(args.output_dir).resolve().is_relative_to(Path(output_root).resolve()):
        raise ValueError('Original attempt must be under configured output root')
    from carla_sight_adapter import load_reviewed_site
    load_reviewed_site(Path(args.site), args.site_sha256)
    from carla_sight_adapter import capture_original_carla
    from native_case_constructor import construct_case
    from world_restore import snapshot, restore
    import carla
    client = carla.Client(args.carla_host, args.carla_port)
    client.set_timeout(30.0)
    saved = snapshot(client)
    actors = ()
    try:
        world = client.get_world()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        def transform(x, y, z, yaw):
            return carla.Transform(carla.Location(x=x, y=y, z=z),
                                   carla.Rotation(yaw=yaw))
        actors = construct_case(world, world.get_blueprint_library(),
                                Path(args.site), args.site_sha256, case, transform)
        result = capture_original_carla(
            world, actors[0], actors[1], Path(args.site), args.site_sha256,
            carla.Location, case, Path(args.output_dir),
            control_factory=carla.VehicleControl)
        print(json.dumps(result, sort_keys=True))
    finally:
        try:
            for actor in reversed(actors):
                actor.destroy()
        finally:
            restore(client, saved)


if __name__ == '__main__':
    main()
