"""Exact following-before-lane-change construction; CARLA imported lazily."""
import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = 'testing__C101303__NRS-484B-127-1__motor_vehicle_driver'


def load_scene(path=None):
    scene = json.loads(Path(path or ROOT/'scene.json').read_text())
    if (scene.get('law_id'), scene.get('cell_id'), scene.get('actor'),
            scene.get('layout'), scene.get('maneuver'), scene.get('control')) != (
            'NRS-484B-127-1', 'C101303', 'motor_vehicle_driver',
            'hill_crest', 'change_lane', 'other_vehicle'):
        raise ValueError('wrong frozen law, actor or cell')
    if not scene.get('case_id', '').startswith(ASSIGNMENT+'__'):
        raise ValueError('exact case ID does not belong to assignment')
    if scene.get('rate_hz') != 20 or scene.get('duration_s') != 45:
        raise ValueError('fixed 20 Hz/45 s capture contract changed')
    for name in ('target_body_gap_m', 'ego_target_speed_mps',
                 'leader_target_speed_mps', 'precipitation_percent'):
        value = scene.get(name)
        if type(value) not in (int, float) or not 0 <= value <= 100:
            raise ValueError('invalid finite engineering target: '+name)
    if 'fog_density_percent' in scene:
        value = scene['fog_density_percent']
        if type(value) not in (int, float) or not 0 <= value <= 100:
            raise ValueError('invalid Native fog target')
    if 'tire_friction' in scene:
        value = scene['tire_friction']
        if type(value) not in (int, float) or not 0 < value <= 10:
            raise ValueError('invalid Native tire friction target')
    if (scene['target_body_gap_m'] < 4 or
            scene['ego_target_speed_mps'] <= 0 or
            scene['leader_target_speed_mps'] <= 0):
        raise ValueError('invalid moving-leader following setup')
    if type(scene.get('surrounding_vehicle_count')) is not int or not 1 <= scene['surrounding_vehicle_count'] <= 12:
        raise ValueError('surrounding vehicle target outside supported capture domain')
    if scene.get('lane_change_start_s') != 21:
        raise ValueError('lane change must follow 14..20 s judgment window')
    if scene.get('route_seed_strategy', 'spawn') not in ('spawn', 'topology'):
        raise ValueError('unknown route seed strategy')
    return scene


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--scene')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    scene = load_scene(args.scene)
    if args.check:
        print(json.dumps({'case_id': scene['case_id'], 'construction_checked': True,
                          'physical_route_and_motion_pending': True}))
        return
    if not args.output_dir:
        parser.error('--output-dir required for explicit Native capture')
    from native_capture import run_native
    run_native(scene, args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
