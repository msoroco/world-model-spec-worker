"""Bicycle dismount construction for the assigned prohibited U-turn cell.

CARLA is imported only on explicit Native execution. The prop identifiers are
checked against the local blueprint library.
"""
import argparse
import json
import math
import os
from pathlib import Path

SCENE = Path(__file__).with_name('scene.json')


def load_scene(path=SCENE):
    scene = json.loads(Path(path).read_text())
    if scene['law_id'] != 'LVMC-11-40-080' or scene['cell_id'] != 'C10808':
        raise ValueError('wrong law or cell identity')
    if scene['actor'] != 'cycle_or_scooter_operator':
        raise ValueError('wrong operator identity')
    if not (scene['approach_x_m'] < scene['sign']['x_m'] < scene['dismount_x_m'] < scene['turn_x_m']):
        raise ValueError('sign/dismount/turn order is invalid')
    if not scene['turn_x_m'] > scene['exit_x_m']:
        raise ValueError('return path must reverse longitudinal direction')
    if scene['alley_half_width_m'] <= 0 or scene['control']['dismount_hold_s'] <= 0:
        raise ValueError('turning width and dismount interval must be positive')
    return scene


def path_points(scene):
    """The reversal begins only after the dismount station."""
    half = scene['alley_half_width_m']
    turn = [(scene['dismount_x_m'], -half / 2),
                  (scene['turn_x_m'], -half / 2),
                  (scene['turn_x_m'] + half, 0.0),
                  (scene['turn_x_m'], half / 2),
                  (scene['exit_x_m'], half / 2)]
    approach = [(scene['approach_x_m'], -half / 2), (scene['dismount_x_m'], -half / 2)]
    return {'mounted': approach if scene['dismount_enabled'] else approach + turn[1:],
            'afoot': turn if scene['dismount_enabled'] else []}


def choose_blueprint(library, pattern):
    matches = list(library.filter(pattern))
    if not matches:
        raise ValueError('required physical blueprint unavailable: ' + pattern)
    return matches[0]


def spawn_scene(world, scene, transform_factory):
    """Create the sign, bicycle and one persistent human operator.

    transform_factory(x,y,z,yaw) is injected so CPU tests can check actual calls.
    The no-U-turn sign graphic/authorization must be confirmed locally; a traffic
    cone is deliberately rejected as a sign so this draft never claims readiness.
    """
    library = world.get_blueprint_library()
    sign = scene['sign']
    if not sign['blueprint_filter'].startswith('static.prop.sign'):
        raise ValueError('configured object is not a prohibition sign blueprint')
    actors = {}
    try:
        for name, pattern, pose in (
            ('sign', sign['blueprint_filter'],
             (sign['x_m'], sign['y_m'], 0.0, sign['yaw_deg'])),
            ('bicycle', scene['bicycle']['blueprint_filter'],
             (scene['approach_x_m'], -scene['alley_half_width_m']/2, 0.0, 0.0)),
            ('operator', scene['operator']['blueprint_filter'],
             (scene['approach_x_m'], -scene['alley_half_width_m']/2, 0.0, 0.0))):
            blueprint = choose_blueprint(library, pattern)
            actor = world.spawn_actor(blueprint, transform_factory(*pose))
            if actor is None:
                raise ValueError('Native actor spawn failed: '+name)
            actors[name] = actor
        return actors
    except BaseException:
        for actor in reversed(list(actors.values())):
            if hasattr(actor, 'destroy'):
                actor.destroy()
        raise


def phase_at(scene, x_m, elapsed_since_dismount_s):
    if not scene['dismount_enabled']:
        return 'mounted_approach' if x_m < scene['dismount_x_m'] else 'mounted_reversal'
    if x_m < scene['dismount_x_m']:
        return 'mounted_approach'
    if elapsed_since_dismount_s < scene['control']['dismount_hold_s']:
        return 'dismount_hold'
    return 'afoot_reversal'


def _route_pose(points, distance_m):
    if not points:
        raise ValueError('constructed route has no points')
    remaining = max(0.0, distance_m)
    for start, end in zip(points, points[1:]):
        length = math.dist(start, end)
        if length <= 1e-6:
            raise ValueError('constructed route has zero-length segment')
        fraction = min(1.0, remaining/length)
        if remaining <= length:
            return (start[0]+fraction*(end[0]-start[0]),
                    start[1]+fraction*(end[1]-start[1]),
                    math.degrees(math.atan2(end[1]-start[1], end[0]-start[0])),
                    False)
        remaining -= length
    start, end = points[-2:]
    return (end[0], end[1],
            math.degrees(math.atan2(end[1]-start[1], end[0]-start[0])), True)


def trajectory(scene, elapsed_s):
    """Requested actor poses and phase; Native body samples verify realization."""
    if not math.isfinite(elapsed_s) or elapsed_s < 0:
        raise ValueError('invalid elapsed construction time')
    routes = path_points(scene)
    mounted = routes['mounted']
    mounted_length = sum(math.dist(a,b) for a,b in zip(mounted,mounted[1:]))
    mounted_time = mounted_length/scene['control']['mounted_speed_mps']
    if not scene['dismount_enabled']:
        pose = _route_pose(mounted, elapsed_s*scene['control']['mounted_speed_mps'])
        phase = ('turn_complete' if pose[3] else
                 'mounted_approach' if elapsed_s*scene['control']['mounted_speed_mps'] <
                    scene['dismount_x_m']-scene['approach_x_m'] else 'mounted_reversal')
        return {'operator': pose[:3], 'bicycle': pose[:3], 'phase': phase}
    dismount_pose = _route_pose(mounted, mounted_length)[:3]
    if elapsed_s < mounted_time:
        pose = _route_pose(mounted, elapsed_s*scene['control']['mounted_speed_mps'])
        return {'operator': pose[:3], 'bicycle': pose[:3],
                'phase': 'mounted_approach'}
    afoot_elapsed = elapsed_s-mounted_time-scene['control']['dismount_hold_s']
    if afoot_elapsed <= 0:
        return {'operator': dismount_pose, 'bicycle': dismount_pose,
                'phase': 'dismount_hold'}
    pose = _route_pose(routes['afoot'],
                       afoot_elapsed*scene['control']['afoot_speed_mps'])
    separated = math.dist(pose[:2], dismount_pose[:2]) >= 1.0
    phase = 'turn_complete' if pose[3] else ('afoot_reversal' if separated
                                             else 'dismount_hold')
    return {'operator': pose[:3], 'bicycle': dismount_pose,
            'phase': phase}


def check():
    scene = load_scene()
    points = path_points(scene)
    if scene['dismount_enabled']:
        assert points['mounted'][-1] == points['afoot'][0]
        assert phase_at(scene, scene['turn_x_m'], 0) == 'dismount_hold'
        assert phase_at(scene, scene['turn_x_m'], scene['control']['dismount_hold_s']) == 'afoot_reversal'
    else:
        assert not points['afoot']
        assert phase_at(scene, scene['turn_x_m'], 0) == 'mounted_reversal'
    print(json.dumps({'geometry_checked': True, 'sign_blueprint_unverified': scene['sign']['blueprint_filter']}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--authorization-source')
    parser.add_argument('--scene', default=str(SCENE))
    args = parser.parse_args()
    if args.check:
        check()
    else:
        source = args.authorization_source or os.environ.get(
            'C10808_SIGN_AUTHORIZATION_SOURCE')
        if not args.output_dir or not source:
            parser.error('Native capture requires --output-dir and sign authorization source via --authorization-source or C10808_SIGN_AUTHORIZATION_SOURCE')
        from native_capture import run_native
        run_native(load_scene(args.scene), args.output_dir, args.host, args.port,
                   source)


if __name__ == '__main__':
    main()
